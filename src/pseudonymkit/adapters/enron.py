"""Adapter: the Enron e-mail corpus -> the domain model.

Enron carries no human PII annotation, so the mentions here are **structurally derived** from the
message headers rather than annotated by anyone.  Every document records
``metadata["annotation"] == "structural"`` so that no result built on it is ever mistaken for one
built on gold spans.

The derivation is sound because of how the corpus is shaped:

* Every message has exactly **one** ``From:`` address and one ``X-From:`` display name, so sender
  pairs give an unambiguous name-to-address mapping.  Accumulated over the corpus that becomes a
  reliable identity table, which is then used to link names appearing anywhere — in recipient
  headers or in the body — to an address.
* **The address is a cross-document identity.**  ``ann.aardvark@enron.com`` is the same person in
  every mailbox that mentions him.  Enron is one of only two corpora in the meta corpus that supply
  that, and after n2c2 became unavailable it is the only one left, so it carries the cross-document
  stability metric alone.
* ``X-Folder:`` gives the folder-classification task of Klimt and Yang (2004); ``X-Origin:`` gives
  the mailbox owner.

The document text is the **raw message**, headers included, because that is what a deployed
de-identification system is handed and because it keeps offsets trivially correct.
"""

from __future__ import annotations

import email
import re
import tarfile
from collections import defaultdict
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

from ..domain import Corpus, Document, Mention, Span

__all__ = [
    "build_text",
    "strip_quoted",
    "load",
    "iter_raw_messages",
    "IdentityTable",
    "build_identity_table",
]

_ADDRESS_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_DISPLAY_RE = re.compile(r"([^<>,][^<>]*?)\s*<[^>]*>")
_NAME_OK = re.compile(r"^[A-Za-z][A-Za-z.'\- ]{1,48}(?:,\s*[A-Za-z][A-Za-z.'\- ]{0,24})?$")


@dataclass
class IdentityTable:
    """Display name -> e-mail address, learned from unambiguous sender pairs."""

    by_name: dict[str, str]
    counts: dict[str, int]

    def resolve(self, display_name: str) -> str | None:
        return self.by_name.get(display_name.strip().casefold())

    def names(self) -> list[str]:
        """Known display names, longest first so 'Bramble, Bo' is matched before 'Bramble'."""
        return sorted(self.by_name, key=len, reverse=True)


def iter_raw_messages(
    source: Path | str,
    limit: int | None = None,
    mailboxes: Sequence[str] | None = None,
    stride: int = 1,
) -> Iterator[tuple[str, str, str]]:
    """Stream ``(path, mailbox, raw_text)`` from the tarball or an extracted maildir.

    The tarball is read sequentially (``r|gz``) rather than extracted, so a 443 MB archive costs no
    disk and one pass.

    ``stride`` keeps every *n*-th message.  It matters: the archive is ordered by mailbox, so a bare
    ``limit`` samples the first few mailboxes and nothing else, which would concentrate the name
    distribution on a handful of people and flatter exactly the frequency-skew effect this corpus is
    meant to test.  Striding costs a full decompression pass and buys a sample spread across the
    whole corpus.
    """
    source = Path(source)
    keep = {m.casefold() for m in mailboxes} if mailboxes else None
    seen = 0
    scanned = 0

    def wanted(path: str) -> bool:
        parts = path.split("/")
        if len(parts) < 3:
            return False
        return keep is None or parts[1].casefold() in keep

    if source.is_dir():
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(source.parent).as_posix()
            if not wanted(rel):
                continue
            scanned += 1
            if (scanned - 1) % stride:
                continue
            yield rel, rel.split("/")[1], path.read_text("utf-8", errors="replace")
            seen += 1
            if limit and seen >= limit:
                return
        return

    with tarfile.open(source, mode="r|gz") as tar:
        for member in tar:
            if not member.isfile() or not wanted(member.name):
                continue
            scanned += 1
            if (scanned - 1) % stride:
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            yield member.name, member.name.split("/")[1], handle.read().decode(
                "utf-8", errors="replace"
            )
            seen += 1
            if limit and seen >= limit:
                return


