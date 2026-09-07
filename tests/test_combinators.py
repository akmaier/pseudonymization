import pytest

from pseudonymkit.detectors import COMBINATORS, DetectorOutput, cluster_spans, combination_grid
from pseudonymkit.domain import Span


def out(detector: str, *spans: tuple[int, int, str, str]) -> DetectorOutput:
    return DetectorOutput("d1", detector, tuple(Span(s, e, t, ty) for s, e, t, ty in spans))


PRESIDIO = out("presidio", (0, 9, "Dr. Weber", "PERSON"))
XLMR = out("xlmr", (4, 9, "Weber", "PERSON"))
LLM_A = out("llm_a", (4, 9, "Weber", "PERSON"), (20, 26, "Berlin", "LOC"))
LLM_B = out("llm_b", (4, 9, "Weber", "PERSON"))


def test_overlapping_spans_cluster_together():
    clusters = cluster_spans([PRESIDIO, XLMR, LLM_A])
    person = [c for c in clusters if c.entity_type == "PERSON"]
    assert len(person) == 1 and person[0].votes == 3


def test_union_takes_the_widest_span():
    spans = COMBINATORS.create("union").combine([PRESIDIO, XLMR])
    assert [(s.start, s.end) for s in spans] == [(0, 9)]


def test_intersection_requires_everyone_and_takes_the_narrowest():
    spans = COMBINATORS.create("intersection").combine([PRESIDIO, XLMR, LLM_A])
    assert [(s.start, s.end, s.type) for s in spans] == [(4, 9, "PERSON")]


def test_vote_threshold_drops_the_minority():
    """LOC has one voter of three, so a strict majority drops it and union keeps it."""
    outputs = [PRESIDIO, XLMR, LLM_A]
    voted = COMBINATORS.create("vote").combine(outputs)
    assert [s.type for s in voted] == ["PERSON"]
    assert "LOC" in [s.type for s in COMBINATORS.create("union").combine(outputs)]


def test_explicit_k_overrides_the_majority():
    assert len(COMBINATORS.create("vote", k=1).combine([LLM_A])) == 2
    assert len(COMBINATORS.create("vote", k=4).combine([PRESIDIO, XLMR, LLM_A])) == 0


def test_weighted_vote_lets_one_precise_detector_carry_a_cluster():
    """The point of hybrid ensembling: a trusted classical detector outweighs disagreeing LLMs."""
    rule = COMBINATORS.create("weighted_vote", weights={"presidio": 3.0, "llm_a": 0.1}, threshold=3.0)
    assert len(rule.combine([PRESIDIO])) == 1
    assert len(rule.combine([out("llm_a", (0, 9, "Dr. Weber", "PERSON"))])) == 0


def test_cascade_only_falls_back_where_earlier_detectors_were_silent():
    spans = COMBINATORS.create("cascade", order=("presidio", "llm_a")).combine([PRESIDIO, LLM_A])
    assert [(s.start, s.end) for s in spans] == [(0, 9), (20, 26)]


def test_majority_vote_representative_is_the_most_agreed_span():
    spans = COMBINATORS.create("vote", k=2).combine([XLMR, LLM_B, PRESIDIO])
    assert [(s.start, s.end) for s in spans] == [(4, 9)]


def test_grid_enumerates_subsets_and_rules():
    grid = combination_grid(("a", "b", "c"), rules=("union", "vote"))
    subsets = {members for members, _ in grid}
    assert subsets == {("a", "b"), ("a", "c"), ("b", "c"), ("a", "b", "c")}
    assert len(grid) == len(subsets) * 2


def test_grid_can_pin_required_detectors():
    """'LLMs only' vs 'LLMs plus a classical detector' compared on equal footing."""
    grid = combination_grid(("llm_a", "llm_b", "presidio"), rules=("union",), require=("llm_a", "llm_b"))
    assert {m for m, _ in grid} == {("llm_a", "llm_b"), ("llm_a", "llm_b", "presidio")}
