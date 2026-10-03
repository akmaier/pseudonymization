"""Adapter helpers for ENRON 2.0 — body and subject only, deduplicated, CARDIO:DE-sized.

**Why a second Enron** (AM, 2026-10-03). Three measurements on the paper-1 artefact
(``enron_A.jsonl.gz``, 58,636 messages) made it unusable for the second paper:

* **It is mostly copies.** Only 23,649 bodies are distinct, and 49,795 messages (84.9 %) share their
  body with a message filed under a *different* folder — Lotus Notes keeps one mail under
  ``All documents``, ``Discussion threads`` and ``Sent`` at once. A folder label is therefore not a
  property of the text.
* **Its attack split leaks.** The A3/A5 split is by document id, so 66.8 % of query-half messages
  have a verbatim copy in the reference half: the attack can match the copy instead of the person.
* **Its identifiers are mostly header.** 75.3 % of the PERSON gold-standard tokens sit in the From/To/Cc
  block, which a deployed system parses and replaces deterministically. A detector benchmark gains
  nothing from them, and they made the PERSON statistics a measurement of header parsing.

**AM's decisions of 2026-10-03, which this module implements:**

1. From, To and Cc leave the document text. **The Subject stays** (AM: *"Drop Subject as well?
   No"*), as the first line, in the form a mail client shows it.
2. Header blocks embedded in a body — a quoted original, a forwarded memo, a pasted SMTP dump — are
   stripped by the same logic: they are structured, parseable, and replaced the same way.
3. Bodies are deduplicated across folders *and* mailboxes, and near-duplicates are removed, so
   every split of the corpus is content-disjoint by construction.
4. The draw is from all 150 mailboxes with a per-mailbox cap, to CARDIO:DE's token count.
5. **The gold standard is header-informed.** The header is parsed, kept out of the text, and used to resolve
   the names in the body: in a message between two people, a bare first name in the sign-off belongs
   to one of *them*. The paper-1 gold standard could only credit a body name that exactly matched some
   sender's whole display name, so a sign-off entered the gold standard only if someone's ``X-From`` was literally
   that first name — and then every such first name in the corpus went to that one address.
6. No utility task is attached: folder classification is dropped for this corpus, and §4 already
   gives utility to CARDIO:DE.

The paper-1 adapter (:mod:`.enron`) is not changed in any way. Paper 1 stays reproducible on its
own corpus; this one gets its own id, ``enron2``, and its own files.

**No real name appears in this module or its tests** (``experiment_plan.md`` §15, safeguard 1):
every example is invented.
"""

from __future__ import annotations

import email.utils
import hashlib
import quopri
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from email.message import Message
from typing import Callable, Iterable, Mapping, Sequence

from ..domain import Mention, Span
from .enron import (
    _ADDRESS_RE,
    _BOUNDARY_LEFT,
    _BOUNDARY_RIGHT,
    ROLE_ACCOUNTS,
    IdentityTable,
    is_person_name,
    strip_quoted,
)

__all__ = [
    "GOLD_RULES",
    "NameIndex",
    "ShingleIndex",
    "Unit",
    "clean_body",
    "decoded_body",
    "dedup_key",
    "document_text",
    "draw",
    "find_mentions",
    "local_part_name",
    "name_forms",
    "plausible_full_name",
    "participants",
    "shingles",
    "strip_embedded",
    "thread_key",
]


# ------------------------------------------------------------------------------- body cleaning

QUOTE_LINE = re.compile(
    r"^\s*(?:-{2,}\s*(?:original message|ursprüngliche nachricht|forwarded message)\s*-{2,}"
    r"|-{2,}\s*forwarded by\b"
    r"|begin forwarded message\s*:"
    r"|on\b.{4,120}\bwrote\s*:\s*$)",
    re.IGNORECASE,
)
"""Quote markers the paper-1 list misses because it matches them literally.

``strip_quoted`` looks for ``-----Original Message-----`` exactly; Outlook Express writes
``----- Original Message -----``, with spaces, and that variant survived into the paper-1 bodies.
Matched per line and case-insensitively here, after ``strip_quoted`` has run."""

