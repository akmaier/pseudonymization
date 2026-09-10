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

__all__ = ["Pseudonymiser", "PseudonymisedDocument", "PseudonymisedCorpus"]


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