def _sender_pair(message: Message) -> tuple[str, str] | None:
    """The one unambiguous name/address pair in a message: its sender."""
    address = (message.get("From") or "").strip().casefold()
    display = (message.get("X-From") or "").strip()
    if not address or not display or "@" not in address:
        return None
    display = _DISPLAY_RE.sub(r"\1", display).strip()
    if not _NAME_OK.match(display):
        return None
    return display, address


def build_identity_table(raw_messages: Iterable[str]) -> IdentityTable:
    """Learn display name -> address from sender pairs across the corpus."""
    votes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for raw in raw_messages:
        pair = _sender_pair(email.message_from_string(raw))
        if pair is None:
            continue
        display, address = pair
        votes[display.casefold()][address] += 1
    by_name = {name: max(addrs.items(), key=lambda kv: kv[1])[0] for name, addrs in votes.items()}
    counts = {name: sum(addrs.values()) for name, addrs in votes.items()}
    return IdentityTable(by_name=by_name, counts=counts)


ROLE_ACCOUNTS = frozenset("""
    admin administrator alerts announcements billing bounce contact customerservice documents
    enquiries feedback help helpdesk info information list listserv mail mailer mailing marketing
    members news newsletter noreply notifications offers orders postmaster questions reactions
    register registration reply reporting request sales service staff subscribe subscriptions
    support team unsubscribe updates webmaster weather
""".split())
"""Mailbox names that are a function, not a person.

Enron's identity table is learned from ``X-From`` display names, and a role mailbox supplies one:
``info@mesuite.com`` displays as *info*, ``questions@enron.com`` as *questions*. The name then
matches every occurrence of that ordinary English word in body prose. Anchoring the match (see
:func:`name_pattern`) does not help, because in *"if you have any questions"* the word really is
standing on its own.

The gazetteer test in :func:`is_person_name` removes most of these on its own, but not all: the US
Census surname list contains *News*, *Weather*, *Staff*, *Sales*, *Register*, *Orders* and *Mail*,
so those need naming. The list is deliberately generic rather than Enron-specific."""


def is_person_name(name: str, person_names: frozenset[str] | None) -> bool:
    """Is this display name usable as a person identity?

    Only single-token names are judged. A multi-part name -- *kay mann*, *vince j kaminski* -- is
    taken as a person without further question: role mailboxes do not present two-word human names,
    and the 2,138 multi-part Enron entities are all people.

    A single token has to clear three bars. It must not be a role word; it must not look like a
    domain; and it must appear in the person-name gazetteers, which is what separates *chris*,
    *dan*, *bob*, *beth* and *adam* from *esource*, *clickathome*, *microsoft* and *nytimes.com*.
    Two-character names are dropped as well: they carry no identity and invite collisions.
    """
    if " " in name or "," in name:
        return True
    if len(name) < 3 or "." in name or name in ROLE_ACCOUNTS:
        return False
    if person_names is None:
        return True
    # The Census edit rules fold O'HARA and O HARA into OHARA, so an apostrophe or hyphen in the
    # display name will never match the list as written. O'Brien is a person; test both forms.
    plain = name.replace("'", "").replace("\u2019", "").replace("-", "")
    return name in person_names or plain in person_names


def _person_name_gazetteer() -> frozenset[str] | None:
    """The surname and given-name lists, or ``None`` if they are not on this machine.

    Returning ``None`` degrades to the structural rules alone rather than silently keeping every
    role account, and the caller logs which happened.
    """
    try:
        from ..attacks.priors import load_census_surnames, load_uci_given_names
        from ..paths import shared_corpora

        root = shared_corpora() / "gazetteers"
        out = {n.casefold() for n in load_census_surnames(root / "Names_2010Census.csv")}
        out |= {n.casefold() for n in load_uci_given_names(root / "name_gender_dataset.csv")}
        return frozenset(out)
    except Exception:
        return None


