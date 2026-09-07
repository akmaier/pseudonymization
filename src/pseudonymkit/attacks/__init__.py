"""Leakage attacks (PLAN.md §Measurements/4).

A1 inverts by enumeration and is defined only against unkeyed techniques; A2 needs no inversion at
all and applies to every technique, which is the whole of H1.
"""

from .base import Attack, AttackResult
from .dictionary import DictionaryAttack, candidates_from_inventory, deterministic_inverter
from .frequency import FrequencyAttack, reference_from_counts, spearman

__all__ = [
    "Attack", "AttackResult",
    "DictionaryAttack", "deterministic_inverter", "candidates_from_inventory",
    "FrequencyAttack", "reference_from_counts", "spearman",
]
