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
from typing import Iterable, Iterator, Sequence

from ..domain import Corpus, Document, Mention, Span

__all__ = ["load", "iter_raw_messages", "IdentityTable", "build_identity_table"]

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


def load(
    source: Path | str,
    limit: int | None = None,
    mailboxes: Sequence[str] | None = None,
    identity_table: IdentityTable | None = None,
    min_name_count: int = 2,
    stride: int = 1,
) -> Corpus:
    """Build a corpus from the tarball or an extracted maildir.

    Two passes over the messages: the first learns the identity table from sender pairs, the second
    emits documents.  ``min_name_count`` drops display names seen only once, which are usually
    parsing debris rather than people.
    """
    # Two streaming passes rather than one pass into a list.  Holding every raw message *and* the
    # Document that wraps it doubles peak memory for no benefit, and on 20,000 messages that was
    # enough to be OOM-killed.  A second decompression pass is the cheaper resource.
    if identity_table is None:
        table = build_identity_table(
            r for _, _, r in iter_raw_messages(source, limit, mailboxes, stride)
        )
    else:
        table = identity_table
    known = [n for n in table.names() if table.counts.get(n, 0) >= min_name_count]

    documents: list[Document] = []
    for path, mailbox, raw in iter_raw_messages(source, limit, mailboxes, stride):
        message = email.message_from_string(raw)
        folder = (message.get("X-Folder") or "").replace("\\", "/").rstrip("/").split("/")[-1]
        documents.append(
            Document(
                doc_id=path,
                text=raw,
                language="en",
                mentions=tuple(_mentions(path, raw, table, known)),
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
    return Corpus("enron", tuple(documents))