HEADER_LINE = re.compile(
    r"^\s*(to|cc|bcc|from|sent|sent by|date|subject|reply-to|message-id|received|mime-version|"
    r"content-type|content-transfer-encoding|importance|x-[a-z0-9-]+)\s*:",
    re.IGNORECASE,
)
"""A line that opens a header field. One such line in prose is ordinary — *"Date: Tuesday"* in a
meeting note — so a block needs at least two distinct fields close together (:data:`WINDOW`)."""

WINDOW = 6
"""Lines within which two distinct header fields make a block. Measured on the paper-1 bodies, the
dominant embedded shapes are ``To/cc/Subject`` (Lotus Notes, 8,953 bodies) and
``From/To/cc/Subject`` (2,649), both of which fit in six lines including a wrapped recipient list."""

NOTES_STAMP = re.compile(
    r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AP]M)?\s*$", re.IGNORECASE)
"""The date line Lotus Notes puts above a quoted original: ``12/14/2000 10:22 AM``. The line above
*that* is the original sender's name, which is a header field in all but layout."""


def _name_line(line: str) -> bool:
    """Could this line be the sender's name above a Notes stamp? Short, no field, no sentence."""
    stripped = line.strip()
    if not stripped or ":" in stripped or len(stripped) > 60:
        return False
    if stripped[-1] in ".!?,;":
        return False
    return 1 <= len(stripped.split()) <= 6


def _block_keys(lines: Sequence[str], start: int) -> set[str]:
    keys = set()
    for line in lines[start:start + WINDOW]:
        match = HEADER_LINE.match(line)
        if match:
            keys.add(match.group(1).casefold())
    return keys


def strip_embedded(body: str) -> str:
    """Remove header blocks and quote markers that ``strip_quoted`` does not see.

    Two cases, because a block means different things in different places:

    * **Below some prose**, a block opens quoted history — what was replied to or forwarded — and
      everything from it onwards is cut, exactly as ``strip_quoted`` cuts at a forwarding banner.
      A Notes stamp and the sender's name directly above it are cut with it.
    * **At the top of the body**, with no prose above, it is a forwarded memo's own header: the
      block is dropped up to the next blank line and the memo below it is kept. Cutting there would
      empty the message.
    """
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if QUOTE_LINE.match(line):
            lines = lines[:index]
            break

    index = 0
    while index < len(lines):
        if not HEADER_LINE.match(lines[index]) or len(_block_keys(lines, index)) < 2:
            index += 1
            continue
        if not any(line.strip() for line in lines[:index]):
            end = index
            while end < len(lines) and lines[end].strip():
                end += 1
            lines = lines[end:]
            index = 0
            continue
        start = index
        if start >= 1 and NOTES_STAMP.match(lines[start - 1]):
            start -= 1
            if start >= 1 and _name_line(lines[start - 1]):
                start -= 1
        lines = lines[:start]
        break
    return "\n".join(lines).strip()


_SOFT_BREAK = re.compile(r"=\r?\n")


def _text_part(message: Message) -> Message | None:
    """The part the paper-1 extractor reads: the first plain-text leaf, else the first leaf."""
    if not message.is_multipart():
        return message
    plain = [part for part in message.walk()
             if part.get_content_type() == "text/plain" and not part.is_multipart()]
    return plain[0] if plain else next(
        (part for part in message.walk() if not part.is_multipart()), None)


