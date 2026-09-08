"""Entity profiles — what an attacker can assemble about a pseudonymised entity.

Pseudonymisation replaces the *name* and leaves everything else. What remains around an entity is:

* **context** — the words near its mentions. Unchanged by pseudonymisation, because only entity
  spans are rewritten. This is "the facts in the text".
* **relations** — which other entities it co-occurs with, and how often. Unchanged in structure,
  only relabelled.
* **structure** — how many mentions, across how many documents, with what degree.

A profile is that triple. Both attacks in this package consume it: A3 compares profiles with a fixed
similarity, A5 learns one. Building the representation once, and sharing it, is what makes the gap
between them attributable to the learning rather than to different inputs.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Container, Iterable, Mapping, Sequence

from ..domain import Corpus, Document
from ..engine import PseudonymisedCorpus

__all__ = ["EntityProfile", "build_gallery", "build_queries", "truth_map",
           "disjoint_document_split"]

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
_STOP = frozenset(
    """the and for you are with this that have from was not but they will would there their what
    about which when your all can has had our out who get been more one time some had said may
    please thank thanks regards subject date message sent from mailto original http https com www
    enron""".split()
)


@dataclass(frozen=True, slots=True)
class EntityProfile:
    """Everything an attacker sees about one entity."""

    key: str
    """Pseudonym surface for a query, real entity key for a gallery entry."""
    mentions: int
    documents: frozenset[str]
    neighbours: Mapping[str, int] = field(default_factory=dict)
    context: Mapping[str, int] = field(default_factory=dict)

    @property
    def degree(self) -> int:
        return len(self.neighbours)


def _context_terms(text: str, start: int, end: int, window: int) -> list[str]:
    left = text[max(0, start - window) : start]
    right = text[end : end + window]
    return [
        w.casefold()
        for w in _WORD_RE.findall(left + " " + right)
        if w.casefold() not in _STOP
    ]


def _profiles(
    per_doc: Iterable[tuple[str, str, Sequence[tuple[str, int, int]]]], window: int
) -> dict[str, EntityProfile]:
    """Assemble profiles from ``(doc_id, text, [(entity, start, end), ...])``."""
    mentions: Counter[str] = Counter()
    docs: dict[str, set[str]] = defaultdict(set)
    neighbours: dict[str, Counter[str]] = defaultdict(Counter)
    context: dict[str, Counter[str]] = defaultdict(Counter)

    for doc_id, text, items in per_doc:
        present = {e for e, _, _ in items}
        for entity, start, end in items:
            mentions[entity] += 1
            docs[entity].add(doc_id)
            context[entity].update(_context_terms(text, start, end, window))
            for other in present:
                if other != entity:
                    neighbours[entity][other] += 1

    return {
        entity: EntityProfile(
            key=entity,
            mentions=count,
            documents=frozenset(docs[entity]),
            neighbours=dict(neighbours[entity]),
            context=dict(context[entity]),
        )
        for entity, count in mentions.items()
    }


def build_gallery(
    corpus: Corpus,
    entity_type: str = "PERSON",
    window: int = 120,
    documents: Container[str] | None = None,
) -> dict[str, EntityProfile]:
    """Profiles keyed by **real** identity — what the attacker already knows.

    Uses ``gold_entity_id`` where the corpus supplies one, which for Enron is the e-mail address and
    therefore a genuine cross-document identity.

    ``documents`` restricts the gallery to a subset of document ids, and **should almost always be
    set**.  Building the gallery from the same documents the queries come from makes the two sides
    byte-identical apart from the replaced spans, so the attack degenerates into matching a corpus
    against itself and reports a re-identification rate that no real adversary could achieve.  A
    real attacker holds *other* evidence about the same people.  See
    :func:`disjoint_document_split`.
    """
    per_doc = []
    for doc in corpus:
        if documents is not None and doc.doc_id not in documents:
            continue
        items = [
            (m.gold_entity_id, m.span.start, m.span.end)
            for m in doc.mentions
            if m.type == entity_type and m.gold_entity_id
        ]
        if items:
            per_doc.append((doc.doc_id, doc.text, items))
    return _profiles(per_doc, window)


def build_queries(
    result: PseudonymisedCorpus,
    entity_type: str = "PERSON",
    window: int = 120,
    documents: Container[str] | None = None,
) -> dict[str, EntityProfile]:
    """Profiles keyed by **pseudonym** — what the attacker is given.

    Context is read out of the *pseudonymised* text, exactly as a released corpus would be, so the
    attack never touches anything a real adversary could not see.
    """
    per_doc = []
    for pdoc in result.documents:
        if documents is not None and pdoc.document.doc_id not in documents:
            continue
        skipped = {(m.doc_id, m.mention_id) for m in pdoc.skipped}
        replaced = [
            m
            for m in sorted(pdoc.document.mentions, key=lambda m: (m.span.start, -m.span.length))
            if (m.doc_id, m.mention_id) not in skipped
        ]
        items: list[tuple[str, int, int]] = []
        offset = 0
        for mention, assignment in zip(replaced, pdoc.assignments):
            start = mention.span.start + offset
            end = start + len(assignment.surface)
            offset += len(assignment.surface) - mention.span.length
            if mention.type == entity_type:
                items.append((assignment.surface, start, end))
        if items:
            per_doc.append((pdoc.document.doc_id, pdoc.text, items))
    return _profiles(per_doc, window)


def truth_map(
    result: PseudonymisedCorpus, entity_type: str = "PERSON"
) -> dict[str, str]:
    """pseudonym -> the gold entity behind it, for scoring only.

    Pseudonyms shared by several gold entities are dropped: with no single correct answer they
    cannot be scored either way.
    """
    seen: dict[str, set[str]] = defaultdict(set)
    for pdoc in result.documents:
        skipped = {(m.doc_id, m.mention_id) for m in pdoc.skipped}
        replaced = [
            m
            for m in sorted(pdoc.document.mentions, key=lambda m: (m.span.start, -m.span.length))
            if (m.doc_id, m.mention_id) not in skipped
        ]
        for mention, assignment in zip(replaced, pdoc.assignments):
            if mention.type == entity_type and mention.gold_entity_id:
                seen[assignment.surface].add(mention.gold_entity_id)
    return {p: next(iter(g)) for p, g in seen.items() if len(g) == 1}


def disjoint_document_split(
    corpus: Corpus, fraction: float = 0.5, seed: int = 0
) -> tuple[frozenset[str], frozenset[str]]:
    """Split document ids into a gallery half and a query half.

    The attacker's knowledge and the released corpus must come from **different documents**.
    Otherwise the context around an entity is identical on both sides — only the names were
    rewritten — and the attack measures nothing but the fact that a corpus matches itself.

    Deterministic given ``seed``, so a cell is reproducible.
    """
    import random

    ids = sorted(d.doc_id for d in corpus)
    rng = random.Random(seed)
    rng.shuffle(ids)
    cut = int(len(ids) * fraction)
    return frozenset(ids[:cut]), frozenset(ids[cut:])
