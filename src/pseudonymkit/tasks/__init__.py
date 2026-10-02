"""Utility task runners (``experiment_plan.md`` §8.3).

The statistics layer — score vectors, Wilcoxon, McNemar, Benjamini-Hochberg — lives in
:mod:`pseudonymkit.metrics.utility`.  This package is what calls it: one runner per task in §8.3's
table, each producing a per-document :class:`~pseudonymkit.metrics.utility.ScoreVector` for one
condition, and one frozen scorer per task shape.
"""

from .base import (
    CoreferenceResolver,
    MultiLabelClassifier,
    Regressor,
    SingleLabelClassifier,
    SpanExtractor,
    TaskModel,
    scored,
)
from .linear import (
    Artefact,
    TfidfLogisticClassifier,
    TfidfLogisticTagger,
    load_artefact,
    save_artefact,
    split_documents,
    train_single_label_classifier,
    train_span_tagger,
)
from .runners import (
    coreference,
    echr_articles,
    folder_classification,
    formality,
    label_set,
    medication_ie,
    ner_agreement,
    section_classification,
)

__all__ = [
    "CoreferenceResolver", "MultiLabelClassifier", "SingleLabelClassifier", "SpanExtractor",
    "Regressor", "TaskModel", "scored",
    "coreference", "echr_articles", "medication_ie", "section_classification",
    "folder_classification", "formality", "ner_agreement", "label_set",
    # The trained-and-frozen linear scorers of plan §8.5 — same ports, no gateway.
    "Artefact", "TfidfLogisticClassifier", "TfidfLogisticTagger", "load_artefact",
    "save_artefact", "split_documents", "train_single_label_classifier", "train_span_tagger",
]
