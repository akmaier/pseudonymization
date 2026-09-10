"""The ports a utility task is scored through, and the protocol every runner obeys.

``experiment_plan.md`` §8.3 fixes the measurement protocol, and it is deliberately not the usual one:

* **The unit of analysis is the document.**  A condition's result is the *vector* of per-document
  scores, and that vector is the primary artefact.  Every runner here returns a
  :class:`~pseudonymkit.metrics.utility.ScoreVector` and nothing else — no delta, no ratio, no
  composite scalar across tasks (AM, 2026-09-08).
* **The models are frozen.**  Nothing here is trained.  A TrustFMI audience prompts a foundation
  model over a corpus rather than fine-tuning an encoder on one, so *degradation at fixed weights* is
  the measurement that matches the deployment pattern.  (The A5 attacker is trained; that asymmetry
  is deliberate and belongs to §8.4, not here.)
* **One fixed scorer model is named in every result row.**  Every runner writes the model's name into
  the score vector's metadata, so a row can never be quoted without saying what produced it.

## Why the ports are shaped by the task rather than by the model

There are five: resolve co-reference, assign several labels, assign one label, extract typed spans,
predict a number.  A model that can do more than one implements more than one; a model that can do
none of them is not a scorer for these tasks.  Shaping them by task is what lets the runner be
written once against an interface, and lets a test drive a runner with a five-line stand-in instead
of a foundation model.

## The offset problem, once

Gold is annotated against the **original** text.  The frozen model reads the **condition's** text.
Under B and C those two disagree by every replacement made, so a runner that compares them directly
reports a utility loss that is really an offset drift.  Every span-based runner therefore maps gold
forward through :class:`pseudonymkit.engine.OffsetMap` before scoring.  Under condition A the map is
the identity, which is why A can be run through the same code path rather than special-cased.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Protocol, Sequence, runtime_checkable

from ..metrics.utility import Kind, ScoreVector

__all__ = [
    "CoreferenceResolver",
    "MultiLabelClassifier",
    "SingleLabelClassifier",
    "SpanExtractor",
    "Regressor",
    "TaskModel",
    "scored",
]


@runtime_checkable
class TaskModel(Protocol):
    """Anything that scores a utility task.  ``name`` is what the result row records."""

    name: str


@runtime_checkable
class CoreferenceResolver(TaskModel, Protocol):
    """Clusters of character spans over one text — the co-reference task (TAB, OntoNotes)."""

    def resolve(self, text: str) -> Sequence[Sequence[tuple[int, int]]]: ...


@runtime_checkable
class MultiLabelClassifier(TaskModel, Protocol):
    """Zero or more labels from a closed set — TAB's 30-label ECHR article task."""

    def classify(self, text: str, labels: Sequence[str]) -> Sequence[str]: ...


@runtime_checkable
class SingleLabelClassifier(TaskModel, Protocol):
    """Exactly one label from a closed set — Enron folders, CARDIO:DE sections."""

    def classify(self, text: str, labels: Sequence[str]) -> str: ...


@runtime_checkable
class SpanExtractor(TaskModel, Protocol):
    """Typed character spans — CARDIO:DE medication IE."""

    def extract(self, text: str, classes: Sequence[str]) -> Sequence[tuple[int, int, str]]: ...


@runtime_checkable
class Regressor(TaskModel, Protocol):
    """A number per document — CodEAlltag formality."""

    def predict(self, text: str) -> float: ...


def scored(
    task: str,
    condition: str,
    scores: Iterable[tuple[str, float]],
    *,
    model: str,
    kind: Kind = "continuous",
    higher_is_better: bool = True,
    metadata: Mapping[str, object] | None = None,
    skipped: Mapping[str, int] | None = None,
) -> ScoreVector:
    """Assemble a :class:`ScoreVector` with the provenance §9 requires on every result row.

    ``skipped`` records documents the task could not be scored on and why — a letter with no gold
    medication span, a judgment whose co-reference gold is all singletons.  They are excluded from
    the vector rather than entered as zeros: a zero says the model failed, and a document where
    nothing could have gone wrong would then drag a condition's mean down for no reason.  The count
    travels with the vector so the exclusion is visible in the results rather than in a log.
    """
    pairs = list(scores)
    return ScoreVector(
        task=task,
        condition=condition,
        doc_ids=tuple(doc_id for doc_id, _ in pairs),
        scores=tuple(float(score) for _, score in pairs),
        kind=kind,
        higher_is_better=higher_is_better,
        metadata={
            "scorer": model,
            **({"skipped": dict(skipped)} if skipped else {}),
            **dict(metadata or {}),
        },
    )
