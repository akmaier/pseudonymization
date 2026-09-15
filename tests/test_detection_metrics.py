"""§8.1 scoring — TAB's scheme, which asks whether an identity was concealed.

The metric that carries the argument is entity-level recall: an entity is protected only if *every*
mention of it is masked. A detector that finds four of a patient's five mentions has protected
nobody, and plain recall reports 0.8 for that. These tests pin the difference.
"""

from __future__ import annotations

import math

import pytest

from pseudonymkit.domain import Document, Mention, Span
from pseudonymkit.metrics.detection import (
    covered_tokens,
    frequency_weight,
    score_detection,
    tokenise,
)

TEXT = "Dr. Weber saw Weber in Berlin on Monday."


def doc(mentions):
    built = []
    cursor = 0
    for i, (surface, type_, chain) in enumerate(mentions):
        start = TEXT.index(surface, cursor)
        cursor = start + len(surface)
        built.append(
            Mention("d1", f"m{i}", Span(start, start + len(surface), surface, type_),
                    gold_entity_id=chain)
        )
    return Document("d1", TEXT, "en", tuple(built))


GOLD = [("Weber", "PERSON", "e1"), ("Weber", "PERSON", "e1"), ("Berlin", "LOC", "e2")]


def spans_for(*surfaces):
    out, cursor = [], 0
    for surface in surfaces:
        start = TEXT.index(surface, cursor)
        cursor = start + len(surface)
        out.append(Span(start, start + len(surface), surface, "PERSON"))
    return {"d1": out}


# ------------------------------------------------------------------------------- tokenisation


def test_whitespace_is_never_a_token():
    assert all(TEXT[a:b].strip() for a, b in tokenise(TEXT))


def test_a_span_covering_trailing_space_is_not_rewarded_for_it():
    tokens = tokenise(TEXT)
    tight = covered_tokens(tokens, [Span(14, 19, "Weber", "PERSON")])
    loose = covered_tokens(tokens, [Span(14, 20, "Weber ", "PERSON")])
    assert tight == loose


# ------------------------------------------------------------------------------ the four numbers


def test_perfect_prediction_scores_one_everywhere():
    d = doc(GOLD)
    s = score_detection([d], {"d1": [m.span for m in d.mentions]}, corpus="t", detector="gold")
    assert s.token_recall == 1.0 and s.precision == 1.0 and s.entity_recall == 1.0


def test_predicting_nothing_protects_nobody():
    s = score_detection([doc(GOLD)], {}, corpus="t", detector="silent")
    assert s.token_recall == 0.0 and s.entity_recall == 0.0
    assert math.isnan(s.precision)          # no denominator, not zero


def test_one_missed_mention_leaves_the_entity_unprotected():
    """The point of the metric: 'Weber' found once of twice is 0.5 token recall and 0 entities."""
    s = score_detection([doc(GOLD)], spans_for("Weber", "Berlin"), corpus="t", detector="half")
    assert s.gold_entities == 2
    assert s.protected_entities == 1        # only Berlin
    assert s.entity_recall == 0.5
    assert s.token_recall == pytest.approx(2 / 3)


def test_a_partly_masked_mention_does_not_count_as_masked():
    """'[PERSON] Weber' still says Weber."""
    d = doc([("Dr. Weber", "PERSON", "e1")])
    partial = {"d1": [Span(0, 3, "Dr.", "PERSON")]}
    s = score_detection([d], partial, corpus="t", detector="partial")
    assert s.protected_entities == 0
    assert 0 < s.token_recall < 1


def test_entity_recall_never_exceeds_token_recall():
    for prediction in ({}, spans_for("Weber"), spans_for("Weber", "Berlin")):
        s = score_detection([doc(GOLD)], prediction, corpus="t", detector="x")
        assert s.entity_recall <= s.token_recall + 1e-12


def test_over_masking_costs_precision_not_recall():
    s = score_detection([doc(GOLD)], {"d1": [Span(0, len(TEXT), TEXT, "PERSON")]},
                        corpus="t", detector="greedy")
    assert s.token_recall == 1.0 and s.entity_recall == 1.0
    assert s.precision < 0.5


# ---------------------------------------------------------------------- information weighting


def test_uniform_weighting_reduces_to_plain_precision():
    s = score_detection([doc(GOLD)], spans_for("Weber", "Berlin"), corpus="t", detector="x")
    assert s.information_weighted_precision == pytest.approx(s.precision)
    assert s.weight_model == "uniform"