def decoded_body(message: Message) -> str:
    """The body as a mail client shows it — quoted-printable decoded.

    The paper-1 extractor reads payloads undecoded, and 5.8 % of messages (measured 2026-10-03 on
    every tenth message of the archive) still carry quoted-printable debris: soft line breaks that
    split a word across lines (``talking=``/``about``) and escapes such as ``=20`` and ``=3D``.
    Only 4.4 % declare ``quoted-printable``; the rest say ``7bit`` and were left encoded by the
    archive's export, so a soft line break in the text is taken as evidence too. A plain body with
    neither is returned exactly as read.
    """
    part = _text_part(message)
    if part is None:
        return ""
    raw = part.get_payload(decode=False)
    if not isinstance(raw, str):
        return ""
    declared = (part.get("Content-Transfer-Encoding") or "").strip().casefold()
    if declared != "quoted-printable" and not _SOFT_BREAK.search(raw):
        return raw
    data = quopri.decodestring(raw.encode("latin-1", errors="replace"))
    for charset in (part.get_content_charset(), "cp1252", "latin-1"):
        if not charset:
            continue
        try:
            return data.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw


def clean_body(body: str) -> str:
    """The paper-1 quote stripping, then the embedded blocks it misses."""
    return strip_embedded(strip_quoted(body))


def dedup_key(body: str) -> str:
    """Identity of a body for deduplication: the text with whitespace runs collapsed."""
    return hashlib.sha1(" ".join(body.split()).encode("utf-8")).hexdigest()


_PREFIX = re.compile(r"^\s*(?:(?:re|fw|fwd|aw|wg|antw)\s*(?:\[\d+\])?\s*:\s*)+", re.IGNORECASE)


def thread_key(subject: str | None) -> str | None:
    """The subject without reply and forward prefixes, case- and space-folded. ``None`` if empty."""
    key = " ".join(_PREFIX.sub("", subject or "").casefold().split())
    return key or None


def document_text(subject: str | None, body: str) -> str:
    """Condition A for ENRON 2.0: the subject line, a blank line, the body.

    The ``Subject:`` label is kept so the line reads as what it is, and the blank line keeps the
    paper-1 convention that the first ``\\n\\n`` separates the head from the body.
    """
    return f"Subject: {' '.join((subject or '').split())}\n\n{body}"


# ------------------------------------------------------------------------------------- names

_TOKEN = re.compile(r"[^\W\d_][^\W\d_'\-]*", re.UNICODE)


def _reorder(display: str) -> str:
    """``Last, First M`` → ``First M Last``; anything else unchanged."""
    written = " ".join(display.split()).strip().strip("\"'")
    if "," in written:
        last, _, rest = written.partition(",")
        return f"{rest.strip()} {last.strip()}"
    return written


def name_forms(display: str) -> tuple[frozenset[str], frozenset[str]]:
    """``(multi-token forms, single-token forms)`` of one display name, casefolded.

    ``Last, First M`` is reordered to ``First M Last`` before the parts are read, single-letter
    tokens (middle initials) are dropped, and the forms a body actually uses are generated:
    *first last*, *last, first*, the name as written, and — as single tokens — the first and last
    name. Single tokens shorter than three letters are not produced; they carry no identity.
    """
    written = " ".join(display.split()).strip().strip("\"'")
    if not written or "@" in written:
        return frozenset(), frozenset()
    ordered = _reorder(written)
    tokens = [t for t in _TOKEN.findall(ordered.casefold()) if len(t) > 1]
    multi: set[str] = set()
    single: set[str] = set()
    if len(tokens) >= 2:
        first, last = tokens[0], tokens[-1]
        multi |= {f"{first} {last}", f"{last}, {first}", " ".join(tokens),
                  _canonical(written.casefold())}
        single |= {t for t in (first, last) if len(t) >= 3}
    elif len(tokens) == 1 and len(tokens[0]) >= 3:
        single.add(tokens[0])
    return frozenset(multi), frozenset(single)


def _canonical(surface: str) -> str:
    """Case-, space- and comma-folded form, so a matched surface finds its form."""
    folded = " ".join(surface.casefold().split())
    return re.sub(r"\s*,\s*", ", ", folded)