_MATCHER: re.Pattern[str] | None = None
"""One alternation over every kept display name, compiled once in :func:`load`."""

_BOUNDARY_LEFT = r"(?<![\w.\-])"
_BOUNDARY_RIGHT = r"(?![\w\-])"
"""Wider than ``\\b`` on the left, narrower on the right.

A plain word boundary still matched *mail* inside ``e-mail`` and *mckay* inside ``brad.mckay``,
because ``-`` and ``.`` are not word characters.  The right side stays narrow so a name at the end
of a sentence -- ``Bob.`` -- is still found.
"""


def build_matcher(names: Sequence[str]) -> re.Pattern[str] | None:
    """One regex for all display names, longest alternative first.

    The first version of this fix compiled a pattern per name and scanned the document once per
    name: 8,696 patterns across 58,636 documents is half a billion ``finditer`` calls, and a rebuild
    that had taken minutes took over an hour.  A single alternation scans each document once.

    Ordering carries the semantics.  Python's ``|`` takes the first alternative that matches at a
    position, so listing names longest-first is what makes *Bramble, Bo* win over *Bramble* -- the
    same guarantee :meth:`IdentityTable.names` was already sorted to provide.
    """
    if not names:
        return None
    ordered = sorted(names, key=len, reverse=True)
    return re.compile(
        _BOUNDARY_LEFT + "(?:" + "|".join(re.escape(n) for n in ordered) + ")" + _BOUNDARY_RIGHT
    )


def name_pattern(name: str) -> re.Pattern[str]:
    """One name, anchored the same way.  Kept for tests and for callers matching a single name."""
    return re.compile(_BOUNDARY_LEFT + re.escape(name) + _BOUNDARY_RIGHT)


def _mentions(doc_id: str, text: str, table: IdentityTable, known: Sequence[str]) -> list[Mention]:
    """Find addresses and known display names in the raw message.

    Addresses are matched first and claim their span, so the local part of an address is not also
    reported as a name.  Names are tried longest first for the same reason.
    """
    taken: list[tuple[int, int]] = []
    found: list[Mention] = []

    def free(start: int, end: int) -> bool:
        return not any(start < e and s < end for s, e in taken)

    for match in _ADDRESS_RE.finditer(text):
        start, end = match.span()
        if not free(start, end):
            continue
        taken.append((start, end))
        address = match.group(0).casefold()
        found.append(
            # Harmonised name in ``type``, source label in ``type_src`` — the same shape every
            # other adapter emits.  Writing the raw label into ``type`` made ``span.type`` mean one
            # thing on TAB and another on Enron, so anything reading it without harmonising first
            # saw 445,560 spans typed EMAIL and none typed CODE (experiment_plan.md §10).
            Mention(doc_id, f"a{start}", Span(start, end, match.group(0), "CODE", type_src="EMAIL"),
                    gold_entity_id=address)
        )

    lowered = text.casefold()
    matcher = _MATCHER if _MATCHER is not None else build_matcher(known)
    if matcher is not None:
        for match in matcher.finditer(lowered):
            start, end = match.span()
            address = table.by_name.get(match.group(0))
            if address is None or not free(start, end):
                continue
            taken.append((start, end))
            found.append(
                Mention(doc_id, f"n{start}",
                        Span(start, end, text[start:end], "PERSON", type_src="PERSON"),
                        gold_entity_id=address)
            )

    found.sort(key=lambda m: (m.span.start, -m.span.length))
    return found


_QUOTE_MARKERS = (
    "-----Original Message-----",
    "-----Ursprüngliche Nachricht-----",
    "----- Forwarded by",
    "---------------------- Forwarded by",
    "__________________________________",
)