def test_a_frequency_weighting_punishes_masking_a_rare_token_more():
    d = doc(GOLD)
    # "on" must actually appear in the count table, or it scores as maximally rare and the
    # comparison inverts — which is what the first version of this test got wrong.
    counts, total = {"on": 10_000, "weber": 2}, 10_002
    common = {"d1": [Span(TEXT.index("on"), TEXT.index("on") + 2, "on", "PERSON")]}
    rare = spans_for("Weber")
    w = frequency_weight(counts, total)
    cheap = score_detection([d], common, corpus="t", detector="a", weight=w, weight_model="freq")
    dear = score_detection([d], rare, corpus="t", detector="b", weight=w, weight_model="freq")
    assert dear.weighted_predicted > cheap.weighted_predicted


# ------------------------------------------------------------------------------- breakdowns


def test_types_are_broken_out_and_false_positives_are_attributed_to_none():
    s = score_detection([doc(GOLD)], spans_for("Weber", "Berlin", "Monday"),
                        corpus="t", detector="x")
    assert s.per_type["PERSON"][2] == 1        # one of two Weber tokens recalled
    assert s.per_type["LOC"][2] == 1
    assert s.per_type["__none__"][1] == 1      # Monday was masked and is not gold


def test_direct_and_quasi_are_reported_separately_where_annotated():
    d = Document("d1", TEXT, "en", (
        Mention("d1", "m0", Span(4, 9, "Weber", "PERSON"), gold_entity_id="e1",
                attributes={"identifier_class": "DIRECT"}),
        Mention("d1", "m1", Span(23, 29, "Berlin", "LOC"), gold_entity_id="e2",
                attributes={"identifier_class": "QUASI"}),
    ))
    s = score_detection([d], {"d1": [Span(4, 9, "Weber", "PERSON")]}, corpus="t", detector="x")
    assert s.per_identifier_class["DIRECT"] == (1, 1)
    assert s.per_identifier_class["QUASI"] == (1, 0)


def test_entity_recall_is_marked_unmeasurable_without_coreference():
    """On a corpus with no chains it would silently equal token recall (§8.1: Enron, CARDIO:DE)."""
    d = doc([("Weber", "PERSON", None), ("Berlin", "LOC", None)])
    s = score_detection([d], {}, corpus="t", detector="x")
    assert s.entity_recall_measurable is False
    assert s.as_dict()["entity_recall"] is None


def test_a_document_with_no_prediction_costs_recall_rather_than_being_skipped():
    a, b = doc(GOLD), Document("d2", TEXT, "en", doc(GOLD).mentions)
    b = Document("d2", TEXT, "en", tuple(
        Mention("d2", m.mention_id, m.span, gold_entity_id=m.gold_entity_id) for m in a.mentions))
    s = score_detection([a, b], {"d1": [m.span for m in a.mentions]}, corpus="t", detector="x")
    assert s.documents == 2
    assert s.token_recall == pytest.approx(0.5)


# ------------------------------------------------------- the prepared index used by the sweep
# The sweep scores 3,375 span sources over one corpus (§7, ensembles of up to three detectors), so
# tokenisation must happen once, not once per source. These pin that the fast path agrees with the
# plain one — a faster scorer that disagrees is worse than no scorer.

from pseudonymkit.metrics.detection import prepare, score_prepared     # noqa: E402


@pytest.mark.parametrize("prediction", [
    {}, "gold", "half", "greedy",
])
def test_the_prepared_path_agrees_with_the_plain_one(prediction):
    d = doc(GOLD)
    if prediction == "gold":
        spans = {"d1": [m.span for m in d.mentions]}
    elif prediction == "half":
        spans = spans_for("Weber", "Berlin")
    elif prediction == "greedy":
        spans = {"d1": [Span(0, len(TEXT), TEXT, "PERSON")]}
    else:
        spans = prediction
    slow = score_detection([d], spans, corpus="t", detector="x")
    fast = score_prepared(prepare([d], corpus="t"), spans, detector="x")
    assert _same(slow.as_dict(), fast.as_dict())


def _same(a, b):
    """Dict equality that treats NaN as equal to NaN.

    With no prediction there is no denominator, so precision is NaN in both paths — and two NaNs
    built separately are not equal to each other, which made this test fail on the code being right.
    """
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, float) and isinstance(b, float):
        return (math.isnan(a) and math.isnan(b)) or a == b
    return a == b


def test_the_index_is_reusable_across_sources():
    index = prepare([doc(GOLD)], corpus="t")
    a = score_prepared(index, spans_for("Weber"), detector="a")
    b = score_prepared(index, spans_for("Weber", "Berlin"), detector="b")
    assert a.detector == "a" and b.detector == "b"
    assert b.token_recall > a.token_recall      # no state leaked between the two


def test_the_index_carries_the_weighting_into_every_score():
    index = prepare([doc(GOLD)], corpus="t",
                    weight=frequency_weight({"weber": 2}, 10), weight_model="freq")
    assert score_prepared(index, spans_for("Weber"), detector="x").weight_model == "freq"