def local_part_name(address: str, gazetteer: frozenset[str] | None) -> str | None:
    """``first.last@…`` → ``first last``, when both parts are names; otherwise ``None``.

    Recipients who never sent a message have no display name in the identity table, and for them
    the address is the only evidence of a name. Only the two-part dotted or underscored form is
    read, and both parts must be in the person-name gazetteers when those are available, so
    ``market.news@…`` and ``jsmith@…`` yield nothing rather than a guess.
    """
    local = address.split("@", 1)[0].casefold()
    parts = re.split(r"[._]", local)
    if len(parts) != 2 or not all(p.isalpha() and len(p) >= 2 for p in parts):
        return None
    if any(p in ROLE_ACCOUNTS for p in parts):
        return None
    if gazetteer is not None and not all(p in gazetteer for p in parts):
        return None
    return f"{parts[0]} {parts[1]}"


def participants(message: Message) -> tuple[str, ...]:
    """Every address on the envelope — From, To, Cc, Bcc — casefolded, sorted, unique."""
    fields: list[str] = []
    for name in ("From", "To", "Cc", "Bcc"):
        fields.extend(str(v) for v in (message.get_all(name) or []))
    found = {addr.strip().casefold() for _, addr in email.utils.getaddresses(fields)
             if "@" in addr}
    return tuple(sorted(found))


GOLD_RULES: Mapping[str, str] = {
    "a": "address",
    "p": "participant full name",
    "n": "known full name, not a participant",
    "f": "participant first or last name",
    "g": "known single name, not a participant",
}
"""How each gold-standard mention was found, stored as the mention-id prefix and in ``attributes``.

Kept per mention so the validation sample can measure each rule's precision on its own: the
participant rules are the new evidence, and the two non-participant rules are the paper-1 behaviour
carried over, the second of them without an identity."""

WORD_NAMES = frozenset("""
    will may mark bill pat rich art june april august grant rose don ray gene frank joy hope faith
    chase page dean earl guy jack sue drew dawn summer major price young long white brown green
    hunter lane case cash miles wade chip buck rob sandy penny holly ivy iris ruby crystal amber
    jade autumn misty rusty sunny star angel max gray grey west north south best bell hill wood
    rock stone ford love gale glen heath cliff bud rocky wolf fox gay king
""".split())
"""Given names that are also frequent English words. A bare capitalised *Will* or *Mark* opens
sentences as often as it names someone, so rule ``g`` — a single name with no participant behind it
— does not fire on these. Rule ``f`` still does: inside a message to or from a *Mark*, the bare
*Mark* is most likely him, and the validation sample is what measures how often that is wrong."""


ORG_WORDS = frozenset("""
    enron office department dept team group desk services service announcement announcements
    resources center centre committee council corp corporation inc llc ltd company association
    communications news update updates alert alerts admin administrator help support staff
    management operations information info chairman board network systems technology
""".split())
"""Words that make a multi-word display name an organisation, not a person.

The paper-1 rule takes every multi-token display name as a person, on a measurement over its 15
mailboxes ("the 2,138 multi-part Enron entities are all people"). Drawn from all 150, the identity
table also holds senders like *Office of the Chairman* or *Human Resources*, and a gold standard that credits
those as PERSON would punish every detector that correctly leaves them alone."""


def plausible_full_name(tokens: Sequence[str], given: frozenset[str] | None,
                        surnames: frozenset[str] | None) -> bool:
    """A multi-token name is a person if no token is an organisational word and either the first
    token is a known given name or the last a known surname. Without gazetteers only the first test
    applies."""
    if len(tokens) < 2 or any(t in ORG_WORDS or t in ROLE_ACCOUNTS for t in tokens):
        return False
    if given is None and surnames is None:
        return True
    return bool((given and tokens[0] in given) or (surnames and tokens[-1] in surnames))


