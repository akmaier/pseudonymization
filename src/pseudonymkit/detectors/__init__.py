"""Detectors (axis D) and the rules that combine them.

Importing this package registers every detector level in :data:`DETECTORS`.  It is safe to do so
without any model installed: each detector imports its own framework — presidio, gliner,
transformers, flair — inside ``load()``, so a machine with none of them can still build a
configuration, read the cache and score an ensemble.
"""

from .base import DETECTORS, Detector, DetectorOutput, GoldSpans, StaticDetector
from .combinators import COMBINATORS, Combinator, cluster_spans, combination_grid
from .domain import PrivacyTagger
from .finetuned import FINETUNED_MODELS, TokenClassificationDetector
from .rule import PresidioDetector
from .runner import RunReport, run_detector
from .zeroshot import GLINER_MODELS, GlinerDetector

__all__ = [
    "DETECTORS", "Detector", "DetectorOutput", "GoldSpans", "StaticDetector",
    "COMBINATORS", "Combinator", "cluster_spans", "combination_grid",
    "PresidioDetector", "GlinerDetector", "GLINER_MODELS",
    "TokenClassificationDetector", "FINETUNED_MODELS", "PrivacyTagger",
    "RunReport", "run_detector",
]
