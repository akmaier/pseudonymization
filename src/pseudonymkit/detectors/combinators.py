"""Combining detectors — including classical detectors with LLMs.

The in-house ensembling that motivated this study combined large language models only.  Whether
adding rule-based, fine-tuned and zero-shot detectors to an LLM ensemble helps is an empirical
question, and answering it needs the combination rule to be a first-class, enumerable axis rather
than a hard-coded ``union``.

A combinator takes the outputs of several detectors on one document and returns one span set.
Because spans from different detectors rarely align exactly, agreement is defined by *overlap
clustering*: spans of the same entity type that overlap transitively form one cluster, and the
rule decides whether the cluster survives and which of its spans represents it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol, Sequence, runtime_checkable

from ..domain import Span
from ..registry import Registry
from ..domain import Document
from .alignment import bio_to_spans, spans_to_bio, tokenise, vote_labels
from .base import DetectorOutput

__all__ = ["Combinator", "COMBINATORS", "cluster_spans", "combination_grid", "TokenVote"]


@runtime_checkable
class Combinator(Protocol):
    """Merges several detectors' spans into one set."""

    name: str

    def combine(self, outputs: Sequence[DetectorOutput]) -> tuple[Span, ...]: ...


COMBINATORS: Registry[Combinator] = Registry("combinator")


@dataclass(frozen=True, slots=True)
class Cluster:
    """Overlapping spans of one entity type, and which detectors contributed them."""

    entity_type: str
    spans: tuple[Span, ...]
    voters: frozenset[str]

    @property
    def votes(self) -> int:
        return len(self.voters)

    def widest(self) -> Span:
        """The longest span, earliest on ties — the recall-maximising representative."""
        return max(self.spans, key=lambda s: (s.length, -s.start))

    def narrowest(self) -> Span:
        """The shortest span — the precision-maximising representative."""
        return min(self.spans, key=lambda s: (s.length, s.start))

    def most_agreed(self) -> Span:
        """The exact span the most detectors produced; the widest breaks ties."""
        counts: dict[tuple[int, int], int] = {}
        for s in self.spans:
            counts[(s.start, s.end)] = counts.get((s.start, s.end), 0) + 1
        best = max(counts.items(), key=lambda kv: (kv[1], kv[0][1] - kv[0][0]))[0]
        return next(s for s in self.spans if (s.start, s.end) == best)


def cluster_spans(
    outputs: Sequence[DetectorOutput], link: str = "single", iou: float = 0.5
) -> list[Cluster]:
    """Group spans into clusters, per entity type.

    Two spans join the same cluster when they share the entity type and overlap.  Overlap rather
    than exact match is the right criterion because detectors disagree about boundaries far more
    often than about the presence of an entity — treating *Dr. Weber* and *Weber* as disagreement
    would understate agreement badly.

    ``link`` controls how far that tolerance extends:

    * ``"single"`` — transitive overlap. Simple, but it **chains**: ``A(0,10)``, ``B(8,20)``,
      ``C(18,30)`` land in one cluster although A and C are disjoint. On dense text this can merge
      two adjacent people into one entity.
    * ``"iou"`` — a span joins a cluster only if its intersection-over-union with a member reaches
      ``iou``. Chaining stops, at the price of splitting genuine boundary disagreements when one
      detector is much more generous than another.

    Which is right is an empirical question about the detector pool, so it is a reported setting
    rather than a hard-coded choice.
    """
    tagged: list[tuple[Span, str]] = [(s, o.detector) for o in outputs for s in o.spans]
    clusters: list[Cluster] = []
    for entity_type in sorted({s.type for s, _ in tagged}):
        items = sorted(((s, d) for s, d in tagged if s.type == entity_type), key=lambda x: x[0].start)
        current: list[tuple[Span, str]] = []
        end = -1
        for span, detector in items:
            joins = bool(current) and span.start < end and (
                link == "single" or any(_iou(span, m) >= iou for m, _ in current)
            )
            if joins:
                current.append((span, detector))
                end = max(end, span.end)
            else:
                if current:
                    clusters.append(_make(entity_type, current))
                current = [(span, detector)]
                end = span.end
        if current:
            clusters.append(_make(entity_type, current))
    return clusters


