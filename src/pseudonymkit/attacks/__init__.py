"""Leakage attacks (experiment_plan.md §8.4).

A1 inverts by enumeration and is defined only against unkeyed techniques.  A2 needs no inversion at
all and applies to every technique, which is the whole of H1.  A3 and A5 attack what pseudonymisation
cannot remove -- the facts and relations around an entity -- with a fixed and a learned similarity
respectively, so the gap between them measures what learning buys the adversary.  A4 asks a language
model the same question in a bounded form: rank a candidate list built out of the corpus itself.

**A3, A4 and A5 run on condition A as well** (§8.4).  Condition A is the ceiling -- what the
adversary recovers with no protection at all -- and without it a leakage rate on B or C has no scale,
exactly as §8.3 requires the original-text score beside every utility condition.  No attack needs a
special case for it: :class:`pseudonymkit.conditions.Unmodified` produces a
:class:`~pseudonymkit.engine.PseudonymisedCorpus` whose text is the corpus's own and whose
assignments map each mention to its own surface, so :func:`build_queries`, :func:`truth_map` and
:func:`build_items` all read it unchanged.
"""

from .base import Attack, AttackResult
from .dictionary import DictionaryAttack, candidates_from_inventory, deterministic_inverter
from .frequency import A2Score, FrequencyAttack, Prior, degrade, observe, reference_from_counts, spearman
from .profiles import (
    EntityProfile, build_gallery, build_queries, disjoint_document_split, truth_map,
)
from .candidates import (
    A4Report, Candidate, CandidateRanker, CandidateSet, LlmCandidateRanker, build_items,
)
from .candidates import score as score_candidates
from .relational import LearnedLinkage, ReIdResult, StructuralLinkage, featurise

__all__ = [
    "A2Score", "Prior", "degrade", "observe",
    "Attack", "AttackResult",
    "DictionaryAttack", "deterministic_inverter", "candidates_from_inventory",
    "FrequencyAttack", "reference_from_counts", "spearman",
    "EntityProfile", "build_gallery", "build_queries", "truth_map", "disjoint_document_split",
    "StructuralLinkage", "LearnedLinkage", "ReIdResult", "featurise",
    "Candidate", "CandidateSet", "CandidateRanker", "A4Report", "build_items",
    "score_candidates", "LlmCandidateRanker",
]
