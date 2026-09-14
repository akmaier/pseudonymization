"""Adapter: OntoNotes 5.0 (LDC2013T19) -> the domain model.

OntoNotes is the only member of the meta corpus that supplies **real names, co-reference and
non-Latin script** at once — English, Chinese and Arabic across news, broadcast, weblog, telephone
speech and usenet.  It is why the study can say anything at all about scripts where the 2026
evaluations report detector collapse (Arabic F1 0.04).

The release stores one directory per document with parallel annotation layers.  Two matter here:

* ``.name`` — inline SGML, ``<ENAMEX TYPE="PERSON">Quentin Quill</ENAMEX>``, over the sentence
  stream.  Gives the text and the typed spans.
* ``.coref`` — the same stream marked with ``<COREF ID="…">``.  Gives the chains the stability
  metrics need.

They are separate files over the same tokenisation, so the adapter builds the document from
``.name`` and maps ``.coref`` onto it **only when the two strip to identical text**.  Where they do
not, co-reference is dropped for that document and counted, rather than aligned by guesswork — a
mis-aligned chain would corrupt exactly the metric OntoNotes was included to support.
"""

from __future__ import annotations

import difflib
import html
import re
import tarfile
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterator, Sequence

from ..domain import Corpus, Document, Mention, Span

__all__ = ["extract", "load", "parse_name", "parse_coref", "LoadReport", "map_coref_onto_name", "GENRES", "TYPE_MAP"]

TYPE_MAP: dict[str, str] = {
    "PERSON": "PERSON",
    "GPE": "LOC",
    "LOC": "LOC",
    "FAC": "LOC",
    "ORG": "ORG",
    "NORP": "DEMOGRAPHIC",
    "DATE": "DATETIME",
    "TIME": "DATETIME",
    "MONEY": "QUANTITY",
    "PERCENT": "QUANTITY",
    "QUANTITY": "QUANTITY",
    "CARDINAL": "QUANTITY",
    "ORDINAL": "QUANTITY",
    "EVENT": "MISC",
    "WORK_OF_ART": "MISC",
    "LAW": "MISC",
    "PRODUCT": "MISC",
    "LANGUAGE": "MISC",
}
"""OntoNotes' 18 entity types mapped onto the harmonised taxonomy."""

_ENAMEX = re.compile(r'<ENAMEX TYPE="([^"]+)"[^>]*>(.*?)</ENAMEX>', re.DOTALL)
_COREF = re.compile(r'<COREF ID="([^"]+)"[^>]*>(.*?)</COREF>', re.DOTALL)
_DOC = re.compile(r"</?DOC[^>]*>")
_TAG = re.compile(r"<[^>]+>")