def _pattern(forms: Iterable[str]) -> re.Pattern[str] | None:
    """One case-insensitive alternation, longest first, tolerant of spacing around commas."""
    ordered = sorted(set(forms), key=len, reverse=True)
    if not ordered:
        return None
    pieces = []
    for form in ordered:
        piece = re.escape(form)
        piece = piece.replace(r",\ ", r",\s*").replace(r"\ ", r"\s+")
        pieces.append(piece)
    return re.compile(_BOUNDARY_LEFT + "(?:" + "|".join(pieces) + ")" + _BOUNDARY_RIGHT,
                      re.IGNORECASE)


@dataclass
class NameIndex:
    """The corpus-wide name evidence, built once from the identity table of all 517,401 messages.

    ``address_forms`` is the reverse of the identity table — every display name a sender used,
    turned into forms — and is what a message's participants are looked up in. ``multi`` and
    ``single`` are the paper-1 matcher's names, kept for people mentioned in a body who are not on
    that message's envelope.
    """

    address_forms: dict[str, tuple[frozenset[str], frozenset[str]]]
    multi: dict[str, str | None]
    single: frozenset[str]
    gazetteer: frozenset[str] | None = None
    _multi_pattern: re.Pattern[str] | None = field(default=None, repr=False)
    _single_pattern: re.Pattern[str] | None = field(default=None, repr=False)

    @classmethod
    def build(cls, table: IdentityTable, *, min_name_count: int = 2,
              gazetteer: frozenset[str] | None = None, given: frozenset[str] | None = None,
              surnames: frozenset[str] | None = None) -> "NameIndex":
        address_multi: dict[str, set[str]] = defaultdict(set)
        address_single: dict[str, set[str]] = defaultdict(set)
        multi_owner: dict[str, set[str]] = defaultdict(set)
        single: set[str] = set()
        for name, address in table.by_name.items():
            if table.counts.get(name, 0) < min_name_count or not is_person_name(name, gazetteer):
                continue
            many, one = name_forms(name)
            if many:
                reordered = [t for t in _TOKEN.findall(_reorder(name).casefold()) if len(t) > 1]
                if not plausible_full_name(reordered, given, surnames):
                    continue
            address_multi[address] |= many
            address_single[address] |= {t for t in one
                                        if gazetteer is None or t in gazetteer}
            for form in many:
                multi_owner[form].add(address)
            if not many and one:
                single |= one
        # A full form shared by two addresses names nobody in particular: it stays a PERSON
        # mention, with no identity, rather than being credited to whichever won the vote.
        multi = {form: (next(iter(owners)) if len(owners) == 1 else None)
                 for form, owners in multi_owner.items()}
        forms = {a: (frozenset(address_multi[a]), frozenset(address_single[a]))
                 for a in set(address_multi) | set(address_single)}
        return cls(address_forms=forms, multi=multi, single=frozenset(single),
                   gazetteer=gazetteer)

    def forms_of(self, address: str) -> tuple[frozenset[str], frozenset[str]]:
        many, one = self.address_forms.get(address, (frozenset(), frozenset()))
        derived = local_part_name(address, self.gazetteer)
        if derived:
            more_many, more_one = name_forms(derived)
            many, one = many | more_many, one | more_one
        return many, one

    @property
    def multi_pattern(self) -> re.Pattern[str] | None:
        if self._multi_pattern is None and self.multi:
            self._multi_pattern = _pattern(self.multi)
        return self._multi_pattern

    @property
    def single_pattern(self) -> re.Pattern[str] | None:
        if self._single_pattern is None and self.single:
            self._single_pattern = _pattern(self.single)
        return self._single_pattern


