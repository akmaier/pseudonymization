"""Adapter: the Text Anonymization Benchmark (TAB) -> the domain model.

TAB is 1,268 English judgments of the European Court of Human Rights, annotated with entity type,
identifier class (DIRECT / QUASI / NO_MASK), confidential status and — uniquely among the corpora in
this study — **co-reference chains**.  That is what makes it the corpus the stability metrics were
designed against.

Two properties of the release shape this adapter:

* Documents carry **several annotators**, 274 of the 1,268 with two to ten.  Which annotator is used
  is an experimental setting, not a detail, so it is explicit here and recorded with the results.
* ``entity_id`` is **document-scoped**.  Chains may be compared within a document and never across
  documents; :func:`load` therefore never sets ``subject_id``.

The article labels ride along in ``meta.articles`` and become the document's downstream task, so the
legal utility task needs no join to an external judgment-prediction dataset.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator, Literal, Sequence

from ..domain import Corpus, Document, Mention, Span

__all__ = ["load", "load_split", "TYPE_MAP"]

TYPE_MAP: dict[str, str] = {
    "PERSON": "PERSON",
    "LOC": "LOC",
    "ORG": "ORG",
    "DATETIME": "DATETIME",
    "CODE": "CODE",
    "QUANTITY": "QUANTITY",
    "DEM": "DEMOGRAPHIC",
    "MISC": "MISC",
}
"""TAB's eight categories mapped onto the harmonised taxonomy."""

AnnotatorChoice = Literal["first", "quality_checked", "all"]


def load_split(
    path: Path | str,
    annotator: AnnotatorChoice = "first",
    types: Sequence[str] | None = None,
) -> Iterator[Document]:
    """Read one ``echr_*.json`` file.

    ``annotator``:

    * ``"first"`` — the lexicographically first annotator. Deterministic, one opinion per document.
    * ``"quality_checked"`` — prefer a document flagged as revised by a second annotator, else fall
      back to the first. Higher quality, at the cost of a non-uniform annotator population.
    * ``"all"`` — every annotator's mentions merged. Inflates mention counts and duplicates spans;
      useful only for measuring inter-annotator disagreement, never for a stability cell.
    """
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    keep = set(types) if types else None
    for record in records:
        yield _document(record, annotator, keep)


def load(
    directory: Path | str,
    splits: Iterable[str] = ("train", "dev", "test"),
    annotator: AnnotatorChoice = "first",
    types: Sequence[str] | None = None,
) -> Corpus:
    """Read the whole benchmark from a checkout of the TAB repository."""
    directory = Path(directory)
    documents = [
        doc
        for split in splits
        for doc in load_split(directory / f"echr_{split}.json", annotator, types)
    ]
    return Corpus("tab", tuple(documents))


def _annotations(record: dict, choice: AnnotatorChoice) -> list[dict]:
    annotations: dict[str, dict] = record.get("annotations", {})
    if not annotations:
        return []
    if choice == "all":
        return [m for ann in annotations.values() for m in ann.get("entity_mentions", [])]
    names = sorted(annotations)
    if choice == "quality_checked" and record.get("quality_checked") and len(names) > 1:
        names = names[1:] + names[:1]
    return list(annotations[names[0]].get("entity_mentions", []))


def _document(record: dict, choice: AnnotatorChoice, keep: set[str] | None) -> Document:
    doc_id = record["doc_id"]
    text = record["text"]
    meta = record.get("meta", {})
    mentions: list[Mention] = []

    for raw in _annotations(record, choice):
        type_ = TYPE_MAP.get(raw["entity_type"], raw["entity_type"])
        if keep is not None and type_ not in keep:
            continue
        start, end = int(raw["start_offset"]), int(raw["end_offset"])
        mentions.append(
            Mention(
                doc_id=doc_id,
                mention_id=raw["entity_mention_id"],
                span=Span(
                    start=start,
                    end=end,
                    text=text[start:end],
                    type=type_,
                    type_src=raw["entity_type"],
                ),
                gold_entity_id=raw.get("entity_id"),
                attributes={
                    "identifier_type": raw.get("identifier_type", ""),
                    "confidential_status": raw.get("confidential_status", ""),
                },
            )
        )

    mentions.sort(key=lambda m: (m.span.start, -m.span.length))
    return Document(
        doc_id=doc_id,
        text=text,
        language="en",
        mentions=tuple(mentions),
        corpus="tab",
        domain="legal",
        provenance="real",
        subject_id=None,  # TAB's entity_id is document-scoped; there is no cross-document identity
        task={"name": "echr_articles", "label": tuple(meta.get("articles", ()))},
        metadata={
            "year": meta.get("year"),
            "countries": meta.get("countries"),
            "legal_branch": meta.get("legal_branch"),
            "split": record.get("dataset_type"),
            "quality_checked": record.get("quality_checked"),
            "annotators": len(record.get("annotations", {})),
        },
    )
