"""Adapter: OntoNotes 5.0 (LDC2013T19) -> the domain model.

OntoNotes is the only member of the meta corpus that supplies **real names, co-reference and
non-Latin script** at once — English, Chinese and Arabic across news, broadcast, weblog, telephone
speech and usenet.  It is why the study can say anything at all about scripts where the 2026
evaluations report detector collapse (Arabic F1 0.04).

The release stores one directory per document with parallel annotation layers.  Two matter here:

* ``.name`` — inline SGML, ``<ENAMEX TYPE="PERSON">Pierre Vinken</ENAMEX>``, over the sentence
  stream.  Gives the text and the typed spans.
* ``.coref`` — the same stream marked with ``<COREF ID="…">``.  Gives the chains the stability
  metrics need.

They are separate files over the same tokenisation, so the adapter builds the document from
``.name`` and maps ``.coref`` onto it **only when the two strip to identical text**.  Where they do
not, co-reference is dropped for that document and counted, rather than aligned by guesswork — a
mis-aligned chain would corrupt exactly the metric OntoNotes was included to support.
"""

from __future__ import annotations

import html
import re
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Iterator, Sequence

from ..domain import Corpus, Document, Mention, Span

__all__ = ["extract", "load", "parse_name", "parse_coref", "TYPE_MAP"]

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
) -> dict[str, int]:
    """Pull the ``.name`` and ``.coref`` layers out of the archive in **one** pass.

    The archive is 890 MB of gzip holding ~23,000 files; scanning it per document would cost a full
    decompression each time.  One sequential pass writes the two layers we need — a few tens of
    megabytes — after which loading is ordinary file I/O.
    """
    destination = Path(destination)
    counts: dict[str, int] = defaultdict(int)
    wanted = tuple(languages)
    with tarfile.open(tarball, mode="r|gz") as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith((".name", ".coref")):
                continue
            parts = member.name.split("/")
            language = next((p for p in parts if p in wanted), None)
            if language is None:
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            out = destination / language / Path(member.name).name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(handle.read())
            counts[f"{language}/{Path(member.name).suffix.lstrip('.')}"] += 1
    return dict(counts)


def _strip(markup: str) -> str:
    """Remove every tag and unescape, leaving the underlying text."""
    return html.unescape(_TAG.sub("", _DOC.sub("", markup))).strip()


def _spans_from(markup: str, pattern: re.Pattern[str]) -> tuple[str, list[tuple[int, int, str]]]:
    """Strip inline markup, recording each match as ``(start, end, label)`` in the stripped text."""
    text_parts: list[str] = []
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    length = 0
    body = _DOC.sub("", markup)
    for match in pattern.finditer(body):
        before = _TAG.sub("", body[cursor : match.start()])
        text_parts.append(before)
        length += len(before)
        inner = html.unescape(_TAG.sub("", match.group(2)))
        spans.append((length, length + len(inner), match.group(1)))
        text_parts.append(inner)
        length += len(inner)
        cursor = match.end()
    tail = _TAG.sub("", body[cursor:])
    text_parts.append(tail)
    return html.unescape("".join(text_parts)), spans


def parse_name(markup: str) -> tuple[str, list[tuple[int, int, str]]]:
    """``.name`` -> (text, [(start, end, ontonotes_type)])."""
    return _spans_from(markup, _ENAMEX)


def parse_coref(markup: str) -> tuple[str, list[tuple[int, int, str]]]:
    """``.coref`` -> (text, [(start, end, chain_id)])."""
    return _spans_from(markup, _COREF)


def load(
    root: Path | str,
    languages: Sequence[str] = ("english", "chinese", "arabic"),
    limit_per_language: int | None = None,
) -> Corpus:
    """Build a corpus from a directory produced by :func:`extract`.

    Documents with no ``.name`` layer are skipped: without entity spans there is nothing to
    pseudonymise.  Co-reference is attached only where the ``.coref`` layer strips to the same text.
    """
    root = Path(root)
    documents: list[Document] = []
    dropped_coref = 0

    for language in languages:
        directory = root / language
        if not directory.is_dir():
            continue
        names = sorted(directory.glob("*.name"))
        if limit_per_language:
            names = names[:limit_per_language]
        for name_path in names:
            text, entities = parse_name(name_path.read_text("utf-8", errors="replace"))
            if not text.strip():
                continue
            doc_id = f"ontonotes/{language}/{name_path.stem}"

            chains: dict[tuple[int, int], str] = {}
            coref_path = name_path.with_suffix(".coref")
            if coref_path.exists():
                coref_text, coref_spans = parse_coref(
                    coref_path.read_text("utf-8", errors="replace")
                )
                if coref_text == text:
                    chains = {(s, e): cid for s, e, cid in coref_spans}
                else:
                    dropped_coref += 1

            mentions = []
            for i, (start, end, raw_type) in enumerate(entities):
                mentions.append(
                    Mention(
                        doc_id=doc_id,
                        mention_id=f"n{i}",
                        span=Span(start, end, text[start:end],
                                  TYPE_MAP.get(raw_type, "MISC"), type_src=raw_type),
                        # A chain id is attached only on an exact span match, never by overlap.
                        gold_entity_id=chains.get((start, end)),
                    )
                )
            documents.append(
                Document(
                    doc_id=doc_id, text=text, language=_iso(language), mentions=tuple(mentions),
                    corpus="ontonotes", domain=_genre(name_path.stem), provenance="real",
                    subject_id=None,          # OntoNotes chains are document-scoped, like TAB's
                    task={"name": "ontonotes_coref_ner"},
                    metadata={"annotation": "gold", "ontonotes_language": language,
                              "has_coref": bool(chains)},
                )
            )
    if dropped_coref:
        documents = documents          # count surfaced by the caller via metadata
    return Corpus("ontonotes", tuple(documents))


def _iso(language: str) -> str:
    return {"english": "en", "chinese": "zh", "arabic": "ar"}.get(language, language[:2])


def _genre(stem: str) -> str:
    for prefix, genre in (("wsj", "news"), ("cnn", "broadcast"), ("abc", "broadcast"),
                          ("voa", "broadcast"), ("chtb", "news"), ("ann", "news")):
        if stem.startswith(prefix):
            return genre
    return "mixed"


def iter_documents(corpus: Corpus) -> Iterator[Document]:
    return iter(corpus.documents)