def _iou(a: Span, b: Span) -> float:
    """Intersection over union of two character ranges."""
    inter = max(0, min(a.end, b.end) - max(a.start, b.start))
    union = max(a.end, b.end) - min(a.start, b.start)
    return inter / union if union else 0.0


def _make(entity_type: str, items: Sequence[tuple[Span, str]]) -> Cluster:
    return Cluster(
        entity_type=entity_type,
        spans=tuple(s for s, _ in items),
        voters=frozenset(d for _, d in items),
    )


class _RuleBase:
    """A rule over clusters, plus the clustering settings that decide what a cluster *is*.

    ``link`` and ``iou`` were previously fixed at :func:`cluster_spans`'s defaults and unreachable
    from here, which made them invisible parameters of every ensemble result.  They are constructor
    arguments now, they appear in :attr:`settings`, and a result that does not carry them is not
    reproducible (§9).
    """

    name = "rule"
    _representative: Callable[[Cluster], Span] = staticmethod(Cluster.widest)

    def __init__(self, link: str = "single", iou: float = 0.5) -> None:
        self.link = link
        self.iou = iou

    @property
    def settings(self) -> dict[str, object]:
        return {"rule": self.name, "link": self.link, "iou": self.iou}

    def _keep(self, cluster: Cluster, n_detectors: int) -> bool:
        raise NotImplementedError

    def combine(self, outputs: Sequence[DetectorOutput]) -> tuple[Span, ...]:
        n = len({o.detector for o in outputs})
        kept = [c for c in cluster_spans(outputs, link=self.link, iou=self.iou) if self._keep(c, n)]
        spans = [type(self)._representative(c) for c in kept]
        return tuple(sorted(spans, key=lambda s: (s.start, s.end)))


@COMBINATORS.register("union")
class Union(_RuleBase):
    """Any detector suffices; the widest span wins.

    Maximises recall — the privacy-relevant direction — at the cost of precision, and therefore of
    utility, because every false positive pseudonymises a token that carried meaning.
    """

    name = "union"
    _representative = staticmethod(Cluster.widest)

    def _keep(self, cluster: Cluster, n_detectors: int) -> bool:
        return True


@COMBINATORS.register("intersection")
class Intersection(_RuleBase):
    """Every detector must agree; the narrowest span wins. Maximises precision."""

    name = "intersection"
    _representative = staticmethod(Cluster.narrowest)

    def _keep(self, cluster: Cluster, n_detectors: int) -> bool:
        return cluster.votes >= n_detectors


