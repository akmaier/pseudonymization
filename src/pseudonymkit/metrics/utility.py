"""Task-based utility: per-document scores, paired tests, corrected p-values.

The protocol is fixed by ``experiment_plan.md`` §2.3 and is deliberately *not* the usual one.

**The unit of analysis is the document.**  A condition's result is the **vector of per-document
scores**, and that vector is the primary artefact — everything else is derived from it and can be
recomputed.  There is **no delta, no ratio and no composite scalar across tasks** (AM, 2026-09-08):
collapsing eight tasks into one number destroys exactly the information the study exists to report,
and makes the remaining number impossible to interpret.

**Conditions are paired.**  Every condition is scored on the same documents, so the comparison is
within-document and the tests are paired:

* :func:`wilcoxon_signed_rank` for continuous scores.  F1 is bounded in ``[0, 1]`` and skewed, so a
  t-test's normality assumption is unsafe on precisely the metric we report most.
* :func:`mcnemar` for binary correctness — folder, section and intent classification.

**An effect size stands beside every p-value.**  With n ≈ 1,268 documents almost any difference
reaches ``p < 0.05``, so significance without magnitude is misleading rather than informative.  The
continuous test reports the **median paired difference** and the **rank-biserial correlation**; the
binary test reports the **accuracy difference** and the discordant pair counts that produced it.

**Benjamini–Hochberg across the comparison family.**  Dozens of conditions per task generate
spurious significance by construction; :func:`benjamini_hochberg` attaches a q-value to each
comparison and marks which survive.

**The original-text score is reported beside every condition.**  :class:`UtilityReport` cannot be
built without it, and :meth:`UtilityReport.interpretable` states whether the frozen model was above
chance on the original at all.  A task where it was not is excluded **with the reason recorded**,
never quietly averaged into the rest.

Sign convention throughout: differences are ``condition − reference``, so a **negative** median
difference means the pseudonymised text scored *worse* — utility was lost.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from statistics import median
from typing import Iterable, Literal, Mapping, Sequence

import numpy as np

__all__ = [
    "Kind",
    "ScoreVector",
    "PairedComparison",
    "UtilityReport",
    "compare",
    "benjamini_hochberg",
    "wilcoxon_signed_rank",
    "mcnemar",
    "span_f1",
    "multilabel_micro_f1",
    "exact_match",
    "absolute_error",
    "spearman",
]

Kind = Literal["continuous", "binary"]


# --------------------------------------------------------------------------------------- scorers


def span_f1(
    gold: Iterable[tuple[int, int, str]],
    predicted: Iterable[tuple[int, int, str]],
    typed: bool = True,
) -> float:
    """F1 over exact span matches for **one document**.

    ``typed`` compares ``(start, end, label)``; with ``typed=False`` the label is ignored, which
    separates "found the span" from "found the span and named it right" — the two fail differently
    after pseudonymisation and are worth reporting apart.

    A document with no gold and no prediction scores **1.0**: the system was right that there was
    nothing there.  Gold-empty-but-predicted scores 0.0.
    """
    key = (lambda s: s) if typed else (lambda s: (s[0], s[1]))
    g = {key(s) for s in gold}
    p = {key(s) for s in predicted}
    if not g and not p:
        return 1.0
    overlap = len(g & p)
    if overlap == 0:
        return 0.0
    precision = overlap / len(p)
    recall = overlap / len(g)
    return 2 * precision * recall / (precision + recall)


def multilabel_micro_f1(gold: Iterable[str], predicted: Iterable[str]) -> float:
    """Micro-F1 for one multi-label document — TAB's 30-label ECHR article task."""
    g, p = set(gold), set(predicted)
    if not g and not p:
        return 1.0
    overlap = len(g & p)
    if overlap == 0:
        return 0.0
    precision = overlap / len(p)
    recall = overlap / len(g)
    return 2 * precision * recall / (precision + recall)


def exact_match(gold: object, predicted: object) -> float:
    """1.0 / 0.0 for one document — the binary tasks McNemar is for."""
    return float(gold == predicted)


def absolute_error(gold: float, predicted: float) -> float:
    """``|gold − predicted|`` for one document — the continuous formality target.

    Note the sign flip this implies: for an *error* score, lower is better, so a **positive** median
    difference means the condition did worse.  Record which direction a task's score runs; see
    :attr:`ScoreVector.higher_is_better`.
    """
    return abs(float(gold) - float(predicted))


