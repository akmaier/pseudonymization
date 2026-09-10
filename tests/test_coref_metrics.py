"""MUC, B-cubed, CEAF_e and the CoNLL mean.

The three metrics disagree with each other on purpose, and the tests assert that disagreement: a
system that merges two gold entities is punished hardest by CEAF_e and least by MUC, which is the
whole reason the CoNLL score averages them.
"""

from __future__ import annotations

import math

import pytest

from pseudonymkit.metrics.coref import (
    b_cubed,
    ceaf_e,
    conll_f1,
    coref_scores,
    drop_singletons,
    muc,
)

A = {"a1", "a2", "a3"}
B = {"b1", "b2"}


def test_a_perfect_system_scores_one():
    scores = coref_scores([A, B], [A, B])
    assert scores["muc"] == scores["b_cubed"] == scores["ceaf_e"] == 1.0
    assert scores["conll"] == 1.0


def test_singletons_are_dropped_by_the_conll_convention():
    assert drop_singletons([{"x"}, A]) == [frozenset(A)]
    assert math.isnan(conll_f1([{"x"}, {"y"}], [{"x"}, {"y"}]))


def test_a_document_with_no_chain_is_not_a_zero():
    """Scoring it zero would say the resolver failed where nothing could have gone wrong."""
    scores = coref_scores([{"x"}, {"y"}], [{"x"}, {"y"}])
    assert all(math.isnan(v) for v in scores.values())


def test_singletons_can_be_kept_when_a_caller_asks():
    """And MUC still scores zero on them, because it counts links and singletons have none."""
    scores = coref_scores([{"x"}, {"y"}], [{"x"}, {"y"}], include_singletons=True)
    assert (scores["b_cubed"], scores["ceaf_e"]) == (1.0, 1.0)
    assert scores["muc"] == 0.0
    assert scores["conll"] == pytest.approx(2 / 3)


def test_a_split_chain_costs_every_metric():
    scores = coref_scores([A], [{"a1", "a2"}, {"a3"}])
    assert 0.0 < scores["muc"] < 1.0
    assert 0.0 < scores["b_cubed"] < 1.0
    assert 0.0 < scores["ceaf_e"] < 1.0


def test_ceaf_punishes_a_merge_harder_than_muc_does():
    """MUC counts links, so merging two chains costs one link and can buy several."""
    merged = [A | B]
    muc_f1 = muc([frozenset(A), frozenset(B)], [frozenset(A | B)])[2]
    ceaf_f1 = ceaf_e([frozenset(A), frozenset(B)], [frozenset(A | B)])[2]
    assert muc_f1 > ceaf_f1
    assert coref_scores([A, B], merged)["conll"] < muc_f1


def test_ceaf_alignment_is_one_to_one():
    """One system cluster cannot be credited for two gold entities."""
    precision, recall, _ = ceaf_e([frozenset(A), frozenset(B)], [frozenset(A)])
    assert recall == pytest.approx(0.5)
    assert precision == pytest.approx(1.0)


def test_b_cubed_weights_by_cluster_size():
    """Breaking a big chain costs more than breaking a small one."""
    big = {f"m{i}" for i in range(10)}
    small = {"s1", "s2"}
    break_big = b_cubed([frozenset(big), frozenset(small)],
                        [frozenset(list(big)[:5]), frozenset(list(big)[5:]), frozenset(small)])[2]
    break_small = b_cubed([frozenset(big), frozenset(small)],
                          [frozenset(big), frozenset({"s1"}), frozenset({"s2"})])[2]
    assert break_big < break_small


def test_finding_nothing_scores_zero():
    scores = coref_scores([A, B], [])
    assert scores["conll"] == 0.0


def test_mentions_are_compared_by_offset():
    gold = [{(0, 5), (20, 25)}]
    shifted = [{(0, 5), (21, 25)}]
    assert coref_scores(gold, gold)["conll"] == 1.0
    assert coref_scores(gold, shifted)["conll"] < 1.0
