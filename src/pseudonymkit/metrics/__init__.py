"""Metrics: stability, utility, and (later) detection."""

from .stability import StabilityReport, evaluate_stability, rates_by_type
from .utility import (
    PairedComparison,
    ScoreVector,
    UtilityReport,
    absolute_error,
    benjamini_hochberg,
    compare,
    exact_match,
    mcnemar,
    multilabel_micro_f1,
    span_f1,
    spearman,
    wilcoxon_signed_rank,
)

__all__ = [
    "StabilityReport",
    "evaluate_stability",
    "rates_by_type",
    "PairedComparison",
    "ScoreVector",
    "UtilityReport",
    "absolute_error",
    "benjamini_hochberg",
    "compare",
    "exact_match",
    "mcnemar",
    "multilabel_micro_f1",
    "span_f1",
    "spearman",
    "wilcoxon_signed_rank",
]