_KEEP_HEADERS = (
    ("From", "X-From"),
    ("To", "X-To"),
    ("Cc", "X-cc"),
    ("Subject", None),
)
"""The fields condition A keeps (AM, 2026-09-09): sender, recipients, names, addresses, subject.

Each pair is (address header, display-name header).  Both are kept because they carry different
things: ``From`` is an address and ``X-From`` is the human name, and the name is where the person
mentions live.  ``Bcc`` is not kept — it duplicates ``Cc`` byte for byte in every message of the
sample.  Nor are ``Message-ID``, ``Date``, ``X-FileName``, ``X-Origin`` or the MIME headers, which
are routing and archive artefacts rather than correspondence.

**``X-Folder`` is excluded deliberately.** It names the mailbox folder, which *is* the target of the
folder-classification task (§8.3).  Leaving it in the text would put the answer in the input.
"""


def strip_quoted(body: str) -> str:
    """Drop quoted replies and forwarded blocks, keeping only what this message contributed.

    Enron threads quote in full, so the same prose recurs across a chain and a naive corpus counts
    one sentence many times — the audit measured a majority of long-body character mass as duplicate.
    Two rules cover almost all of it: everything from a client's forwarding banner onwards, and any
    line the client marked with ``>``.
    """
    cut = len(body)
    for marker in _QUOTE_MARKERS:
        found = body.find(marker)
        if found != -1:
            cut = min(cut, found)
    kept = [line for line in body[:cut].splitlines() if not line.lstrip().startswith(">")]
    return "\n".join(kept).strip()


def _body(message: Message) -> str:
    """The plain-text body, taking one part of a multipart alternative rather than both."""
    if not message.is_multipart():
        payload = message.get_payload(decode=False)
        return payload if isinstance(payload, str) else ""
    plain = [part for part in message.walk()
             if part.get_content_type() == "text/plain" and not part.is_multipart()]
    chosen = plain[0] if plain else next(
        (part for part in message.walk() if not part.is_multipart()), None)
    if chosen is None:
        return ""
    payload = chosen.get_payload(decode=False)
    return payload if isinstance(payload, str) else ""


_X500 = re.compile(r"\s*</?O=[^>\n]{0,200}>")
"""Exchange distinguished names, as a mail client would never show them.

Every recipient appears three times in these headers: display name, X.500 DN, and address —
``Fairbairn, Finn </O=ENRON/OU=NA/CN=RECIPIENTS/CN=FFAIRBA>, finn.fairbairn@enron.com``.  Measured
over 4,000 documents: **3,883 DNs in the header block and 0 in the body**, 49,463 across the corpus.

The DN goes (AM, 2026-09-13).  It carries nothing the other two forms do not — ``CN=FFAIRBA`` is a
truncation of the same name — while contributing 49,463 highly regular strings that a detector will
learn instead of the task, and inflating the corpus's ``CODE`` count.  Display names stay in their
``Last, First`` form because that is the real surface a client shows and detecting a person in it is
part of the task; addresses stay because they are identifiers, they are what a client shows, and the
gold layer is built from them."""


def build_text(message: Message) -> str:
    """The document text for condition A: sender, recipients, names, addresses, subject, body.

    Constructed rather than taken raw.  A raw Enron message is largely archive metadata — the audit
    measured about a third of its characters as RFC-822 headers — and one of those headers is the
    label of a task the study scores, so the raw message cannot be the document text.

    The headers are kept in the reduced form a mail client shows: display name and address, without
    the Exchange routing internals (see :data:`_X500`).
    """
    lines: list[str] = []
    for address_header, name_header in _KEEP_HEADERS:
        address = _X500.sub("", (message.get(address_header) or "")).strip()
        name = _X500.sub("", (message.get(name_header) or "")).strip() if name_header else ""
        name = _tidy(name)
        address = _tidy(address)
        value = ", ".join(v for v in (name, address) if v) if name and name != address else (
            name or address)
        if value:
            lines.append(f"{address_header}: {value}")
    body = strip_quoted(_body(message))
    return "\n".join(lines) + ("\n\n" + body if body else "\n")