def spearman(a: Sequence[float], b: Sequence[float]) -> float:
    """Spearman ρ between two score sequences.

    Used as a **corpus-level** summary for formality, never as a per-document score — a rank
    correlation needs a population and is undefined for a single document.
    """
    from scipy.stats import rankdata

    if len(a) != len(b):
        raise ValueError(f"length mismatch: {len(a)} vs {len(b)}")
    if len(a) < 2:
        return float("nan")
    ra, rb = rankdata(a), rankdata(b)
    if np.std(ra) == 0 or np.std(rb) == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


# ---------------------------------------------------------------------------------- score vector


@dataclass(frozen=True, slots=True)
class ScoreVector:
    """One condition's per-document scores on one task — the study's primary artefact.

    ``condition`` names the cell that produced it: the pseudonymisation configuration, or
    ``"original"`` for the untransformed text.  ``doc_ids`` and ``scores`` are parallel and are what
    makes the comparison paired; they are kept in full rather than summarised, so any statistic can
    be recomputed without re-running the model.
    """

    task: str
    condition: str
    doc_ids: tuple[str, ...]
    scores: tuple[float, ...]
    kind: Kind = "continuous"
    higher_is_better: bool = True
    """False for error-style scores, where a smaller number is the better result."""
    metadata: Mapping[str, object] = field(default_factory=dict)
    """Cell configuration, seed, sampling scheme and rate, corpus version, commit — §3."""

    def __post_init__(self) -> None:
        if len(self.doc_ids) != len(self.scores):
            raise ValueError(
                f"{len(self.doc_ids)} doc_ids but {len(self.scores)} scores for "
                f"{self.task}/{self.condition}"
            )
        if len(set(self.doc_ids)) != len(self.doc_ids):
            raise ValueError(f"duplicate doc_ids in {self.task}/{self.condition}")

    @property
    def n(self) -> int:
        return len(self.scores)

    @property
    def mean(self) -> float:
        return float(np.mean(self.scores)) if self.scores else float("nan")

    @property
    def sd(self) -> float:
        """Sample standard deviation (ddof=1) — these are a sample of documents, not a population."""
        return float(np.std(self.scores, ddof=1)) if self.n > 1 else float("nan")

    @property
    def median(self) -> float:
        return float(median(self.scores)) if self.scores else float("nan")

    def paired_with(self, other: ScoreVector) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
        """Align two vectors on the documents they share, in this vector's order.

        Conditions can differ in coverage — a model may have failed on a document under one cell and
        not another — so the intersection is taken explicitly rather than assumed.  The shared
        ``doc_ids`` are returned so a result can record exactly which documents it rests on.
        """
        if self.task != other.task:
            raise ValueError(f"different tasks: {self.task} vs {other.task}")
        index = dict(zip(other.doc_ids, other.scores))
        shared = tuple(d for d in self.doc_ids if d in index)
        mine = dict(zip(self.doc_ids, self.scores))
        return (
            np.array([mine[d] for d in shared], dtype=float),
            np.array([index[d] for d in shared], dtype=float),
            shared,
        )

    def describe(self) -> dict[str, object]:
        """mean / SD / n — the summary line, derived, never stored in place of the vector."""
        return {
            "task": self.task,
            "condition": self.condition,
            "n": self.n,
            "mean": self.mean,
            "sd": self.sd,
            "median": self.median,
            "kind": self.kind,
            "higher_is_better": self.higher_is_better,
            **dict(self.metadata),
        }

    def to_record(self) -> dict[str, object]:
        """The full artefact, for the JSONL on disk."""
        return {**self.describe(), "doc_ids": list(self.doc_ids), "scores": list(self.scores)}


# ----------------------------------------------------------------------------------------- tests


def wilcoxon_signed_rank(
    reference: Sequence[float], condition: Sequence[float]
) -> tuple[float, float, float]:
    """Paired Wilcoxon signed-rank on ``condition − reference``.

    Returns ``(statistic, p_value, rank_biserial)``.  The rank-biserial correlation is
    ``(W⁺ − W⁻) / (W⁺ + W⁻)`` over the non-zero differences: ``+1`` when every document improved,
    ``−1`` when every document got worse, ``0`` at a balanced split.

    Two degenerate cases are handled here rather than left to raise: **no documents** gives all-NaN,
    and **every difference exactly zero** — common when a pseudonymisation cell changes nothing the
    task depends on — gives ``p = 1.0`` and effect ``0.0``, which is the correct answer and not an
    error.
    """
    from scipy.stats import rankdata, wilcoxon

    a = np.asarray(reference, dtype=float)
    b = np.asarray(condition, dtype=float)
    if a.size == 0:
        return (float("nan"), float("nan"), float("nan"))
    differences = b - a
    non_zero = differences[differences != 0]
    if non_zero.size == 0:
        return (0.0, 1.0, 0.0)

    ranks = rankdata(np.abs(non_zero))
    positive = float(ranks[non_zero > 0].sum())
    negative = float(ranks[non_zero < 0].sum())
    total = positive + negative
    rank_biserial = (positive - negative) / total if total else 0.0

    statistic, p_value = wilcoxon(b, a, zero_method="wilcox", alternative="two-sided")
    return (float(statistic), float(p_value), float(rank_biserial))


