"""Axis D, rule-based level: Microsoft Presidio over a spaCy backbone.

Presidio is the level H5 is really about.  H5 predicts that *"classical detectors add most where LLMs
are weakest, and that is on structured identifiers"* — IBANs, phone numbers, e-mail addresses, record
numbers — and Presidio is the only detector in the pool built out of pattern recognisers with
checksum validators rather than out of a learned model.  Its named-entity recall comes from spaCy and
will be unremarkable; its structured-identifier precision is the point.

## Three backbones, and why exactly these

``experiment_plan.md`` §14 fixes the level as *"Presidio + spaCy backbone"*.  The study spans four
languages and two non-Latin scripts, so the backbone is chosen per document language:

===========  =====================  =============================================================
language     spaCy model            note
===========  =====================  =============================================================
``en``       ``en_core_web_lg``     TAB, OntoNotes English, Enron
``de``       ``de_core_news_lg``    CARDIO:DE, CodEAlltag
other        ``xx_ent_wiki_sm``     OntoNotes Chinese and Arabic — the multilingual backbone
===========  =====================  =============================================================

The fallback is recorded per document in the run report rather than assumed, because §4 puts
cross-lingual PERSON detection at F1 0.40 overall and 0.04 in Arabic: *which* backbone produced a
number is part of what the number means.  This is not a substitution in the §1 sense — spaCy ships no
``zh``/``ar`` model in the set §14 names, and ``xx_ent_wiki_sm`` is the multilingual model of that
same set.

## What this module does not decide

**Nothing is filtered by score.**  Presidio attaches a confidence to every result and it is written
into :attr:`~pseudonymkit.domain.Span.score` unchanged.  Choosing a threshold is a *combination rule*
decision (§8.1: union maximises recall, the privacy-relevant direction, at the cost of precision),
and making it here would silently fix one point of a trade-off the paper exists to report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..domain import Document, Span
from ..taxonomy import harmonise
from .alignment import dedupe_spans, text_windows
from .base import DETECTORS, DetectorOutput

__all__ = ["PresidioDetector", "SPACY_MODELS", "MULTILINGUAL"]

SPACY_MODELS: Mapping[str, str] = {
    "en": "en_core_web_lg",
    "de": "de_core_news_lg",
    "xx": "xx_ent_wiki_sm",
}
"""Presidio language code -> spaCy model, as ``experiment_plan.md`` §14 fixes them."""

MULTILINGUAL = "xx"
"""The backbone every language without a dedicated model routes to."""


@DETECTORS.register("presidio")
@dataclass
class PresidioDetector:
    """Presidio's analyser, one instance serving every language in the study.

    Stateful in one respect only: the analyser engine is built once by :meth:`load` because loading
    three spaCy pipelines takes tens of seconds and a corpus is thousands of documents.  Detection
    itself is pure.
    """

    name: str = "presidio"
    family: str = "rule"
    languages: Sequence[str] = ("en", "de", MULTILINGUAL)
    score_threshold: float = 0.0
    """Kept at zero on purpose — see the module docstring."""
    max_chars: int = 100_000
    """Windowed only to stay inside spaCy's ``nlp.max_length``; a TAB judgment is far below it."""
    overlap: int = 500
    entities: Sequence[str] | None = None
    """``None`` means every recogniser the registry loaded, which is what H5 needs."""
    _analyzer: Any = field(default=None, init=False, repr=False)
    _fallbacks: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    # ------------------------------------------------------------------ set-up

    def load(self) -> None:
        """Build the analyser engine.  Separate from ``__init__`` so a job can time the load.

        The registry is built explicitly rather than left to default, because the default loads the
        predefined recognisers for English alone and would leave German and the multilingual
        backbone with pattern recognisers only — which would look like a German detection result and
        would not be one.
        """
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        languages = list(self.languages)
        provider = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [
                    {"lang_code": code, "model_name": SPACY_MODELS[code]} for code in languages
                ],
            }
        )
        nlp_engine = provider.create_engine()
        registry = RecognizerRegistry(supported_languages=languages)
        registry.load_predefined_recognizers(languages=languages, nlp_engine=nlp_engine)
        self._analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine, registry=registry, supported_languages=languages
        )

    def use(self, analyzer: Any) -> PresidioDetector:
        """Inject an already-built analyser.  Used by tests, and by a job that shares one engine."""
        self._analyzer = analyzer
        return self

    # ------------------------------------------------------------------ language

    def language_for(self, document: Document) -> str:
        """The Presidio language code this document is analysed under.

        Anything the backbone set does not cover falls to the multilingual model, and the fall is
        counted: :attr:`fallbacks` is reported with the run so a Chinese or Arabic result is never
        read as if it came from a dedicated model.
        """
        language = (document.language or "").split("-")[0].lower()
        if language in self.languages:
            return language
        return MULTILINGUAL

    @property
    def fallbacks(self) -> Mapping[str, int]:
        """Document language -> how often it was analysed with the multilingual backbone."""
        return dict(self._fallbacks)

    # ------------------------------------------------------------------ detection

    def detect(self, document: Document) -> DetectorOutput:
        if self._analyzer is None:
            self.load()
        language = self.language_for(document)
        if language == MULTILINGUAL and (document.language or "") != MULTILINGUAL:
            key = document.language or "unknown"
            self._fallbacks[key] = self._fallbacks.get(key, 0) + 1

        spans: list[Span] = []
        for start, end in text_windows(document.text, self.max_chars, self.overlap):
            chunk = document.text[start:end]
            for result in self._analyzer.analyze(
                text=chunk,
                language=language,
                entities=list(self.entities) if self.entities else None,
                score_threshold=self.score_threshold,
            ):
                raw = str(result.entity_type)
                begin, finish = start + int(result.start), start + int(result.end)
                spans.append(
                    Span(
                        start=begin,
                        end=finish,
                        text=document.text[begin:finish],
                        type=harmonise(raw, "presidio")[0],
                        type_src=raw,
                        source=self.name,
                        score=float(getattr(result, "score", 0.0)),
                    )
                )
        return DetectorOutput(document.doc_id, self.name, tuple(dedupe_spans(spans)))
