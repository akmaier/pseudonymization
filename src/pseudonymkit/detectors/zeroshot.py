"""Axis D, zero-shot level: GLiNER.

Two checkpoints, both fixed by ``experiment_plan.md`` §14: ``urchade/gliner_multi-v2.1``, a general
multilingual zero-shot NER, and ``urchade/gliner_multi_pii-v1``, the same architecture tuned for
personally identifying information.  They are separate levels of axis D, not a choice between two
ways of doing one thing, and both are run.

**Prompted with the eight harmonised labels directly.**  §10's mapping table gives GLiNER the entry
*"open — the label set is ours"*, so unlike every other detector there is no translation step: the
model is asked for PERSON, LOC, ORG, DATETIME, CODE, DEMOGRAPHIC, QUANTITY and MISC, and what it
returns is already on the harmonised grid.  Two consequences are worth stating rather than
discovering later:

* MISC is prompted for because §10 says *the eight*.  Asking a zero-shot model for a residual class
  is unusual and its behaviour there is a measurement, not a defect.
* If GLiNER returns anything that is not one of the eight, that is an invented category and the
  taxonomy counts it (:class:`pseudonymkit.taxonomy.Harmoniser`) exactly as it counts one from any
  other detector.

**Windowing is a correctness requirement, not a speed one.**  GLiNER v2.1's encoder is trained at
roughly 384 tokens.  Handed a TAB judgment whole it does not fail — it returns entities from the
beginning of the text and nothing from the rest, which reads downstream as a detector with poor
recall on long documents rather than as a truncation.  :func:`~.alignment.text_windows` cuts the
document with an overlap so an entity on a boundary is seen whole in at least one window, and
:func:`~.alignment.dedupe_spans` removes the duplicates that produces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from ..domain import Document, Span
from ..taxonomy import HARMONISED, harmonise
from .alignment import dedupe_spans, text_windows
from .base import DETECTORS, DetectorOutput

__all__ = ["GlinerDetector", "GLINER_MODELS"]

GLINER_MODELS: tuple[str, ...] = (
    "urchade/gliner_multi-v2.1",
    "urchade/gliner_multi_pii-v1",
)
"""The two checkpoints §14 fixes.  Both are levels of axis D and both are run."""


@DETECTORS.register("gliner")
@dataclass
class GlinerDetector:
    """One GLiNER checkpoint, prompted with the harmonised label set.

    ``name`` carries the checkpoint id, so the cache and every results row say which of the two
    produced a span; the detector *family* is what H5 groups by.
    """

    model: str = GLINER_MODELS[0]
    labels: Sequence[str] = HARMONISED
    threshold: float = 0.5
    """GLiNER's own default.  Reported with the run; the ensemble, not this class, decides how much
    precision to trade for recall (§8.1)."""
    max_chars: int = 1200
    """About 300 word pieces — inside the encoder's training length with room for the label set."""
    overlap: int = 200
    device: str | None = None
    family: str = "zeroshot"
    _model: Any = field(default=None, init=False, repr=False)

    @property
    def name(self) -> str:
        return f"gliner:{self.model}"

    # ------------------------------------------------------------------ set-up

    def load(self) -> None:
        """Fetch the checkpoint.  Separate from ``__init__`` so a job can time the load."""
        from gliner import GLiNER

        model = GLiNER.from_pretrained(self.model)
        if self.device:
            model = model.to(self.device)
        self._model = model

    def use(self, model: Any) -> GlinerDetector:
        """Inject an already-loaded model.  Used by tests and by a job that shares one checkpoint."""
        self._model = model
        return self

    # ------------------------------------------------------------------ detection

    def _spans(self, document: Document, offset: int, found: Iterable[dict]) -> list[Span]:
        spans: list[Span] = []
        for entity in found:
            start = offset + int(entity["start"])
            end = offset + int(entity["end"])
            raw = str(entity.get("label", ""))
            spans.append(
                Span(
                    start=start,
                    end=end,
                    text=document.text[start:end],
                    type=harmonise(raw, "gliner")[0],
                    type_src=raw,
                    source=self.name,
                    score=float(entity.get("score", 0.0)),
                )
            )
        return spans

    def detect(self, document: Document) -> DetectorOutput:
        if self._model is None:
            self.load()
        labels = list(self.labels)
        spans: list[Span] = []
        for start, end in text_windows(document.text, self.max_chars, self.overlap):
            found = self._model.predict_entities(
                document.text[start:end], labels, threshold=self.threshold
            )
            spans.extend(self._spans(document, start, found))
        return DetectorOutput(document.doc_id, self.name, tuple(dedupe_spans(spans)))

    def detect_many(self, documents: Iterable[Document]) -> list[DetectorOutput]:
        """Batched detection: every window of every document goes into one call.

        GLiNER exposes ``batch_predict_entities``; using it keeps the GPU busy instead of paying the
        per-call overhead once per window, which on Enron is hundreds of thousands of windows.
        """
        if self._model is None:
            self.load()
        docs = list(documents)
        labels = list(self.labels)
        chunks: list[str] = []
        owner: list[tuple[int, int]] = []
        for index, document in enumerate(docs):
            for start, end in text_windows(document.text, self.max_chars, self.overlap):
                chunks.append(document.text[start:end])
                owner.append((index, start))

        if not chunks:
            return [DetectorOutput(d.doc_id, self.name, ()) for d in docs]

        batched = getattr(self._model, "batch_predict_entities", None)
        if batched is None:                       # older GLiNER: fall back to one call per window
            results = [
                self._model.predict_entities(chunk, labels, threshold=self.threshold)
                for chunk in chunks
            ]
        else:
            results = batched(chunks, labels, threshold=self.threshold)

        per_document: list[list[Span]] = [[] for _ in docs]
        for (index, start), found in zip(owner, results):
            per_document[index].extend(self._spans(docs[index], start, found))
        return [
            DetectorOutput(d.doc_id, self.name, tuple(dedupe_spans(spans)))
            for d, spans in zip(docs, per_document)
        ]
