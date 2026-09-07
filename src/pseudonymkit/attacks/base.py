"""Attacks against a pseudonymised corpus, and what they all report.

Every attack in this study inverts **pseudonyms we generated ourselves**.  None attempts to recover
the identity of a real person from a corpus, and the distinction is not cosmetic: it is what keeps
the leakage measurements inside the data agreements the corpora are held under.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, runtime_checkable

__all__ = ["AttackResult", "Attack"]


@dataclass(frozen=True, slots=True)
class AttackResult:
    """What one attack recovered from one pseudonymised corpus."""

    attack: str
    entity_type: str
    policy: str
    technique: str
    candidates: int
    """Distinct pseudonyms the attacker had to invert."""
    recovered_top1: int
    recovered_top5: int
    accuracy_top1: float
    accuracy_top5: float
    rank_correlation: float | None = None
    """Spearman rho between pseudonym frequency and true frequency; the leak itself."""
    by_frequency_band: Mapping[str, float] = field(default_factory=dict)
    """Top-1 accuracy per frequency band — the curve the hash-vs-HMAC question turns on."""
    notes: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "attack": self.attack,
            "entity_type": self.entity_type,
            "policy": self.policy,
            "technique": self.technique,
            "candidates": self.candidates,
            "recovered_top1": self.recovered_top1,
            "recovered_top5": self.recovered_top5,
            "accuracy_top1": self.accuracy_top1,
            "accuracy_top5": self.accuracy_top5,
            "rank_correlation": self.rank_correlation,
            "by_frequency_band": dict(self.by_frequency_band),
            "notes": self.notes,
        }


@runtime_checkable
class Attack(Protocol):
    """Attempts to invert a pseudonymisation."""

    name: str
    requires_unkeyed: bool
    """Whether the attack needs the function to be publicly computable.

    A1 does — it applies the function to a dictionary of candidates, which is impossible without
    the key.  A2 does not, and that asymmetry is the whole of H1.
    """
