"""Axis D's scoring: how well a span set conceals the identities the gold marks (§8.1).

TAB's scheme, because it is the only published one designed for **concealing an identity** rather
than for hitting a category (Pilán et al., *Computational Linguistics* 48(4) 2022).  Four numbers,
and they answer different questions:

``entity_recall``
    The privacy metric.  An entity counts as protected only if **every one of its mentions** is
    masked — one unmasked mention leaks the person, so a detector that finds four of a patient's five
    mentions has protected nobody.  This is the risk-weighted measure Scaiano et al. (JBI 2016) argue
    plain recall is not, and it is strictly harsher: it cannot exceed token recall.

``token_recall``
    Reported beside it for comparability with the i2b2/n2c2 and MEDDOCAN literature, which scores
    spans rather than entities.

``precision``
    Plain: of the tokens a detector masked, how many were identifiers.

``information_weighted_precision``
    The over-masking metric.  Masking a token that carried no information is not the same harm as
    masking one that did, so each masked token is weighted by how predictable it is from the rest of
    the document.  **The weighting model is a parameter, not a constant**, because §8.1 names the
    metric and no source in the plan names the model; whatever is used is recorded in the result so
    two runs are comparable only when they agree on it.  With the default weight of 1.0 this reduces
    exactly to ``precision``, and the report says so rather than implying a weighting happened.

Everything is computed over **tokens**, not characters, so that a one-character boundary slip does
not count as a miss, and a mention counts as masked only when **all** of its tokens are covered:
``[PERSON] Weber`` still says Weber.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

from ..domain import Document, Span

__all__ = [
    "TOKEN_RE",
    "ScoringIndex",
    "prepare",
    "score_prepared",
    "tokenise",
    "covered_tokens",
    "DetectionScore",
    "score_detection",
    "score_corpus",
]

TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
"""Words and single punctuation marks.  Whitespace is not a token, so it can never be masked or
missed, and a span that covers trailing space is not rewarded for it."""


def tokenise(text: str) -> list[tuple[int, int]]:
    """``(start, end)`` for every token.  Offsets into ``text``, so spans align without a mapping."""
    return [(m.start(), m.end()) for m in TOKEN_RE.finditer(text)]


def covered_tokens(tokens: Sequence[tuple[int, int]], spans: Iterable[Span]) -> set[int]:
    """Indices of the tokens any span overlaps.

    Overlap, not containment: detectors disagree about whether a title or a trailing period belongs
    to the span, and a token the detector touched has been masked in the output text regardless.
    """
    hit: set[int] = set()
    if not tokens:
        return hit
    starts = [s for s, _ in tokens]
    for span in spans:
        if span.end <= span.start:
            continue
        # tokens are ordered and disjoint, so a linear scan from the first candidate suffices
        lo = _first_at_or_after(starts, span.start) - 1
        for index in range(max(lo, 0), len(tokens)):
            t_start, t_end = tokens[index]
            if t_start >= span.end:
                break
            if t_end > span.start:
                hit.add(index)
    return hit


def _first_at_or_after(starts: Sequence[int], value: int) -> int:
    lo, hi = 0, len(starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if starts[mid] < value:
            lo = mid + 1
        else:
            hi = mid
    return lo


@dataclass(frozen=True, slots=True)
class DetectionScore:
    """One span set scored against one gold layer.  A row of §8.1."""

    corpus: str
    detector: str
    documents: int
    gold_tokens: int
    predicted_tokens: int
    true_positive_tokens: int
    gold_entities: int
    protected_entities: int
    weight_model: str
    weighted_predicted: float
    weighted_true_positive: float
    per_type: Mapping[str, tuple[int, int, int]] = field(default_factory=dict)
    """harmonised type -> (gold tokens, predicted tokens, true-positive tokens)."""
    per_identifier_class: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    """DIRECT / QUASI / NO_MASK -> (gold tokens, recalled tokens).  Empty where unannotated."""
    entity_recall_measurable: bool = True
    """False when the gold carries no co-reference, so ``entity_recall`` would silently equal token
    recall rather than measure anything (§8.1: Enron and CARDIO:DE)."""

    @property
    def token_recall(self) -> float:
        return self.true_positive_tokens / self.gold_tokens if self.gold_tokens else float("nan")

    @property
    def precision(self) -> float:
        return (
            self.true_positive_tokens / self.predicted_tokens
            if self.predicted_tokens
            else float("nan")
        )

    @property
    def entity_recall(self) -> float:
        return (
            self.protected_entities / self.gold_entities if self.gold_entities else float("nan")
        )

    @property
    def information_weighted_precision(self) -> float:
        return (
            self.weighted_true_positive / self.weighted_predicted
            if self.weighted_predicted
            else float("nan")
        )

    def as_dict(self) -> dict[str, object]:
        """The result row.  Rates and their counts together — a rate without its denominator cannot
        be pooled or bootstrapped later."""
        return {
            "corpus": self.corpus,
            "detector": self.detector,
            "documents": self.documents,
            "token_recall": self.token_recall,
            "precision": self.precision,
            "information_weighted_precision": self.information_weighted_precision,
            "weight_model": self.weight_model,
            "entity_recall": self.entity_recall if self.entity_recall_measurable else None,
            "entity_recall_measurable": self.entity_recall_measurable,
            "gold_tokens": self.gold_tokens,
            "predicted_tokens": self.predicted_tokens,
            "true_positive_tokens": self.true_positive_tokens,
            "gold_entities": self.gold_entities,
            "protected_entities": self.protected_entities,
            "per_type": {k: list(v) for k, v in self.per_type.items()},
            "per_identifier_class": {k: list(v) for k, v in self.per_identifier_class.items()},
        }


TokenWeight = Callable[[str, int, Sequence[tuple[int, int]]], float]
"""``(document text, token index, tokens) -> information content of that token``."""


def uniform_weight(text: str, index: int, tokens: Sequence[tuple[int, int]]) -> float:  # noqa: ARG001
    """Every token worth the same, so weighted precision reduces to precision."""
    return 1.0


def frequency_weight(counts: Mapping[str, int], total: int) -> TokenWeight:
    """Self-information from a corpus unigram distribution: ``-log2 p(token)``.

    A cheap, reproducible stand-in for the contextual model §8.1 implies but does not name.  It
    captures the property the metric is for — masking *the* is nearly free, masking a rare surname is
    not — without importing a language model into the scorer.  Which weighting was used is recorded
    in every row, so a run using this is never silently compared with one using another.
    """

    def weight(text: str, index: int, tokens: Sequence[tuple[int, int]]) -> float:
        start, end = tokens[index]
        token = text[start:end].casefold()
        count = counts.get(token, 0)
        return -math.log2((count + 1) / (total + len(counts) + 1))

    return weight


@dataclass(frozen=True, slots=True)
class _Prepared:
    """One document reduced to what scoring needs, computed once."""

    doc_id: str
    text: str
    tokens: tuple[tuple[int, int], ...]
    gold_type: Mapping[int, str]
    """token index -> harmonised type, for the tokens the gold covers."""
    mentions: tuple[tuple[frozenset[int], str, str | None], ...]
    """(token indices, entity key, identifier class) per gold mention."""
    weights: tuple[float, ...]
    """information content per token, under the chosen weighting."""


@dataclass(frozen=True, slots=True)
class ScoringIndex:
    """A corpus prepared for scoring, so a sweep pays tokenisation once rather than per source.

    The sweep of §7 is thousands of span sources over the same documents — 3,375 for a corpus once
    ensembles of up to three detectors are included. Tokenising 400 letters inside each of those is
    1.35 million redundant passes, which is the difference between a sweep that runs in a minute and
    one that does not run.
    """

    corpus: str
    documents: tuple[_Prepared, ...]
    weight_model: str
    any_coref: bool


def prepare(
    documents: Sequence[Document],
    *,
    corpus: str,
    weight: TokenWeight = uniform_weight,
    weight_model: str = "uniform",
) -> ScoringIndex:
    """Tokenise, index the gold, and weight every token — once."""
    out: list[_Prepared] = []
    any_coref = False
    for document in documents:
        tokens = tuple(tokenise(document.text))
        gold_type: dict[int, str] = {}
        mentions: list[tuple[frozenset[int], str, str | None]] = []
        for number, mention in enumerate(document.mentions):
            indices = covered_tokens(tokens, (mention.span,))
            if not indices:
                continue
            for index in indices:
                gold_type[index] = mention.type
            if mention.gold_entity_id:
                any_coref = True
            key = mention.gold_entity_id or f"__m{number}"
            mentions.append(
                (frozenset(indices), key, (mention.attributes or {}).get("identifier_class"))
            )
        out.append(
            _Prepared(
                doc_id=document.doc_id,
                text=document.text,
                tokens=tokens,
                gold_type=gold_type,
                mentions=tuple(mentions),
                weights=tuple(weight(document.text, i, tokens) for i in range(len(tokens))),
            )
        )
    return ScoringIndex(corpus=corpus, documents=tuple(out), weight_model=weight_model,
                        any_coref=any_coref)


def score_prepared(
    index: ScoringIndex, predictions: Mapping[str, Sequence[Span]], *, detector: str
) -> DetectionScore:
    """Score one span source against a prepared corpus.  Same numbers as :func:`score_detection`."""
    gold_tokens = predicted_tokens = tp_tokens = 0
    weighted_pred = weighted_tp = 0.0
    per_type: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    per_class: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    entity_all: Counter[tuple[str, str]] = Counter()
    entity_hit: Counter[tuple[str, str]] = Counter()

    for document in index.documents:
        predicted = covered_tokens(document.tokens, predictions.get(document.doc_id, ()))
        predicted_tokens += len(predicted)
        weighted_pred += sum(document.weights[i] for i in predicted)
        for indices, key, cls in document.mentions:
            entity_key = (document.doc_id, key)
            entity_all[entity_key] += 1
            if indices <= predicted:
                entity_hit[entity_key] += 1
            if cls:
                per_class[cls][0] += len(indices)
                per_class[cls][1] += len(indices & predicted)
        gold_tokens += len(document.gold_type)
        for token_index, type_ in document.gold_type.items():
            per_type[type_][0] += 1
            if token_index in predicted:
                per_type[type_][2] += 1
                tp_tokens += 1
                weighted_tp += document.weights[token_index]
        for token_index in predicted:
            per_type[document.gold_type.get(token_index, "__none__")][1] += 1

    protected = sum(1 for key, n in entity_all.items() if entity_hit[key] == n)
    return DetectionScore(
        corpus=index.corpus, detector=detector, documents=len(index.documents),
        gold_tokens=gold_tokens, predicted_tokens=predicted_tokens,
        true_positive_tokens=tp_tokens, gold_entities=len(entity_all),
        protected_entities=protected, weight_model=index.weight_model,
        weighted_predicted=weighted_pred, weighted_true_positive=weighted_tp,
        per_type={k: tuple(v) for k, v in per_type.items()},
        per_identifier_class={k: tuple(v) for k, v in per_class.items()},
        entity_recall_measurable=index.any_coref,
    )


def score_detection(
    documents: Sequence[Document],
    predictions: Mapping[str, Sequence[Span]],
    *,
    corpus: str,
    detector: str,
    weight: TokenWeight = uniform_weight,
    weight_model: str = "uniform",
) -> DetectionScore:
    """Score one detector's spans against the documents' own gold mentions.

    ``predictions`` maps ``doc_id`` to that document's predicted spans.  A document absent from it is
    scored as **no prediction**, which costs recall — that is the honest reading of a detector that
    produced nothing for it, and it is why the runner must never silently drop a failed document.
    """
    gold_tokens = predicted_tokens = tp_tokens = 0
    weighted_pred = weighted_tp = 0.0
    per_type: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    per_class: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    entity_all: Counter[tuple[str, str]] = Counter()
    entity_hit: Counter[tuple[str, str]] = Counter()
    any_coref = False

    for document in documents:
        tokens = tokenise(document.text)
        predicted = covered_tokens(tokens, predictions.get(document.doc_id, ()))
        predicted_tokens += len(predicted)
        for index in predicted:
            weighted_pred += weight(document.text, index, tokens)

        gold_index: dict[int, str] = {}
        for mention in document.mentions:
            mention_tokens = covered_tokens(tokens, (mention.span,))
            if not mention_tokens:
                continue
            for index in mention_tokens:
                gold_index[index] = mention.type
            masked = mention_tokens <= predicted
            key = (document.doc_id, mention.gold_entity_id or f"__{id(mention)}")
            if mention.gold_entity_id:
                any_coref = True
            entity_all[key] += 1
            entity_hit[key] += 1 if masked else 0
            cls = (mention.attributes or {}).get("identifier_class")
            if cls:
                per_class[cls][0] += len(mention_tokens)
                per_class[cls][1] += len(mention_tokens & predicted)

        gold_tokens += len(gold_index)
        for index, type_ in gold_index.items():
            per_type[type_][0] += 1
            if index in predicted:
                per_type[type_][2] += 1
                tp_tokens += 1
                weighted_tp += weight(document.text, index, tokens)
        for index in predicted:
            per_type[gold_index.get(index, "__none__")][1] += 1

    protected = sum(1 for key, n in entity_all.items() if entity_hit[key] == n)
    return DetectionScore(
        corpus=corpus,
        detector=detector,
        documents=len(documents),
        gold_tokens=gold_tokens,
        predicted_tokens=predicted_tokens,
        true_positive_tokens=tp_tokens,
        gold_entities=len(entity_all),
        protected_entities=protected,
        weight_model=weight_model,
        weighted_predicted=weighted_pred,
        weighted_true_positive=weighted_tp,
        per_type={k: tuple(v) for k, v in per_type.items()},
        per_identifier_class={k: tuple(v) for k, v in per_class.items()},
        entity_recall_measurable=any_coref,
    )


def score_corpus(
    documents: Sequence[Document],
    pools: Mapping[str, Mapping[str, Sequence[Span]]],
    *,
    corpus: str,
    weight: TokenWeight = uniform_weight,
    weight_model: str = "uniform",
) -> list[DetectionScore]:
    """Score many span sources over one corpus, tokenising each document once per source.

    The sweep of §7 is thousands of span sources over the same documents, so the cost that matters is
    per source, not per document.
    """
    return [
        score_detection(
            documents, spans, corpus=corpus, detector=name, weight=weight, weight_model=weight_model
        )
        for name, spans in pools.items()
    ]