def extract(
    tarball: Path | str,
    destination: Path | str,
    languages: Sequence[str] = ("english", "chinese", "arabic"),
    progress: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """Pull the ``.name`` and ``.coref`` layers out of the archive in **one** pass.

    The archive is 890 MB of gzip holding ~23,000 files; scanning it per document would cost a full
    decompression each time.  One sequential pass writes the two layers we need — a few tens of
    megabytes — after which loading is ordinary file I/O.

    The directory structure *below* the language is preserved, because document basenames are not
    unique across genres (``nw/…/ann_0001.name`` and ``bn/…/ann_0001.name`` both exist).  Flattening
    them would silently overwrite documents, and the genre — a factor we report on — would be lost
    with them.
    """
    destination = Path(destination)
    counts: dict[str, int] = defaultdict(int)
    wanted = tuple(languages)
    seen = 0
    with tarfile.open(tarball, mode="r|gz") as tar:
        for member in tar:
            seen += 1
            if progress and seen % 50_000 == 0:
                progress(f"scanned {seen} members, kept {sum(counts.values())}")
            if not member.isfile() or not member.name.endswith((".name", ".coref")):
                continue
            parts = member.name.split("/")
            try:
                index = next(i for i, part in enumerate(parts) if part in wanted)
            except StopIteration:
                continue
            language = parts[index]
            # Everything under ``<language>/annotations/`` — genre, source, subdirectory, stem.
            tail = parts[index + 1 :]
            if tail and tail[0] == "annotations":
                tail = tail[1:]
            handle = tar.extractfile(member)
            if handle is None:
                continue
            out = destination / language / Path(*tail)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(handle.read())
            counts[f"{language}/{Path(member.name).suffix.lstrip('.')}"] += 1
    return dict(counts)


def _strip(markup: str) -> str:
    """Remove every tag and unescape, leaving the underlying text."""
    return html.unescape(_TAG.sub("", _DOC.sub("", markup))).strip()


def _spans_from(markup: str, pattern: re.Pattern[str]) -> tuple[str, list[tuple[int, int, str]]]:
    """Strip inline markup, recording each match as ``(start, end, label)`` in the stripped text.

    Every fragment is unescaped exactly once, as it is appended.  Unescaping the joined string
    instead would shorten fragments *before* the recorded offsets and shift every span after the
    first ``&amp;`` — the kind of error that produces plausible-looking but wrong entity text.
    """
    text_parts: list[str] = []
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    length = 0
    body = _DOC.sub("", markup)
    for match in pattern.finditer(body):
        before = html.unescape(_TAG.sub("", body[cursor : match.start()]))
        text_parts.append(before)
        length += len(before)
        inner = html.unescape(_TAG.sub("", match.group(2)))
        spans.append((length, length + len(inner), match.group(1)))
        text_parts.append(inner)
        length += len(inner)
        cursor = match.end()
    text_parts.append(html.unescape(_TAG.sub("", body[cursor:])))
    return "".join(text_parts), spans


def parse_name(markup: str) -> tuple[str, list[tuple[int, int, str]]]:
    """``.name`` -> (text, [(start, end, ontonotes_type)])."""
    return _spans_from(markup, _ENAMEX)


def parse_coref(markup: str) -> tuple[str, list[tuple[int, int, str]]]:
    """``.coref`` -> (text, [(start, end, chain_id)])."""
    return _spans_from(markup, _COREF)


@dataclass(frozen=True)
class LoadReport:
    """What :func:`load` kept and what it had to drop, per language.

    Dropped co-reference is not a detail: OntoNotes is in the study *for* its chains, so a run that
    silently lost them would report stability over a corpus that no longer supports it.
    """

    documents: int = 0
    with_coref: int = 0
    coref_misaligned: int = 0
    """Documents whose ``.coref`` layer yielded no usable span at all."""
    coref_spans_dropped: int = 0
    """Individual chain spans that could not be carried across the token alignment."""
    coref_absent: int = 0
    empty: int = 0

    def __str__(self) -> str:
        return (
            f"{self.documents} documents, {self.with_coref} with co-reference; dropped "
            f"{self.coref_misaligned} misaligned, {self.coref_spans_dropped} unmappable spans, "
            f"{self.coref_absent} without a .coref layer, {self.empty} empty"
        )



def _tokens(text: str) -> list[tuple[str, int, int]]:
    """Whitespace tokenisation with character offsets: ``(token, start, end)``."""
    return [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def map_coref_onto_name(
    name_text: str,
    coref_text: str,
    coref_spans: list[tuple[int, int, str]],
) -> tuple[list[tuple[int, int, str]], int]:
    """Move ``.coref`` chain spans onto the ``.name`` text, returning ``(spans, dropped)``.

    The two layers are **not** over the same token stream, which is why an exact-text match attaches
    nothing at all: ``.coref`` carries the Penn Treebank null elements — ``*pro*``, ``*T*-1``,
    ``*PRO*``, ``*OP*``, the null complementiser ``0`` — and ``.name`` does not.  Measured over 102
    document pairs: 27,000 such tokens appear only in ``.coref``, against five tokens that appear
    only in ``.name``.  ``.coref`` also wraps its body in ``<TEXT PARTNO=…>``, which leaves an extra
    newline behind once the tags are stripped.

    Rather than hard-code the null-element inventory — which is a guess that fails silently on the
    token it does not know — the two token sequences are aligned with :mod:`difflib`, and a chain
    span is carried across only when **every one of its tokens** lands inside a matched block.  Spans
    that do not are dropped and counted, never approximated: a mis-aligned chain would corrupt
    exactly the stability metric OntoNotes was included to support.
    """
    name_tokens = _tokens(name_text)
    coref_tokens = _tokens(coref_text)
    matcher = difflib.SequenceMatcher(
        a=[t for t, _, _ in coref_tokens], b=[t for t, _, _ in name_tokens], autojunk=False
    )
    # coref token index -> name token index, for the tokens the two streams share.
    index: dict[int, int] = {}
    for i, j, size in matcher.get_matching_blocks():
        for offset in range(size):
            index[i + offset] = j + offset

    out: list[tuple[int, int, str]] = []
    dropped = 0
    for start, end, chain in coref_spans:
        covered = [k for k, (_, s, e) in enumerate(coref_tokens) if s < end and start < e]
        if not covered or any(k not in index for k in covered):
            dropped += 1
            continue
        first, last = index[covered[0]], index[covered[-1]]
        out.append((name_tokens[first][1], name_tokens[last][2], chain))
    return out, dropped


def load(
    root: Path | str,
    languages: Sequence[str] = ("english", "chinese", "arabic"),
    limit_per_language: int | None = None,
    report: dict[str, LoadReport] | None = None,
) -> Corpus:
    """Build a corpus from a directory produced by :func:`extract`.

    Documents with no ``.name`` layer are skipped: without entity spans there is nothing to
    pseudonymise.  Co-reference is attached only where the ``.coref`` layer strips to the same text;
    pass ``report`` to receive the per-language tally of what that cost.
    """
    root = Path(root)
    documents: list[Document] = []

    for language in languages:
        directory = root / language
        if not directory.is_dir():
            continue
        tally = LoadReport()
        names = sorted(directory.rglob("*.name"))
        if limit_per_language:
            names = names[:limit_per_language]
        for name_path in names:
            text, entities = parse_name(name_path.read_text("utf-8", errors="replace"))
            if not text.strip():
                tally = replace(tally, empty=tally.empty + 1)
                continue
            relative = name_path.relative_to(directory).with_suffix("")
            doc_id = f"ontonotes/{language}/{relative.as_posix()}"

            chains: dict[tuple[int, int], str] = {}
            coref_path = name_path.with_suffix(".coref")
            if not coref_path.exists():
                tally = replace(tally, coref_absent=tally.coref_absent + 1)
            else:
                coref_text, coref_spans = parse_coref(
                    coref_path.read_text("utf-8", errors="replace")
                )
                mapped, dropped = map_coref_onto_name(text, coref_text, coref_spans)
                chains = {(s, e): cid for s, e, cid in mapped}
                if dropped:
                    tally = replace(tally, coref_spans_dropped=tally.coref_spans_dropped + dropped)
                if not mapped and coref_spans:
                    tally = replace(tally, coref_misaligned=tally.coref_misaligned + 1)

            mentions = []
            for i, (start, end, raw_type) in enumerate(entities):
                chain = chains.get((start, end))
                mentions.append(
                    Mention(
                        doc_id=doc_id,
                        mention_id=f"n{i}",
                        span=Span(start, end, text[start:end],
                                  TYPE_MAP.get(raw_type, "MISC"), type_src=raw_type),
                        # A chain id is attached only on an exact span match, never by overlap, and
                        # is namespaced by document: OntoNotes numbers chains per document, so a
                        # bare id would fabricate cross-document identity between unrelated people.
                        gold_entity_id=f"{doc_id}#{chain}" if chain is not None else None,
                    )
                )
            documents.append(
                Document(
                    doc_id=doc_id, text=text, language=_iso(language), mentions=tuple(mentions),
                    corpus="ontonotes", domain=_genre(relative.as_posix()), provenance="real",
                    subject_id=None,          # OntoNotes chains are document-scoped, like TAB's
                    task={"name": "ontonotes_coref_ner"},
                    metadata={"annotation": "gold", "ontonotes_language": language,
                              "genre_code": relative.parts[0] if relative.parts else "",
                              "has_coref": bool(chains)},
                )
            )
            tally = replace(tally, documents=tally.documents + 1,
                            with_coref=tally.with_coref + bool(chains))
        if report is not None:
            report[language] = tally
    return Corpus("ontonotes", tuple(documents))


def _iso(language: str) -> str:
    return {"english": "en", "chinese": "zh", "arabic": "ar"}.get(language, language[:2])


GENRES: dict[str, str] = {
    "bc": "broadcast_conversation",
    "bn": "broadcast_news",
    "mz": "magazine",
    "nw": "newswire",
    "pt": "pivot_text",
    "tc": "telephone_conversation",
    "wb": "web",
}
"""OntoNotes' genre directory codes, which sit directly under ``<language>/annotations/``."""


def _genre(relative_path: str) -> str:
    return GENRES.get(relative_path.split("/", 1)[0], "unknown")


def iter_documents(corpus: Corpus) -> Iterator[Document]:
    return iter(corpus.documents)
