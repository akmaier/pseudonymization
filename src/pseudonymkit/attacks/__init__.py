"""Leakage attacks (PLAN.md §Measurements/4).

A1 inverts by enumeration and is defined only against unkeyed techniques.  A2 needs no inversion at
all and applies to every technique, which is the whole of H1.  A3 and A5 attack what pseudonymisation
cannot remove -- the facts and relations around an entity -- with a fixed and a learned similarity
respectively, so the gap between them measures what learning buys the adversary.
"""

from .base import Attack, AttackResult
from .dictionary import DictionaryAttack, candidates_from_inventory, deterministic_inverter
from .frequency import FrequencyAttack, reference_from_counts, spearman
from .profiles import EntityProfile, build_gallery, build_queries, truth_map
from .relational import LearnedLinkage, ReIdResult, StructuralLinkage, featurise

__all__ = [
    "Attack", "AttackResult",
    "DictionaryAttack", "deterministic_inverter", "candidates_from_inventory",
    "FrequencyAttack", "reference_from_counts", "spearman",
    "EntityProfile", "build_gallery", "build_queries", "truth_map",
    "StructuralLinkage", "LearnedLinkage", "ReIdResult", "featurise",
]
