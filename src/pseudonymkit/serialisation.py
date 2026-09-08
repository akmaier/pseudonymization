"""Writing a corpus to JSONL and reading it back.

This exists for exactly one reason: **Enron cannot be materialised where it is needed.** Building it
takes more memory than the cluster head node has — and, as it turned out, more than an 18 GB laptop
has either: a full pass over all 517,401 messages was killed by memory pressure while constructing
the documents. So the sampled corpus is built once, on a machine that can hold it, and shipped.

It is deliberately **not** a general corpus format. Every other corpus in the study is read straight
from its release by its adapter, which is where corpus-specific knowledge belongs; adding a canonical
intermediate for all of them would be a layer nobody needs. This is one file per corpus, one JSON
object per document, gzip-friendly, and it round-trips the domain model exactly.

Dataclasses inside ``Document.task`` — CARDIO:DE's medication and section spans, for instance — are
encoded structurally with a ``__type__`` tag so that a reader can tell a serialised span from a plain
dictionary, and so that a corpus that carries them does not silently lose them.
"""

from __future__ import annotations

import dataclasses
import gzip
import json
from pathlib import Path
from typing import Any, Iterator

from .domain import Corpus, Document, Mention, Span

__all__ = ["write_corpus", "read_corpus", "iter_documents"]


def _encode(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {"__type__": type(value).__name__, **{
            f.name: _encode(getattr(value, f.name)) for f in dataclasses.fields(value)
        }}
    if isinstance(value, dict):
        return {str(k): _encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    return value


def _document_record(document: Document) -> dict[str, Any]:
    return {
        "doc_id": document.doc_id,
        "text": document.text,
        "language": document.language,
        "corpus": document.corpus,
        "domain": document.domain,
        "provenance": document.provenance,
        "subject_id": document.subject_id,
        "task": _encode(dict(document.task)),
        "metadata": _encode(dict(document.metadata)),
        "mentions": [
            {
                "mention_id": m.mention_id,
                "start": m.span.start,
                "end": m.span.end,
                "text": m.span.text,
                "type": m.span.type,
                "type_src": m.span.type_src,
                "gold_entity_id": m.gold_entity_id,
                "attributes": dict(m.attributes),
            }
            for m in document.mentions
        ],
    }


def _open(path: Path, mode: str):
    """Transparently gzip when the name says so — a sampled Enron is ~160 MB plain, ~50 MB gzipped."""
    if path.suffix == ".gz":
        return gzip.open(path, mode + "t", encoding="utf-8")
    return path.open(mode, encoding="utf-8")


def write_corpus(corpus: Corpus, path: Path | str) -> int:
    """Write one document per line. Returns the number written.

    The corpus **name** goes on the first line as a header record, because it carries the sampling
    provenance — scheme, rate and seed — and ``experiment_plan.md`` §5 forbids quoting any result
    without it. Losing it in transit would make the shipped corpus unciteable.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with _open(path, "w") as handle:
        handle.write(json.dumps({"__corpus__": corpus.name, "documents": len(corpus)}) + "\n")
        for document in corpus.documents:
            handle.write(json.dumps(_document_record(document), ensure_ascii=False) + "\n")
            written += 1
    return written


def iter_documents(path: Path | str) -> Iterator[Document]:
    """Stream documents back without holding the corpus in memory."""
    for record in _records(Path(path)):
        yield _document(record)


def read_corpus(path: Path | str) -> Corpus:
    """Read the whole file, restoring the corpus name and its sampling provenance."""
    path = Path(path)
    name = "unknown"
    documents: list[Document] = []
    with _open(path, "r") as handle:
        for line in handle:
            record = json.loads(line)
            if "__corpus__" in record:
                name = record["__corpus__"]
                continue
            documents.append(_document(record))
    return Corpus(name, tuple(documents))


def _records(path: Path) -> Iterator[dict[str, Any]]:
    with _open(path, "r") as handle:
        for line in handle:
            record = json.loads(line)
            if "__corpus__" not in record:
                yield record


def _document(record: dict[str, Any]) -> Document:
    doc_id = record["doc_id"]
    mentions = tuple(
        Mention(
            doc_id=doc_id,
            mention_id=m["mention_id"],
            span=Span(m["start"], m["end"], m["text"], m["type"], type_src=m.get("type_src")),
            gold_entity_id=m.get("gold_entity_id"),
            attributes=m.get("attributes") or {},
        )
        for m in record.get("mentions", ())
    )
    return Document(
        doc_id=doc_id,
        text=record["text"],
        language=record["language"],
        mentions=mentions,
        corpus=record.get("corpus"),
        domain=record.get("domain"),
        provenance=record.get("provenance"),
        subject_id=record.get("subject_id"),
        task=record.get("task") or {},
        metadata=record.get("metadata") or {},
    )