def _tidy(value: str) -> str:
    """Repair the separators that removing a DN leaves behind — ``a, , b`` and a trailing comma."""
    value = re.sub(r",\s*(?=,)", "", value)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip().strip(",").strip()


def load(
    source: Path | str,
    limit: int | None = None,
    mailboxes: Sequence[str] | None = None,
    identity_table: IdentityTable | None = None,
    min_name_count: int = 2,
    stride: int = 1,
    require_body: bool = True,
    progress: Callable[[str], None] | None = None,
) -> Corpus:
    """Build a corpus from the tarball or an extracted maildir.

    Two passes over the messages: the first learns the identity table from sender pairs, the second
    emits documents.  ``min_name_count`` drops display names seen only once, which are usually
    parsing debris rather than people.

    ``require_body`` drops messages that carry no prose once quoting is stripped (AM, 2026-09-10).
    They are a real part of an e-mail archive — a forward with nothing added — but they cannot be
    scored on any utility task, and they would enter every condition as an empty document.  The
    identity table is built **before** the filter, so a name that appears only in such a message
    still counts towards the corpus's identities.
    """
    # One decompression pass, held in memory.  An earlier version made two passes to halve peak
    # memory after being OOM-killed -- but the kill happened on the *login node*, whose per-user
    # limit is small, not because 20,000 messages are large: they are about 100 MB, trivial inside a
    # 48 GB Slurm allocation.  The second pass cost a full re-decompression of a 443 MB archive on a
    # contended NFS mount and bought nothing.  Run this under sbatch, not on the head node.
    raws = list(iter_raw_messages(source, limit, mailboxes, stride))
    if progress:
        progress(f"read {len(raws)} messages")
    table = identity_table or build_identity_table(r for _, _, r in raws)
    frequent = [n for n in table.names() if table.counts.get(n, 0) >= min_name_count]
    gazetteer = _person_name_gazetteer()
    known = [n for n in frequent if is_person_name(n, gazetteer)]
    if progress:
        progress(
            f"display names: {len(frequent)} seen at least {min_name_count}x, "
            f"{len(known)} kept as people, {len(frequent) - len(known)} dropped as role accounts"
            + ("" if gazetteer else " (no gazetteer on this machine: structural rules only)")
        )
    # Compiled once, as one alternation: a pattern per name made this a half-billion-call scan.
    global _MATCHER
    _MATCHER = build_matcher(known)
    if progress:
        progress(f"identity table: {len(table.by_name)} names, {len(known)} above threshold")

    documents: list[Document] = []
    bodyless = 0
    for path, mailbox, raw in raws:
        message = email.message_from_string(raw)
        folder = (message.get("X-Folder") or "").replace("\\", "/").rstrip("/").split("/")[-1]
        text = build_text(message)
        if require_body and not text.split("\n\n", 1)[-1].strip() or (
                require_body and "\n\n" not in text):
            # A message that quoted a thread and added nothing carries sender, recipients and
            # subject but no prose (AM, 2026-09-10). It is excluded: a utility task cannot be
            # scored on it, and keeping it would put empty documents in every condition.
            bodyless += 1
            continue
        documents.append(
            Document(
                doc_id=path,
                text=text,
                language="en",
                mentions=tuple(_mentions(path, text, table, known)),
                corpus="enron",
                domain="email",
                provenance="real",
                subject_id=(message.get("X-Origin") or mailbox).strip().casefold(),
                task={"name": "enron_folder", "label": folder or "unfiled"},
                metadata={
                    "annotation": "structural",
                    "mailbox": mailbox,
                    "message_id": message.get("Message-ID"),
                    "date": message.get("Date"),
                },
            )
        )
    if progress:
        mentions = sum(len(d.mentions) for d in documents)
        progress(f"built {len(documents)} documents, {mentions} mentions")
    return Corpus("enron", tuple(documents))
