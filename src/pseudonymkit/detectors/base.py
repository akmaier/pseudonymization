"""Axis D: detectors, and the port every detector implements.

The detector is not the independent variable of this study, so what matters here is that
rule-based, fine-tuned, zero-shot, domain-specific and LLM detectors are interchangeable behind
one interface, and that their outputs can be *combined*.  The combination is the interesting part:
the group's own ensembling used LLMs only, and whether classical detectors add anything to an LLM
ensemble is an open question this package is built to answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

from ..domain import Document, Span
from ..registry import Registry

__all__ = ["Detector", "DetectorOutput", "DETECTORS", "GoldSpans"]


@dataclass(frozen=True, slots=True)
class DetectorOutput:
    """Spans one detector found in one document."""

    doc_id: str
    detector: str
    spans: tuple[Span, ...]

    def of_type(self, entity_type: str) -> tuple[Span, ...]:
        return tuple(s for s in self.spans if s.type == entity_type)


@runtime_checkable
class Detector(Protocol):
    """Finds candidate spans in a document."""

    name: str
    family: str
    """rule | ner | zeroshot | domain | llm | oracle — the axis-D family, reported with results."""

    def detect(self, document: Document) -> DetectorOutput: ...


DETECTORS: Registry[Detector] = Registry("detector")


@DETECTORS.register("gold")
class GoldSpans:
    """The oracle: returns the corpus's own annotations.

    Essential rather than decorative.  It is what separates detector error from pseudonymisation
    error; without it every downstream number is confounded by a name detector that the 2026
    cross-lingual evaluations put at F1 0.40.
    """

    name = "gold"
    family = "oracle"

    def detect(self, document: Document) -> DetectorOutput:
        return DetectorOutput(
            doc_id=document.doc_id,
            detector=self.name,
            spans=tuple(m.span for m in document.mentions),
        )


class StaticDetector:
    """A detector that replays pre-computed spans. Used for tests and for cached model output."""

    family = "static"

    def __init__(self, name: str, spans_by_doc: dict[str, Sequence[Span]], family: str = "static"):
        self.name = name
        self.family = family
        self._spans = {k: tuple(v) for k, v in spans_by_doc.items()}

    def detect(self, document: Document) -> DetectorOutput:
        return DetectorOutput(document.doc_id, self.name, self._spans.get(document.doc_id, ()))
