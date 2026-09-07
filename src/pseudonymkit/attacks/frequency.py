"""A2 — frequency analysis.

The attack that needs no inversion at all.  Under a deterministic policy every occurrence of an
entity becomes the same pseudonym, so the frequency distribution of the pseudonyms is the frequency
distribution of the real entities, merely relabelled.  Ranking both and aligning them recovers the
mapping without touching the cryptography.

This is why H1 predicts that hash, HMAC and AES-SIV leak comparably: **A2 is indifferent to the
technique.**  If it succeeds, the axis practitioners agonise over is not the one that matters.

On optimal assignment: the attacker is matching two one-dimensional sequences under a cost that
increases with the difference in frequency.  For that problem the sorted (rank) alignment *is* the
optimal assignment, so a Hungarian solver would return the same answer at far greater cost.  The
implementation therefore ranks, and says so rather than leaving the reader to wonder.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping, Sequence

from ..engine import PseudonymisedCorpus
from .base import AttackResult

__all__ = ["FrequencyAttack", "spearman"]

_BANDS: tuple[tuple[str, int, int], ...] = (
    ("1", 1, 1),
    ("2-4", 2, 4),
    ("5-19", 5, 19),
    ("20+", 20, 1 << 30),
)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman's rho, with average ranks for ties. ``None`` when it is undefined."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def _band(count: int) -> str:
    for label, low, high in _BANDS:
        if low <= count <= high:
            return label
    return _BANDS[-1][0]


class FrequencyAttack:
    """Rank pseudonyms by frequency, rank candidate names by frequency, align.

    The reference distribution is the attacker's prior over real names.  Two settings matter and are
    reported:

    * ``reference=None`` — the attacker knows the corpus's own name distribution.  An upper bound,
      and the honest way to ask "if frequency is knowable, is the scheme broken?".
    * ``reference=<mapping>`` — an external gazetteer, e.g. census surname frequencies.  The
      realistic setting, and weaker, because corpus frequency and population frequency differ.
    """

    name = "a2_frequency"
    requires_unkeyed = False

    def __init__(self, reference: Mapping[str, float] | None = None) -> None:
        self._reference = dict(reference) if reference is not None else None

    def run(
        self,
        result: PseudonymisedCorpus,
        entity_type: str,
        policy: str,
        technique: str,
    ) -> AttackResult:
        # Each of these walks the corpus exactly once; everything below reuses them.  Recomputing
        # a corpus-wide Counter inside the scoring loop turns the attack quadratic, which on TAB's
        # 8,700 PERSON entities is the difference between a second and an hour.
        counts = self._pseudonym_counts(result, entity_type)
        truth = self._truth(result, entity_type)
        entity_counts = self._entity_counts(result, entity_type)
        if not counts:
            return AttackResult(
                self.name, entity_type, policy, technique, 0, 0, 0, 0.0, 0.0,
                notes="no mentions of this type",
            )

        # The attacker's view: pseudonyms ordered by how often they occur.
        observed = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

        # The attacker's prior: candidate names ordered by expected frequency.
        if self._reference is None:
            prior = sorted(entity_counts.items(), key=lambda kv: (-kv[1], kv[0]))
            note = "reference: corpus-internal (upper bound)"
        else:
            prior = sorted(self._reference.items(), key=lambda kv: (-kv[1], kv[0]))
            note = "reference: external gazetteer"

        guesses = [name for name, _ in prior]
        top1 = top5 = 0
        per_band: dict[str, list[int]] = {}
        for rank, (surface, count) in enumerate(observed):
            true_key = truth.get(surface)
            if true_key is None:
                continue          # a pseudonym shared by several entities: no single truth
            window = guesses[max(0, rank - 2) : rank + 3]
            hit1 = rank < len(guesses) and guesses[rank] == true_key
            hit5 = true_key in window
            top1 += hit1
            top5 += hit5
            per_band.setdefault(_band(count), []).append(int(hit1))

        n = len(observed)
        xs = [c for _, c in observed]
        ys = [entity_counts.get(truth.get(s, ""), 0) for s, _ in observed]
        return AttackResult(
            attack=self.name,
            entity_type=entity_type,
            policy=policy,
            technique=technique,
            candidates=n,
            recovered_top1=top1,
            recovered_top5=top5,
            accuracy_top1=top1 / n,
            accuracy_top5=top5 / n,
            rank_correlation=spearman(xs, ys),
            by_frequency_band={k: sum(v) / len(v) for k, v in sorted(per_band.items())},
            notes=note,
        )

    @staticmethod
    def _pseudonym_counts(result: PseudonymisedCorpus, entity_type: str) -> Counter[str]:
        """How often each pseudonym appears — everything the attacker can see."""
        counts: Counter[str] = Counter()
        for pdoc in result.documents:
            for a in pdoc.assignments:
                if a.entity_type == entity_type:
                    counts[a.surface] += 1
        return counts

    @staticmethod
    def _entity_counts(result: PseudonymisedCorpus, entity_type: str) -> Counter[str]:
        """How often each real entity key appears — the ground truth for scoring."""
        counts: Counter[str] = Counter()
        for pdoc in result.documents:
            for a in pdoc.assignments:
                if a.entity_type == entity_type:
                    counts[a.entity_key] += 1
        return counts

    @staticmethod
    def _truth(result: PseudonymisedCorpus, entity_type: str) -> dict[str, str]:
        """pseudonym -> the entity key behind it, omitting pseudonyms shared by several keys."""
        keys: dict[str, set[str]] = {}
        for pdoc in result.documents:
            for a in pdoc.assignments:
                if a.entity_type == entity_type:
                    keys.setdefault(a.surface, set()).add(a.entity_key)
        return {surface: next(iter(ks)) for surface, ks in keys.items() if len(ks) == 1}


def reference_from_counts(pairs: Iterable[tuple[str, float]]) -> dict[str, float]:
    """Build an external reference distribution from ``(name, frequency)`` pairs."""
    return {name: float(freq) for name, freq in pairs}
