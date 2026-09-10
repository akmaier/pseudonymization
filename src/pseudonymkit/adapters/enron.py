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
* **The address is a cross-document identity.**  ``jeff.skilling@enron.com`` is the same person in
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
        """Known display names, longest first so 'Blair, Lynn' is matched before 'Blair'."""
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
            Mention(doc_id, f"a{start}", Span(start, end, match.group(0), "EMAIL"),
                    gold_entity_id=address)
        )

    lowered = text.casefold()
    for name in known:
        address = table.by_name[name]
        start = lowered.find(name)
        while start >= 0:
            end = start + len(name)
            if free(start, end):
                taken.append((start, end))
                found.append(
                    Mention(doc_id, f"n{start}", Span(start, end, text[start:end], "PERSON"),
                            gold_entity_id=address)
                )
            start = lowered.find(name, start + 1)

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


def build_text(message: Message) -> str:
    """The document text for condition A: sender, recipients, names, addresses, subject, body.

    Constructed rather than taken raw.  A raw Enron message is largely archive metadata — the audit
    measured about a third of its characters as RFC-822 headers — and one of those headers is the
    label of a task the study scores, so the raw message cannot be the document text.
    """
    lines: list[str] = []
    for address_header, name_header in _KEEP_HEADERS:
        address = (message.get(address_header) or "").strip()
        name = (message.get(name_header) or "").strip() if name_header else ""
        value = ", ".join(v for v in (name, address) if v) if name and name != address else (
            name or address)
        if value:
            lines.append(f"{address_header}: {value}")
    body = strip_quoted(_body(message))
    return "\n".join(lines) + ("\n\n" + body if body else "\n")


def load(
    source: Path | str,
    limit: int | None = None,
    mailboxes: Sequence[str] | None = None,
    identity_table: IdentityTable | None = None,
    min_name_count: int = 2,
    stride: int = 1,
    progress: Callable[[str], None] | None = None,
) -> Corpus:
    """Build a corpus from the tarball or an extracted maildir.

    Two passes over the messages: the first learns the identity table from sender pairs, the second
    emits documents.  ``min_name_count`` drops display names seen only once, which are usually
    parsing debris rather than people.
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
    known = [n for n in table.names() if table.counts.get(n, 0) >= min_name_count]
    if progress:
        progress(f"identity table: {len(table.by_name)} names, {len(known)} above threshold")

    documents: list[Document] = []
    for path, mailbox, raw in raws:
        message = email.message_from_string(raw)
        folder = (message.get("X-Folder") or "").replace("\\", "/").rstrip("/").split("/")[-1]
        text = build_text(message)
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
