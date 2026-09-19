"""Stability metrics: collision, fragmentation and drift.

These are pure set operations over ``gold chain -> assignments``.  All three must be read against
the policy in force, because what is a defect under one policy is the definition of another:

===================  ===============  ====================  =================
metric               deterministic    document-randomised   fully-randomised
===================  ===============  ====================  =================
collision            defect           defect                meaningless
fragmentation        defect           defect                by design
drift                defect           **by design**         by design
===================  ===============  ====================  =================

Reporting a single "fragmentation rate" across policies would be a category error, so
:class:`StabilityReport` carries all three separately and records the policy alongside them.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping

from ..domain import Mention
from ..engine import PseudonymisedCorpus, PseudonymisedDocument

__all__ = ["StabilityReport", "evaluate_stability"]


@dataclass(frozen=True, slots=True)
class StabilityReport:
    """Stability of one cell, for one entity type."""

    entity_type: str
    policy: str
    chains: int
    """Gold co-reference chains observed (entities with at least one replaced mention)."""
    collisions: int
    """Distinct gold chains that share a pseudonym surface within a scope."""
    collision_rate: float
    fragmented_chains: int
    """Gold chains that received more than one pseudonym within a single document."""
    fragmentation_rate: float
    drifting_chains: int | None
    """Gold chains whose pseudonym differs between documents.

    ``None`` unless the scoring ran cross-document, and that is not a formality.  Scored *within* a
    document the chain key already carries the document id, so "the same chain in two documents"
    cannot occur and this counter degenerates to :attr:`fragmented_chains` exactly — same numerator,
    same denominator, a different name.  TAB's first stability run wrote ``drift_rate 0.1462``
    beside ``fragmentation_rate 0.1462`` for that reason, and on a corpus with no cross-document
    identity that duplicate was the only drift number on disk.  §2 says results are artefacts on
    disk rather than claims in prose, so the artefact has to be as careful as the log line.
    """
    drift_rate: float | None
    surfaces: int
    cross_document: bool = False
    """Whether identity was resolved across documents.  Decides whether drift means anything."""

    def as_dict(self) -> dict[str, object]:
        return {
            "entity_type": self.entity_type,
            "policy": self.policy,
            "chains": self.chains,
            "collisions": self.collisions,
            "collision_rate": self.collision_rate,
            "fragmented_chains": self.fragmented_chains,
            "fragmentation_rate": self.fragmentation_rate,
            "drifting_chains": self.drifting_chains,
            "drift_rate": self.drift_rate,
            "surfaces": self.surfaces,
            "cross_document": self.cross_document,
            "drift_note": None if self.cross_document else (
                "not computable: identity is document-scoped in this scope, so drift would be "
                "fragmentation under another name"
            ),
        }


def _chain_id(doc_id: str, mention: Mention, cross_document: bool) -> str | None:
    """Identity of the entity a mention belongs to.

    Within a document the gold co-reference id suffices.  Across documents it does not — TAB's
    ``entity_id`` is document-scoped — so cross-document identity has to come from the corpus
    (a patient id, a mailbox owner) and is only used when ``cross_document`` is set.
    """
    if mention.gold_entity_id is None:
        return None
    return mention.gold_entity_id if cross_document else f"{doc_id}\x1f{mention.gold_entity_id}"


def evaluate_stability(
    result: PseudonymisedCorpus,
    entity_type: str,
    policy: str,
    cross_document: bool = False,
) -> StabilityReport:
    """Score one pseudonymised corpus for one entity type.

    Mentions without a gold chain id are ignored: stability is defined against ground truth, and a
    corpus without co-reference annotation cannot enter a stability cell.
    """
    surfaces_per_chain: dict[str, set[str]] = defaultdict(set)
    surfaces_per_chain_doc: dict[tuple[str, str], set[str]] = defaultdict(set)
    chains_per_surface: dict[tuple[str, str], set[str]] = defaultdict(set)

    for pdoc in result.documents:
        doc_id = pdoc.document.doc_id
        by_span = _assignments_by_mention(pdoc)
        for mention, assignment in by_span:
            if mention.type != entity_type:
                continue
            chain = _chain_id(doc_id, mention, cross_document)
            if chain is None:
                continue
            surfaces_per_chain[chain].add(assignment.surface)
            surfaces_per_chain_doc[(doc_id, chain)].add(assignment.surface)
            chains_per_surface[(doc_id, assignment.surface)].add(chain)

    chains = len(surfaces_per_chain)
    fragmented = sum(1 for s in surfaces_per_chain_doc.values() if len(s) > 1)
    drifting = sum(1 for s in surfaces_per_chain.values() if len(s) > 1)
    collisions = sum(1 for c in chains_per_surface.values() if len(c) > 1)
    n_doc_chains = max(len(surfaces_per_chain_doc), 1)

    return StabilityReport(
        entity_type=entity_type,
        policy=policy,
        chains=chains,
        collisions=collisions,
        collision_rate=collisions / max(len(chains_per_surface), 1),
        fragmented_chains=fragmented,
        fragmentation_rate=fragmented / n_doc_chains,
        drifting_chains=drifting if cross_document else None,
        drift_rate=(drifting / max(chains, 1)) if cross_document else None,
        surfaces=len({s for ss in surfaces_per_chain.values() for s in ss}),
        cross_document=cross_document,
    )


def _assignments_by_mention(
    pdoc: PseudonymisedDocument,
) -> Iterable[tuple[Mention, object]]:
    """Pair each replaced mention with the assignment it received, in document order."""
    ordered = sorted(pdoc.document.mentions, key=lambda m: (m.span.start, -m.span.length))
    skipped = {(m.doc_id, m.mention_id) for m in pdoc.skipped}
    replaced = [m for m in ordered if (m.doc_id, m.mention_id) not in skipped]
    return zip(replaced, pdoc.assignments)


def rates_by_type(
    result: PseudonymisedCorpus, policy: str, types: Iterable[str], cross_document: bool = False
) -> Mapping[str, StabilityReport]:
    """Convenience: stability for several entity types at once."""
    return {t: evaluate_stability(result, t, policy, cross_document) for t in types}