def find_mentions(doc_id: str, text: str, envelope: Sequence[str],
                  index: NameIndex) -> list[Mention]:
    """Gold PERSON and address mentions for one document, header-informed.

    Precedence, which is also the order the spans are claimed in: addresses; full names, longest
    first, a participant's form beating a corpus form of equal length; then bare first or last
    names, a participant's beating a corpus one. Bare names must be capitalised in the text —
    lower-case *will* and *mark* are words — and a bare name two participants share stays a PERSON
    mention with no identity, because the text alone does not say which of them it is.
    """
    taken: list[tuple[int, int]] = []
    found: list[Mention] = []

    def free(start: int, end: int) -> bool:
        return not any(start < e and s < end for s, e in taken)

    def claim(start: int, end: int, rule: str, kind: str, entity: str | None) -> None:
        taken.append((start, end))
        span = Span(start, end, text[start:end], kind,
                    type_src="EMAIL" if kind == "CODE" else "PERSON")
        found.append(Mention(doc_id, f"{rule}{start}", span, gold_entity_id=entity,
                             attributes={"gold_rule": GOLD_RULES[rule]}))

    for match in _ADDRESS_RE.finditer(text):
        if free(*match.span()):
            claim(match.start(), match.end(), "a", "CODE", match.group(0).casefold())

    local_multi: dict[str, set[str]] = defaultdict(set)
    local_single: dict[str, set[str]] = defaultdict(set)
    for address in envelope:
        many, one = index.forms_of(address)
        for form in many:
            local_multi[form].add(address)
        for form in one:
            local_single[form].add(address)

    def owner(owners: set[str]) -> str | None:
        return next(iter(owners)) if len(owners) == 1 else None

    candidates: list[tuple[int, int, int, str, str | None]] = []
    pattern = _pattern(local_multi)
    if pattern is not None:
        for m in pattern.finditer(text):
            candidates.append((m.start(), m.end(), 0, "p",
                               owner(local_multi.get(_canonical(m.group(0)), set()))))
    if index.multi_pattern is not None:
        for m in index.multi_pattern.finditer(text):
            candidates.append((m.start(), m.end(), 1, "n", index.multi.get(_canonical(m.group(0)))))
    for start, end, _, rule, entity in sorted(candidates, key=lambda c: (c[0] - c[1], c[2], c[0])):
        if free(start, end):
            claim(start, end, rule, "PERSON", entity)

    singles: list[tuple[int, int, int, str, str | None]] = []
    pattern = _pattern(local_single)
    if pattern is not None:
        for m in pattern.finditer(text):
            if text[m.start()].isupper():
                singles.append((m.start(), m.end(), 0, "f",
                                owner(local_single.get(m.group(0).casefold(), set()))))
    if index.single_pattern is not None:
        for m in index.single_pattern.finditer(text):
            token = m.group(0).casefold()
            if text[m.start()].isupper() and token not in WORD_NAMES and token not in local_single:
                singles.append((m.start(), m.end(), 1, "g", None))
    for start, end, _, rule, entity in sorted(singles, key=lambda c: (c[0] - c[1], c[2], c[0])):
        if free(start, end):
            claim(start, end, rule, "PERSON", entity)

    found.sort(key=lambda m: (m.span.start, -m.span.length))
    return found


# ------------------------------------------------------------------------- near-duplicates

def _stable_hash(text: str) -> int:
    """Process-independent: Python's own ``hash`` is salted per run and would change the draw."""
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest(), "big")


def shingles(body: str, n: int = 5) -> frozenset[int]:
    """Word ``n``-gram shingles of a body, casefolded. Empty for a body shorter than ``n`` words —
    exact deduplication already covers those."""
    words = re.findall(r"\w+", body.casefold())
    if len(words) < n:
        return frozenset()
    return frozenset(_stable_hash(" ".join(words[i:i + n])) for i in range(len(words) - n + 1))