@COMBINATORS.register("vote")
class MajorityVote(_RuleBase):
    """At least ``k`` detectors must agree; ``k`` defaults to a strict majority.

    The counterpart to union: it trades recall for precision, and the gap between the two is the
    privacy/utility trade-off this study is about, appearing a second time at the detector level.
    """

    name = "vote"
    _representative = staticmethod(Cluster.most_agreed)

    def __init__(self, k: int | None = None, **clustering: object) -> None:
        super().__init__(**clustering)  # type: ignore[arg-type]
        self.k = k
        if k is not None:
            self.name = f"vote{k}"

    def _keep(self, cluster: Cluster, n_detectors: int) -> bool:
        threshold = self.k if self.k is not None else (n_detectors // 2) + 1
        return cluster.votes >= threshold


@COMBINATORS.register("weighted_vote")
class WeightedVote(_RuleBase):
    """Votes weighted per detector, e.g. by that detector's precision on a dev split.

    This is where a classical detector can earn its place in an LLM ensemble: a high-precision
    rule-based recogniser for structured identifiers can outweigh several language models that
    disagree about a name boundary.
    """

    name = "weighted_vote"
    _representative = staticmethod(Cluster.most_agreed)

    def __init__(self, weights: Mapping[str, float], threshold: float = 1.0,
                 **clustering: object) -> None:
        super().__init__(**clustering)  # type: ignore[arg-type]
        self._weights = dict(weights)
        self._threshold = threshold

    def _keep(self, cluster: Cluster, n_detectors: int) -> bool:
        return sum(self._weights.get(v, 1.0) for v in cluster.voters) >= self._threshold


@COMBINATORS.register("cascade")
class Cascade(_RuleBase):
    """Trust an ordered list of detectors, falling back only where earlier ones found nothing.

    Models the deployed pattern of "cheap detector first, expensive model only on what it missed",
    and lets the cost of an LLM in the loop be quantified rather than assumed.
    """

    name = "cascade"

    def __init__(self, order: Sequence[str], **clustering: object) -> None:
        super().__init__(**clustering)  # type: ignore[arg-type]
        self._order = tuple(order)

    def combine(self, outputs: Sequence[DetectorOutput]) -> tuple[Span, ...]:
        by_detector = {o.detector: o for o in outputs}
        accepted: list[Span] = []
        for detector in self._order:
            output = by_detector.get(detector)
            if output is None:
                continue
            for span in output.spans:
                if not any(span.overlaps(a) and span.type == a.type for a in accepted):
                    accepted.append(span)
        return tuple(sorted(accepted, key=lambda s: (s.start, s.end)))


def combination_grid(
    detectors: Sequence[str],
    rules: Sequence[str] = ("union", "vote", "intersection"),
    min_size: int = 2,
    max_size: int | None = None,
    require: Sequence[str] = (),
) -> list[tuple[tuple[str, ...], str]]:
    """Enumerate (detector subset, rule) pairs — the hybrid-ensemble search space.

    The question motivating it is whether classical detectors add anything to an ensemble of large
    language models, so the grid is meant to be swept rather than sampled.  ``require`` pins
    detectors that must appear in every subset, which is how "LLMs only" and "LLMs plus at least
    one classical detector" are compared on equal footing.

    >>> len(combination_grid(("a", "b", "c"), rules=("union",)))
    4
    """
    from itertools import combinations

    pool = [d for d in detectors if d not in require]
    upper = max_size if max_size is not None else len(detectors)
    grid: list[tuple[tuple[str, ...], str]] = []
    for size in range(max(min_size - len(require), 0), len(pool) + 1):
        for subset in combinations(pool, size):
            members = tuple(sorted((*require, *subset)))
            if not (min_size <= len(members) <= upper):
                continue
            for rule in rules:
                grid.append((members, rule))
    return grid


@COMBINATORS.register("token_vote")
class TokenVote:
    """Per-token voting on a shared grid — the ROVER analogue for sequence labelling.

    ROVER aligns recognisers' outputs into a transition network and votes at each slot.  Here the
    alignment is free, because every detector read the same string, so the token sequence *is* the
    network.  Voting on it rather than on whole spans buys three things the span-level rules cannot
    give:

    * **partial credit** — a detector that got three tokens of a four-token name right contributes
      to those three, instead of being counted as disagreeing about the whole span;
    * **type disagreement resolved as a tie**, not as two separate minorities that both fail their
      threshold, which is what per-type span clustering does to it;
    * **boundaries decided by the vote** rather than by a representative-picking heuristic.

    Requires the document, because tokens are positions in its text.  Where a span-level rule is
    enough this is more machinery than the problem needs — which of the two wins is exactly the
    ensembling question this study is meant to answer, so both are levels of axis D'.
    """

    name = "token_vote"

    def __init__(
        self, weights: Mapping[str, float] | None = None, threshold: float | None = None
    ) -> None:
        self._weights = dict(weights or {})
        self._threshold = threshold

    def combine_document(
        self, document: Document, outputs: Sequence[DetectorOutput]
    ) -> tuple[Span, ...]:
        tokens = tokenise(document.text)
        if not tokens or not outputs:
            return ()
        sequences = [spans_to_bio(o.spans, tokens) for o in outputs]
        weights = [self._weights.get(o.detector, 1.0) for o in outputs]
        voted = vote_labels(sequences, weights, self._threshold)
        return tuple(bio_to_spans(voted, tokens, document.text))

    def combine(self, outputs: Sequence[DetectorOutput]) -> tuple[Span, ...]:
        raise TypeError(
            "token_vote needs the document text; call combine_document(document, outputs)"
        )
