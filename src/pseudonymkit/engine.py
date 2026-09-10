"""The pseudonymiser: composes one cell of the A x B x C design.

One object, four collaborators, no branching on which policy or technique is in play.  Adding a
sixth technique or a fourth surrogate form means registering a class, not editing this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .domain import Assignment, Corpus, Document, Mention, PseudonymMapping
from .keys import Normaliser, entity_key
from .policies import Policy
from .surrogates import SurrogateForm
from .techniques import Technique

__all__ = [
    "Pseudonymiser",
    "PseudonymisedDocument",
    "PseudonymisedCorpus",
    "Replacement",
    "OffsetMap",
    "replacements",
    "offset_map",
]


@dataclass(frozen=True, slots=True)
class PseudonymisedDocument:
    """A document after replacement, with the assignments that produced it."""

    document: Document
    text: str
    assignments: tuple[Assignment, ...]
    skipped: tuple[Mention, ...] = ()
    """Mentions dropped because their span overlapped an already-replaced one."""


@dataclass(frozen=True, slots=True)
class PseudonymisedCorpus:
    documents: tuple[PseudonymisedDocument, ...]
    mapping: PseudonymMapping


class Pseudonymiser:
    """Applies one (normaliser, policy, technique, surrogate form) combination to a corpus.

    The mapping is shared across documents, which is what makes the deterministic policy
    deterministic; the policy decides whether the scope key lets that sharing take effect.

    Instances are stateful — ``counter`` and ``table`` accumulate, and the tag renderer numbers
    entities in order of appearance — so **one instance serves one run**.  Reuse across cells would
    silently leak state between them.
    """

    def __init__(
        self,
        normaliser: Normaliser,
        policy: Policy,
        technique: Technique,
        surrogate: SurrogateForm,
    ) -> None:
        self.normaliser = normaliser
        self.policy = policy
        self.technique = technique
        self.surrogate = surrogate
        self.mapping = PseudonymMapping()

    def assign(self, mention: Mention, language: str) -> Assignment:
        """Resolve the assignment for one mention, creating it on first sight.

        ``language`` selects the surrogate pool and is **required**, not defaulted: the defect it
        replaces (§12.2) was a default of ``"en"`` that silently gave 1,911 Chinese and 446 Arabic
        OntoNotes documents English surrogates.  Non-Latin script is the reason OntoNotes is in the
        study, so a caller that does not know the language must not be able to guess one.

        Note what the deterministic policy does to this.  An entity that appears in two documents of
        different languages is *one* entity and receives *one* pseudonym — the one made when it was
        first seen, in that document's language.  Stability beats locale, which is the policy's whole
        point (§5): a surrogate that changed with the language would break the corpus-wide identity
        the data's usability depends on.
        """
        key = entity_key(mention.surface, mention.type, self.normaliser)
        scope = self.policy.scope_key(key, mention)
        existing = self.mapping.get(scope)
        if existing is not None:
            return existing
        index = self.technique.index(scope, mention.type)
        return self.mapping.put(
            Assignment(
                scope_key=scope,
                entity_key=key,
                entity_type=mention.type,
                index=index,
                surface=self.surrogate.render(index, mention, mention_language(mention, language)),
            )
        )

    def pseudonymise(self, document: Document) -> PseudonymisedDocument:
        """Replace every mention in one document, left to right.

        Overlapping mentions are resolved by keeping the longest span that starts earliest and
        skipping the rest; the skipped ones are reported rather than silently dropped, because an
        ensemble's union rule produces overlaps and their rate is a result in its own right.
        """
        ordered = sorted(document.mentions, key=lambda m: (m.span.start, -m.span.length))
        pieces: list[str] = []
        assignments: list[Assignment] = []
        skipped: list[Mention] = []
        cursor = 0
        for mention in ordered:
            if mention.span.start < cursor:
                skipped.append(mention)
                continue
            assignment = self.assign(mention, document.language)
            pieces.append(document.text[cursor : mention.span.start])
            pieces.append(assignment.surface)
            assignments.append(assignment)
            cursor = mention.span.end
        pieces.append(document.text[cursor:])
        return PseudonymisedDocument(
            document=document,
            text="".join(pieces),
            assignments=tuple(assignments),
            skipped=tuple(skipped),
        )

    def pseudonymise_corpus(self, corpus: Corpus | Iterable[Document]) -> PseudonymisedCorpus:
        documents = corpus.documents if isinstance(corpus, Corpus) else corpus
        return PseudonymisedCorpus(
            documents=tuple(self.pseudonymise(d) for d in documents),
            mapping=self.mapping,
        )


@dataclass(frozen=True, slots=True)
class Replacement:
    """One mention that was actually replaced, with where its surrogate landed."""

    mention: Mention
    assignment: Assignment
    new_start: int
    new_end: int

    @property
    def old_start(self) -> int:
        return self.mention.span.start

    @property
    def old_end(self) -> int:
        return self.mention.span.end


def replacements(document: PseudonymisedDocument) -> tuple[Replacement, ...]:
    """Pair each replaced mention with its assignment and its offsets in the **new** text.

    Every consumer of a pseudonymised corpus needs this and none of them should recompute it.  The
    engine writes the new text as a single left-to-right pass and keeps only the assignment list, so
    the new offsets are implied rather than stored; reconstructing them means replaying the same
    pass, and a second implementation that replays it slightly differently is a silent
    mis-alignment.  The order and the skipping rule here are the engine's own.
    """
    skipped = {(m.doc_id, m.mention_id) for m in document.skipped}
    kept = [
        m
        for m in sorted(document.document.mentions, key=lambda m: (m.span.start, -m.span.length))
        if (m.doc_id, m.mention_id) not in skipped
    ]
    out: list[Replacement] = []
    delta = 0
    for mention, assignment in zip(kept, document.assignments):
        new_start = mention.span.start + delta
        new_end = new_start + len(assignment.surface)
        delta += len(assignment.surface) - mention.span.length
        out.append(Replacement(mention, assignment, new_start, new_end))
    return tuple(out)


@dataclass(frozen=True, slots=True)
class OffsetMap:
    """Maps a character offset in the original text to its place in the pseudonymised text.

    Gold annotations are recorded against the original — CARDIO:DE's medication spans, TAB's
    co-reference chains, every corpus's section boundaries — while a frozen model reads the
    *replaced* text.  Scoring one against the other without this map compares offsets that drift
    further apart with every replacement, and nothing about the result looks wrong: the scores are
    simply low, in a way that reads as utility loss.

    A gold span that **overlaps** a replacement of a different length cannot be mapped exactly,
    because the characters it covered no longer exist.  The rule there is to extend it to the whole
    replacement — a start inside a surrogate becomes the surrogate's start, an end inside it becomes
    its end — which keeps the span covering the same *entities* even though it no longer covers the
    same characters.  That is the only choice that leaves an entity-level task scorable, and it is
    stated here rather than buried, because it is an approximation.

    A replacement that did **not** change length needs no such rule: position *i* inside it still
    denotes position *i*, so the map stays linear there.  Condition A is the limiting case of that —
    every replacement is the identity, and the map is too.
    """

    edits: tuple[tuple[int, int, int, int], ...]
    """``(old_start, old_end, new_start, new_end)`` per replacement, in document order."""

    @classmethod
    def of(cls, document: PseudonymisedDocument) -> OffsetMap:
        return cls(
            tuple(
                (r.old_start, r.old_end, r.new_start, r.new_end)
                for r in replacements(document)
            )
        )

    def _shift(self, index: int, at_end: bool) -> int:
        delta = 0
        for old_start, old_end, new_start, new_end in self.edits:
            if old_end <= index:
                delta += (new_end - new_start) - (old_end - old_start)
                continue
            inside = old_start < index if at_end else old_start <= index
            if inside:
                if (new_end - new_start) == (old_end - old_start):
                    return index + delta        # same length: position i still denotes position i
                return new_end if at_end else new_start
            break
        return index + delta

    def start(self, index: int) -> int:
        """Map an inclusive start offset."""
        return self._shift(index, at_end=False)

    def end(self, index: int) -> int:
        """Map an exclusive end offset."""
        return self._shift(index, at_end=True)

    def span(self, start: int, end: int) -> tuple[int, int]:
        """Map a half-open ``[start, end)`` range."""
        return self.start(start), self.end(end)


def offset_map(document: PseudonymisedDocument) -> OffsetMap:
    """The original-to-pseudonymised offset map for one document."""
    return OffsetMap.of(document)


def mention_language(mention: Mention, default: str) -> str:
    """Language for surrogate selection.

    The **document's** language is the default, passed in by :meth:`Pseudonymiser.pseudonymise`.  A
    mention may override it — a quoted foreign name inside an otherwise German letter — but no
    adapter sets that attribute today, so in practice the document decides.

    That is the fix for the defect ``experiment_plan.md`` §12.2 records: this function used to be
    called with a hard-coded ``"en"`` and the attribute nobody sets, so *every* mention in every
    corpus resolved to English.  The corpora affected are the ones the study is multilingual for —
    1,911 Chinese and 446 Arabic OntoNotes documents were pseudonymised with English surrogates.
    """
    return mention.attributes.get("language", default)