@dataclass
class ShingleIndex:
    """Near-duplicate test against everything accepted so far.

    Two criteria, because they catch different copies. **Jaccard** catches two versions of one
    message that differ by a few words. **Containment** catches the commonest Enron case: the same
    text with a line added above it. Containment is applied only when both bodies have at least
    ``min_for_containment`` shingles, because a short stock phrase — *let me know if you have any
    questions* — is contained in thousands of longer messages without being a copy of any of them.
    """

    jaccard: float = 0.8
    containment: float = 0.9
    min_for_containment: int = 10
    _sizes: list[int] = field(default_factory=list)
    _postings: dict[int, list[int]] = field(default_factory=dict)

    def is_near(self, shingle_set: frozenset[int]) -> bool:
        if not shingle_set:
            return False
        overlap = Counter(j for h in shingle_set for j in self._postings.get(h, ()))
        size = len(shingle_set)
        for j, shared in overlap.items():
            other = self._sizes[j]
            if shared / (size + other - shared) >= self.jaccard:
                return True
            smaller = min(size, other)
            if smaller >= self.min_for_containment and shared / smaller >= self.containment:
                return True
        return False

    def add(self, shingle_set: frozenset[int]) -> None:
        j = len(self._sizes)
        self._sizes.append(len(shingle_set))
        for h in shingle_set:
            self._postings.setdefault(h, []).append(j)


# ------------------------------------------------------------------------------------ the draw

@dataclass(frozen=True)
class Unit:
    """The sampling unit: one thread inside one mailbox, or one message if it has no subject.

    Whole threads are drawn so people recur — the attack curve needs a person in more than one
    document. A thread is identified by its folded subject (:func:`thread_key`) within a mailbox.
    """

    mailbox: str
    thread: str
    members: tuple[str, ...]


def draw(units: Sequence[Unit], tokens: Mapping[str, int], body: Callable[[str], str], *,
         budget: int, cap_fraction: float, seed: int,
         near: ShingleIndex | None = None) -> tuple[list[str], dict[str, object]]:
    """Seeded draw of whole units to ``budget`` tokens, no mailbox above ``cap_fraction`` of it.

    Units are visited in a seeded shuffle of their sorted order, so the result depends on the seed
    and the corpus and never on the order the archive was read in. Inside a unit each message is
    tested against everything accepted so far, including its own thread, and a near-duplicate is
    skipped. A unit whose surviving messages would take its mailbox over the cap is skipped whole.
    The draw stops at the first unit that reaches the budget, so it overshoots by less than one
    thread.
    """
    near = near or ShingleIndex()
    cap = int(budget * cap_fraction)
    order = sorted(units, key=lambda u: (u.mailbox, u.thread, u.members))
    random.Random(seed).shuffle(order)
    used: Counter[str] = Counter()
    accepted: list[str] = []
    total = 0
    stats: Counter[str] = Counter()
    for unit in order:
        if total >= budget:
            break
        stats["units_considered"] += 1
        kept: list[tuple[str, frozenset[int]]] = []
        dropped = 0
        staged = ShingleIndex(near.jaccard, near.containment, near.min_for_containment)
        for key in unit.members:
            sh = shingles(body(key))
            if near.is_near(sh) or staged.is_near(sh):
                dropped += 1
                continue
            staged.add(sh)
            kept.append((key, sh))
        if not kept:
            stats["units_entirely_near_duplicate"] += 1
            stats["messages_near_duplicate"] += dropped
            continue
        size = sum(tokens[key] for key, _ in kept)
        if used[unit.mailbox] + size > cap:
            # Counted as a cap decision only: a near-duplicate inside a unit that was skipped
            # anyway decided nothing, and counting it inflated the figure in the first smoke run.
            stats["units_over_mailbox_cap"] += 1
            continue
        for key, sh in kept:
            near.add(sh)
            accepted.append(key)
        stats["messages_near_duplicate"] += dropped
        used[unit.mailbox] += size
        total += size
        stats["units_accepted"] += 1
    stats_out: dict[str, object] = dict(stats)
    stats_out.update(tokens=total, budget=budget, cap_tokens=cap, mailboxes=len(used),
                     largest_mailbox_tokens=max(used.values()) if used else 0)
    return accepted, stats_out