def mcnemar(
    reference: Sequence[float], condition: Sequence[float]
) -> tuple[float, float, int, int]:
    """Paired McNemar on binary correctness.

    Returns ``(statistic, p_value, b, c)`` where ``b`` counts documents the reference got right and
    the condition got wrong, and ``c`` the reverse.  Only those **discordant pairs** carry
    information; the documents both conditions agreed on cannot distinguish them.

    Below 25 discordant pairs the **exact binomial** test is used, above it the chi-square with
    Edwards' continuity correction — the asymptotic form is unreliable in exactly the small-``b+c``
    regime that a mild utility loss produces.
    """
    from scipy.stats import binomtest, chi2

    a = np.asarray(reference, dtype=float) > 0.5
    d = np.asarray(condition, dtype=float) > 0.5
    if a.size == 0:
        return (float("nan"), float("nan"), 0, 0)
    b = int(np.sum(a & ~d))
    c = int(np.sum(~a & d))
    if b + c == 0:
        return (0.0, 1.0, 0, 0)
    if b + c < 25:
        p_value = binomtest(b, b + c, 0.5, alternative="two-sided").pvalue
        return (float(min(b, c)), float(p_value), b, c)
    statistic = (abs(b - c) - 1) ** 2 / (b + c)
    return (float(statistic), float(chi2.sf(statistic, df=1)), b, c)


@dataclass(frozen=True, slots=True)
class PairedComparison:
    """One condition measured against the original text, on the documents they share."""

    task: str
    reference: str
    condition: str
    test: Literal["wilcoxon", "mcnemar"]
    n: int
    statistic: float
    p_value: float
    effect: float
    effect_name: str
    reference_mean: float
    condition_mean: float
    median_difference: float
    """Median of ``condition − reference``. Negative means the condition scored lower."""
    discordant: tuple[int, int] | None = None
    """McNemar's ``(b, c)``: reference-right/condition-wrong, and the reverse."""
    q_value: float | None = None
    """Benjamini–Hochberg adjusted p, filled in by :func:`benjamini_hochberg`."""
    significant: bool | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        return {
            "task": self.task,
            "reference": self.reference,
            "condition": self.condition,
            "test": self.test,
            "n": self.n,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "q_value": self.q_value,
            "significant": self.significant,
            "effect": self.effect,
            "effect_name": self.effect_name,
            "reference_mean": self.reference_mean,
            "condition_mean": self.condition_mean,
            "median_difference": self.median_difference,
            "discordant": list(self.discordant) if self.discordant else None,
            **dict(self.metadata),
        }


def compare(reference: ScoreVector, condition: ScoreVector) -> PairedComparison:
    """Test one condition against the original-text scores, picking the test from the score kind.

    The reference's ``kind`` decides: ``"binary"`` takes McNemar, ``"continuous"`` Wilcoxon.  The
    two vectors must agree on kind — silently applying a rank test to 0/1 correctness would give a
    p-value that looks fine and answers a different question.
    """
    if reference.kind != condition.kind:
        raise ValueError(
            f"kind mismatch: reference {reference.kind!r} vs condition {condition.kind!r}"
        )
    a, b, shared = reference.paired_with(condition)
    differences = b - a
    median_difference = float(median(differences)) if differences.size else float("nan")

    if reference.kind == "binary":
        statistic, p_value, discordant_b, discordant_c = mcnemar(a, b)
        n = int(a.size)
        effect = float(b.mean() - a.mean()) if n else float("nan")
        return PairedComparison(
            task=reference.task, reference=reference.condition, condition=condition.condition,
            test="mcnemar", n=n, statistic=statistic, p_value=p_value,
            effect=effect, effect_name="accuracy_difference",
            reference_mean=float(a.mean()) if n else float("nan"),
            condition_mean=float(b.mean()) if n else float("nan"),
            median_difference=median_difference,
            discordant=(discordant_b, discordant_c),
            metadata={"n_shared": len(shared)},
        )

    statistic, p_value, rank_biserial = wilcoxon_signed_rank(a, b)
    n = int(a.size)
    return PairedComparison(
        task=reference.task, reference=reference.condition, condition=condition.condition,
        test="wilcoxon", n=n, statistic=statistic, p_value=p_value,
        effect=rank_biserial, effect_name="rank_biserial",
        reference_mean=float(a.mean()) if n else float("nan"),
        condition_mean=float(b.mean()) if n else float("nan"),
        median_difference=median_difference,
        metadata={"n_shared": len(shared)},
    )


