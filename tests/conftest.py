"""Shared fixtures.

Documents are built by locating the entity strings in the text rather than by hand-counted
offsets, so a fixture can never silently drift out of alignment with its own text.
"""

from __future__ import annotations

import pytest

from pseudonymkit.domain import Corpus, Document, Mention, Span


def build(doc_id: str, text: str, entities: list[tuple[str, str, str | None]],
          language: str = "en") -> Document:
    """Build a document by finding each surface form in ``text``.

    ``entities`` must be listed in document order: the search advances a single cursor, so a
    surface that is a substring of an earlier one (``Weber`` inside ``Dr. Weber``) cannot be
    matched inside it by accident.
    """
    cursor = 0
    mentions = []
    for i, (surface, type_, chain) in enumerate(entities):
        start = text.find(surface, cursor)
        if start < 0:
            raise AssertionError(f"{surface!r} not found in fixture text at or after {cursor}")
        cursor = start + len(surface)
        mentions.append(
            Mention(doc_id, f"m{i}", Span(start, start + len(surface), surface, type_),
                    gold_entity_id=chain)
        )
    return Document(doc_id, text, language, tuple(mentions))


@pytest.fixture
def weber_doc() -> Document:
    """One person written three ways, one place written twice."""
    return build(
        "d1",
        "Dr. Weber met Weber in Berlin. F. Weber later left Berlin.",
        [("Dr. Weber", "PERSON", "e1"), ("Weber", "PERSON", "e1"), ("Berlin", "LOC", "e2"),
         ("F. Weber", "PERSON", "e1"), ("Berlin", "LOC", "e2")],
    )


@pytest.fixture
def two_doc_corpus() -> Corpus:
    """The same person in two documents, sharing a cross-document chain id."""
    a = build("d1", "Weber called Meyer.", [("Weber", "PERSON", "e1"), ("Meyer", "PERSON", "e2")])
    b = build("d2", "Meyer answered Weber.", [("Meyer", "PERSON", "e2"), ("Weber", "PERSON", "e1")])
    return Corpus("two", (a, b))
