"""CoNLL co-reference scoring: MUC, B-cubed, CEAF_e, and their mean.

Co-reference is the sharpest utility measurement in the study (``experiment_plan.md`` §8.3), and it
is the one that ties §8.2 to §8.3 directly: **fragmentation *is* chain breakage**.  A resolver's
CoNLL F1 on pseudonymised text measures the utility cost of exactly the failure the stability metrics
count, on the same documents.  No prior work reports both.

The CoNLL-2012 score is the unweighted mean of three F1s that disagree with each other on purpose:

* **MUC** counts *links*.  It is blind to singletons and rewards over-merging, because merging two
  chains costs one link and can buy several.
* **B-cubed** counts *mentions*, weighting each cluster by its size, so one badly split large chain
  costs more than one badly split small one.
* **CEAF_e** counts *entities*, under a one-to-one alignment between gold and system clusters, so no
  system cluster can be credited for two gold entities at once.

Reporting their mean rather than any one of them is the field's convention and is what makes the
number comparable with the co-reference literature.

**Singletons are excluded by default**, which is also the CoNLL-2012 convention and matters here more
than usual: on both TAB and OntoNotes about three quarters of PERSON chains hold a single mention
(§8.2), so including them would let a resolver score highly by finding no links at all.  A document
whose gold has no multi-mention chain therefore has nothing to score, and the runner reports it as
such rather than as a zero.

Mentions are compared by their character offsets.  A predicted mention with different boundaries from
the gold one is a different mention, which is strict — the alternative is a boundary-tolerance rule
that would itself need justifying, and strictness costs the same in every condition, so it cannot
bias the comparison the study is making.
"""

from __future__ import annotations

from typing import Hashable, Iterable, Sequence

__all__ = ["muc", "b_cubed", "ceaf_e", "conll_f1", "coref_scores", "drop_singletons"]

Mention = Hashable
Cluster = frozenset


def _clusters(clusters: Iterable[Iterable[Mention]]) -> list[frozenset[Mention]]:
    return [frozenset(c) for c in clusters if c]


def drop_singletons(clusters: Iterable[Iterable[Mention]]) -> list[frozenset[Mention]]:
    """The CoNLL-2012 convention: a chain of one mention asserts no co-reference."""
    return [c for c in _clusters(clusters) if len(c) > 1]


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0


def _index(clusters: Sequence[frozenset[Mention]]) -> dict[Mention, frozenset[Mention]]:
    return {m: c for c in clusters for m in c}


def _muc_side(
    reference: Sequence[frozenset[Mention]], other: Sequence[frozenset[Mention]]
) -> float:
    """MUC recall of ``reference`` against ``other``; precision is the same call, swapped."""
    numerator = denominator = 0
    lookup = _index(other)
    for cluster in reference:
        if len(cluster) < 2:
            continue
        partitions = {lookup.get(m) for m in cluster}
        # A mention the other side never placed is its own partition, hence the None -> 1 each.
        loose = sum(1 for m in cluster if m not in lookup)
        pieces = len([p for p in partitions if p is not None]) + loose
        numerator += len(cluster) - pieces
        denominator += len(cluster) - 1
    return numerator / denominator if denominator else 0.0


def muc(
    gold: Sequence[frozenset[Mention]], predicted: Sequence[frozenset[Mention]]
) -> tuple[float, float, float]:
    """MUC precision, recall and F1 — the link-based metric (Vilain et al. 1995)."""
    recall = _muc_side(gold, predicted)
    precision = _muc_side(predicted, gold)
    return precision, recall, _f1(precision, recall)


def _b_cubed_side(
    reference: Sequence[frozenset[Mention]], other: Sequence[frozenset[Mention]]
) -> float:
    lookup = _index(other)
    total = 0.0
    mentions = 0
    for cluster in reference:
        for mention in cluster:
            mentions += 1
            counterpart = lookup.get(mention)
            if counterpart:
                total += len(cluster & counterpart) / len(cluster)
    return total / mentions if mentions else 0.0


def b_cubed(
    gold: Sequence[frozenset[Mention]], predicted: Sequence[frozenset[Mention]]
) -> tuple[float, float, float]:
    """B-cubed precision, recall and F1 — the mention-based metric (Bagga & Baldwin 1998)."""
    recall = _b_cubed_side(gold, predicted)
    precision = _b_cubed_side(predicted, gold)
    return precision, recall, _f1(precision, recall)


def ceaf_e(
    gold: Sequence[frozenset[Mention]], predicted: Sequence[frozenset[Mention]]
) -> tuple[float, float, float]:
    """CEAF_e precision, recall and F1 — the entity-based metric (Luo 2005).

    ``phi4(G, S) = 2|G n S| / (|G| + |S|)``, maximised over a **one-to-one** alignment of gold and
    system clusters.  The alignment is what makes this the strictest of the three: a system cluster
    that merged two gold entities can be credited for at most one of them.
    """
    if not gold or not predicted:
        return 0.0, 0.0, 0.0

    import numpy as np
    from scipy.optimize import linear_sum_assignment

    similarity = np.zeros((len(gold), len(predicted)), dtype=float)
    for i, g in enumerate(gold):
        for j, s in enumerate(predicted):
            overlap = len(g & s)
            if overlap:
                similarity[i, j] = 2 * overlap / (len(g) + len(s))

    rows, columns = linear_sum_assignment(-similarity)
    total = float(similarity[rows, columns].sum())
    precision = total / len(predicted)
    recall = total / len(gold)
    return precision, recall, _f1(precision, recall)


def coref_scores(
    gold: Iterable[Iterable[Mention]],
    predicted: Iterable[Iterable[Mention]],
    include_singletons: bool = False,
) -> dict[str, float]:
    """All three metrics plus the CoNLL mean, for one document.

    Returns ``nan`` for every value when the document has nothing to score — no gold chain of more
    than one mention.  That is not a zero: a zero would say the resolver failed, and averaging zeros
    from documents with no chains into a corpus mean would make a condition look worse in exactly the
    documents where nothing could have gone wrong.  The runner drops them and records how many.
    """
    prepare = drop_singletons if not include_singletons else _clusters
    g = prepare(gold)
    p = prepare(predicted)
    if not g:
        return {k: float("nan") for k in ("muc", "b_cubed", "ceaf_e", "conll")}

    muc_scores = muc(g, p)
    b3_scores = b_cubed(g, p)
    ceaf_scores = ceaf_e(g, p)
    return {
        "muc": muc_scores[2],
        "b_cubed": b3_scores[2],
        "ceaf_e": ceaf_scores[2],
        "conll": (muc_scores[2] + b3_scores[2] + ceaf_scores[2]) / 3.0,
    }


def conll_f1(
    gold: Iterable[Iterable[Mention]],
    predicted: Iterable[Iterable[Mention]],
    include_singletons: bool = False,
) -> float:
    """The CoNLL-2012 score for one document: the mean of MUC, B-cubed and CEAF_e F1."""
    return coref_scores(gold, predicted, include_singletons)["conll"]
