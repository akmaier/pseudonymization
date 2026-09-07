"""Detectors (axis D) and the rules that combine them."""

from .base import DETECTORS, Detector, DetectorOutput, GoldSpans, StaticDetector
from .combinators import COMBINATORS, Combinator, cluster_spans, combination_grid

__all__ = [
    "DETECTORS", "Detector", "DetectorOutput", "GoldSpans", "StaticDetector",
    "COMBINATORS", "Combinator", "cluster_spans", "combination_grid",
]
