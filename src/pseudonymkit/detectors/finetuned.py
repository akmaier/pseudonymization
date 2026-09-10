"""Axis D, fine-tuned level: public token-classification checkpoints.

Three models, fixed by ``experiment_plan.md`` §14 and §7:

=================================================  ================================================
model                                              what it was trained on
=================================================  ================================================
``obi/deid_roberta_i2b2``                          i2b2/n2c2 clinical de-identification, 11 labels
``StanfordAIMI/stanford-deidentifier-base``        radiology reports, 7 labels
``Davlan/xlm-roberta-large-ner-hrl``               multilingual NER, 4 labels
=================================================  ================================================

They are the level H5 predicts will add *least* to an LLM ensemble, *"because it fails where the LLMs
already agree"* — a fine-tuned NER and a prompted foundation model are both learned models of the
same distribution, so their errors correlate.  A clean negative result there is a result about where
the field should spend its effort, which is why the level is run rather than assumed.

Two of the three are clinical de-identifiers evaluated here on legal, news and e-mail text as well.
That is deliberate and is the same measurement §7 makes with ``privacy_tagger``: a detector trained
on one domain, run on others, shows what its published recall owes to its training corpus.

## The two things that silently corrupt offsets here

**Aggregation strategy.**  Without one, the pipeline emits one record per word piece with a BIO
prefix; with ``"first"`` it emits whole entities.  Both are handled — the taxonomy strips the prefix
(:func:`pseudonymkit.taxonomy.normalise_label`) — but the aggregated form is the default because
un-aggregated word pieces make span-level scoring meaningless.

**Character offsets need a fast tokenizer.**  ``start`` and ``end`` come from the tokenizer's offset
mapping, which the Python (slow) tokenizers do not provide; the pipeline then returns ``None`` for
both and a naive reader would write ``Span(None, None)``.  Such a record is refused loudly here
rather than written, because the failure is otherwise invisible until the offsets are scored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from ..domain import Document, Span
from ..taxonomy import harmonise, source_for
from .alignment import dedupe_spans, text_windows
from .base import DETECTORS, DetectorOutput

__all__ = ["TokenClassificationDetector", "FINETUNED_MODELS"]

FINETUNED_MODELS: tuple[str, ...] = (
    "obi/deid_roberta_i2b2",
    "StanfordAIMI/stanford-deidentifier-base",
    "Davlan/xlm-roberta-large-ner-hrl",
)
"""The three checkpoints §14 fixes.  Each is a separate level of axis D."""


@DETECTORS.register("finetuned")
@dataclass
class TokenClassificationDetector:
    """One HuggingFace token-classification checkpoint behind the detector port.

    ``name`` is ``hf:<model id>``, which :func:`pseudonymkit.taxonomy.source_for` resolves back to
    the model's own row in §10's mapping table — so the label translation a results row used is
    recoverable from the row itself.
    """

    model: str = FINETUNED_MODELS[0]
    aggregation: str = "first"
    """``"first"`` takes the whole entity's label from its first word piece, which is what the
    de-ID checkpoints were evaluated with."""
    max_chars: int = 1500
    """Roughly 400 word pieces, inside the 512-position limit these encoders were trained at."""
    overlap: int = 200
    device: int | str | None = None
    batch_size: int = 8
    family: str = "ner"
    _pipeline: Any = field(default=None, init=False, repr=False)

    @property
    def name(self) -> str:
        return f"hf:{self.model}"

    @property
    def source(self) -> str:
        """The §10 mapping table this model's labels are read through."""
        return source_for(self.name)

    # ------------------------------------------------------------------ set-up

    def load(self) -> None:
        """Build the pipeline.  Separate from ``__init__`` so a job can time the weight download."""
        from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline

        tokenizer = AutoTokenizer.from_pretrained(self.model, use_fast=True)
        model = AutoModelForTokenClassification.from_pretrained(self.model)
        self._pipeline = pipeline(
            "token-classification",
            model=model,
            tokenizer=tokenizer,
            aggregation_strategy=self.aggregation,
            device=self.device,
        )

    def use(self, pipe: Any) -> TokenClassificationDetector:
        """Inject an already-built pipeline.  Used by tests and by a job that shares weights."""
        self._pipeline = pipe
        return self

    # ------------------------------------------------------------------ detection

    def _spans(self, document: Document, offset: int, found: Iterable[dict]) -> list[Span]:
        spans: list[Span] = []
        for entity in found:
            start, end = entity.get("start"), entity.get("end")
            if start is None or end is None:
                raise RuntimeError(
                    f"{self.name} returned an entity without character offsets: a slow tokenizer "
                    "cannot produce them, so the checkpoint must be loaded with use_fast=True"
                )
            begin, finish = offset + int(start), offset + int(end)
            raw = str(entity.get("entity_group") or entity.get("entity") or "")
            spans.append(
                Span(
                    start=begin,
                    end=finish,
                    text=document.text[begin:finish],
                    type=harmonise(raw, self.source)[0],
                    type_src=raw,
                    source=self.name,
                    score=float(entity.get("score", 0.0)),
                )
            )
        return spans

    def detect(self, document: Document) -> DetectorOutput:
        return self.detect_many([document])[0]

    def detect_many(self, documents: Iterable[Document]) -> list[DetectorOutput]:
        """Every window of every document in one pipeline call.

        The pipeline batches internally, so handing it the whole window list rather than one window
        at a time is the difference between a saturated GPU and a per-call round trip.
        """
        if self._pipeline is None:
            self.load()
        docs = list(documents)
        chunks: list[str] = []
        owner: list[tuple[int, int]] = []
        for index, document in enumerate(docs):
            for start, end in text_windows(document.text, self.max_chars, self.overlap):
                chunks.append(document.text[start:end])
                owner.append((index, start))

        if not chunks:
            return [DetectorOutput(d.doc_id, self.name, ()) for d in docs]

        results = self._pipeline(chunks, batch_size=self.batch_size)
        if chunks and results and isinstance(results[0], dict):
            # A pipeline handed a one-element list may unwrap it; normalise so zip() stays aligned.
            results = [results]

        per_document: list[list[Span]] = [[] for _ in docs]
        for (index, start), found in zip(owner, results):
            per_document[index].extend(self._spans(docs[index], start, found or ()))
        return [
            DetectorOutput(d.doc_id, self.name, tuple(dedupe_spans(spans)))
            for d, spans in zip(docs, per_document)
        ]


def detectors(models: Sequence[str] = FINETUNED_MODELS, **kwargs: object) -> list[
    TokenClassificationDetector
]:
    """One detector per checkpoint — the three levels of axis D this module supplies."""
    return [TokenClassificationDetector(model=m, **kwargs) for m in models]  # type: ignore[arg-type]
