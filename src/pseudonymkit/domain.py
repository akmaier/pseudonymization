"""Value objects shared by every part of the pipeline.

These types are deliberately free of I/O, of any corpus format and of any model.  Corpora are
converted *into* them by adapters in :mod:`pseudonymkit.adapters`, detectors emit them, the
engine transforms them and the metrics read them.  Keeping the domain inert is what allows a
detector, a corpus or a technique to be swapped without touching anything else.

All types are frozen: a run must be reproducible from its configuration and seed, and mutable
state shared between cells is the usual way that stops being true.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable, Iterator, Mapping, Sequence

__all__ = [
    "Span",
    "Mention",
    "Document",
    "Corpus",
    "Assignment",
    "PseudonymMapping",
]


@dataclass(frozen=True, slots=True, order=True)
class Span:
    """A character range in a document, with a harmonised entity type.

    Offsets are Python string indices into :attr:`Document.text` — half-open, ``[start, end)``.
    ``type`` is a name from the harmonised taxonomy (PERSON, LOC, ORG, DATETIME, ...), not the
    source corpus's own label; ``type_src`` keeps the original for traceability.
    """

    start: int
    end: int
    text: str
    type: str
    type_src: str | None = None
    source: str | None = None
    """Which detector produced this span; ``None`` for gold."""
    score: float | None = None

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span offsets: [{self.start}, {self.end})")

    @property
    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: Span) -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True, slots=True)
class Mention:
    """One occurrence of an entity in a document.

    ``gold_entity_id`` is the co-reference chain identifier where the corpus provides one.  It is
    the *ground truth* for the stability metrics and must never be used as the pseudonymisation
    key — see ``experiment_plan.md`` §8.2.
    """

    doc_id: str
    mention_id: str
    span: Span
    gold_entity_id: str | None = None
    attributes: Mapping[str, str] = field(default_factory=dict)
    """Inferred or annotated attributes (gender, locale, ...) used by attribute-matched surrogates."""

    @property
    def type(self) -> str:
        return self.span.type

    @property
    def surface(self) -> str:
        return self.span.text


@dataclass(frozen=True, slots=True)
class Document:
    """A single text with its mentions."""

    doc_id: str
    text: str
    language: str
    mentions: Sequence[Mention] = ()
    corpus: str | None = None
    domain: str | None = None
    provenance: str | None = None
    """Identifier provenance tier: real | surrogate | placeholder | inserted | synthetic."""
    subject_id: str | None = None
    """Cross-document identity (patient, mailbox owner) where the corpus supplies one."""
    task: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def with_mentions(self, mentions: Sequence[Mention]) -> Document:
        """Return a copy carrying a different mention set (e.g. from another detector)."""
        return replace(self, mentions=tuple(mentions))

    def mentions_of_type(self, type_: str) -> tuple[Mention, ...]:
        return tuple(m for m in self.mentions if m.type == type_)


@dataclass(frozen=True, slots=True)
class Corpus:
    """A named collection of documents."""

    name: str
    documents: Sequence[Document] = ()

    def __iter__(self) -> Iterator[Document]:
        return iter(self.documents)

    def __len__(self) -> int:
        return len(self.documents)

    @property
    def languages(self) -> frozenset[str]:
        return frozenset(d.language for d in self.documents)


@dataclass(frozen=True, slots=True)
class Assignment:
    """The pseudonym chosen for one scope key."""

    scope_key: tuple[str, ...]
    entity_key: str
    entity_type: str
    index: int
    """The integer produced by the technique — the axis-B output, before rendering."""
    surface: str
    """The rendered replacement text — the axis-C output."""


class PseudonymMapping:
    """Every assignment made during one pseudonymisation run.

    Holds the record the stability metrics and the attacks read.  It is append-only: an assignment
    for a scope key is made once and reused, which is precisely what makes a policy *stable* within
    its scope.
    """

    def __init__(self) -> None:
        self._by_scope: dict[tuple[str, ...], Assignment] = {}

    def get(self, scope_key: tuple[str, ...]) -> Assignment | None:
        return self._by_scope.get(scope_key)

    def put(self, assignment: Assignment) -> Assignment:
        existing = self._by_scope.get(assignment.scope_key)
        if existing is not None:
            return existing
        self._by_scope[assignment.scope_key] = assignment
        return assignment

    def __len__(self) -> int:
        return len(self._by_scope)

    def __iter__(self) -> Iterator[Assignment]:
        return iter(self._by_scope.values())

    def assignments(self) -> tuple[Assignment, ...]:
        return tuple(self._by_scope.values())

    def surfaces_by_entity_key(self) -> dict[str, set[str]]:
        """entity key -> the distinct surfaces it was given (across all scopes)."""
        out: dict[str, set[str]] = {}
        for a in self._by_scope.values():
            out.setdefault(a.entity_key, set()).add(a.surface)
        return out

    def entity_keys_by_surface(self) -> dict[str, set[str]]:
        """Rendered surface -> the distinct entity keys that produced it. Collisions have >1."""
        out: dict[str, set[str]] = {}
        for a in self._by_scope.values():
            out.setdefault(a.surface, set()).add(a.entity_key)
        return out


def iter_mentions(documents: Iterable[Document]) -> Iterator[Mention]:
    """Flatten mentions across documents, preserving document order."""
    for doc in documents:
        yield from doc.mentions