def benjamini_hochberg(
    comparisons: Sequence[PairedComparison], alpha: float = 0.05
) -> tuple[PairedComparison, ...]:
    """Attach BH-adjusted q-values across one comparison family, preserving input order.

    The family is the set of comparisons reported together — every condition on one task, normally.
    Choosing the family is a reporting decision, so it is the caller's: pass the comparisons that
    will appear in the same panel, and no others.

    Comparisons whose p-value is NaN (an empty or degenerate cell) are carried through untouched and
    excluded from the correction; counting them in ``m`` would penalise every other comparison for a
    test that was never run.
    """
    indexed = [(i, c) for i, c in enumerate(comparisons) if not math.isnan(c.p_value)]
    m = len(indexed)
    if m == 0:
        return tuple(comparisons)

    order = sorted(indexed, key=lambda pair: pair[1].p_value)
    q_values: dict[int, float] = {}
    running = 1.0
    for rank in range(m, 0, -1):
        index, comparison = order[rank - 1]
        running = min(running, comparison.p_value * m / rank)
        q_values[index] = running

    out = list(comparisons)
    for index, q in q_values.items():
        out[index] = replace(out[index], q_value=q, significant=q <= alpha)
    return tuple(out)


# ---------------------------------------------------------------------------------------- report


@dataclass(frozen=True, slots=True)
class UtilityReport:
    """One task's original-text scores plus every condition measured against them.

    Constructing it without a reference is impossible by design: ``experiment_plan.md`` §2.3
    requires the original-text score beside every condition, because a condition's absolute number
    means nothing until it is known what the frozen model could do on the untransformed text.
    """

    task: str
    reference: ScoreVector
    conditions: tuple[ScoreVector, ...]
    comparisons: tuple[PairedComparison, ...]
    chance_level: float | None = None
    """The score a trivial baseline reaches. Below it, the task is uninterpretable — see
    :meth:`interpretable`."""

    @classmethod
    def build(
        cls,
        reference: ScoreVector,
        conditions: Sequence[ScoreVector],
        alpha: float = 0.05,
        chance_level: float | None = None,
    ) -> UtilityReport:
        if reference.condition != "original":
            raise ValueError(
                f"the reference must be the original text, got {reference.condition!r}"
            )
        comparisons = benjamini_hochberg(
            [compare(reference, c) for c in conditions], alpha=alpha
        )
        return cls(reference.task, reference, tuple(conditions), comparisons, chance_level)

    def interpretable(self) -> tuple[bool, str]:
        """Whether the frozen model cleared chance on the **original** text.

        Returns the verdict and the reason, so an excluded task is reported with its reason attached
        rather than dropped from a table with no trace (``experiment_plan.md`` §2.3).
        """
        if self.chance_level is None:
            return (True, "no chance level declared for this task")
        if math.isnan(self.reference.mean):
            return (False, "no reference scores")
        if self.reference.mean <= self.chance_level:
            return (
                False,
                f"frozen model scored {self.reference.mean:.3f} on the original text, at or below "
                f"the {self.chance_level:.3f} chance level: differences between conditions are not "
                f"interpretable as utility",
            )
        return (
            True,
            f"reference {self.reference.mean:.3f} > chance {self.chance_level:.3f}",
        )

    def rows(self) -> tuple[dict[str, object], ...]:
        """One row per condition, with the reference row first — the shape of a results panel."""
        by_condition = {c.condition: c for c in self.conditions}
        out = [{**self.reference.describe(), "comparison": None}]
        for comparison in self.comparisons:
            vector = by_condition[comparison.condition]
            out.append({**vector.describe(), "comparison": comparison.to_record()})
        return tuple(out)

    def to_record(self) -> dict[str, object]:
        interpretable, reason = self.interpretable()
        return {
            "task": self.task,
            "interpretable": interpretable,
            "interpretable_reason": reason,
            "chance_level": self.chance_level,
            "reference": self.reference.to_record(),
            "conditions": [c.to_record() for c in self.conditions],
            "comparisons": [c.to_record() for c in self.comparisons],
        }
