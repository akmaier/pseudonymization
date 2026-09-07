"""Leakage attacks (PLAN.md §Measurements/4). A2 first: it is where H1 lives."""

from .base import Attack, AttackResult
from .frequency import FrequencyAttack, reference_from_counts, spearman

__all__ = ["Attack", "AttackResult", "FrequencyAttack", "reference_from_counts", "spearman"]
