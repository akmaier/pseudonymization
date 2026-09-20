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


# --- alignment and token-level voting (the ROVER analogue) --------------------

from pseudonymkit.detectors.alignment import (  # noqa: E402
    bio_to_spans, ground_snippets, spans_to_bio, tokenise, vote_labels,
)
from pseudonymkit.detectors.combinators import TokenVote  # noqa: E402
from pseudonymkit.domain import Document  # noqa: E402

TEXT = "Dr. Weber met Mary Jones in Berlin."
DOC = Document("d1", TEXT, "en", ())


def test_bio_round_trip_is_lossless():
    tokens = tokenise(TEXT)
    spans = [Span(4, 9, "Weber", "PERSON"), Span(28, 34, "Berlin", "LOC")]
    back = bio_to_spans(spans_to_bio(spans, tokens), tokens, TEXT)
    assert [(s.start, s.end, s.type) for s in back] == [(4, 9, "PERSON"), (28, 34, "LOC")]


def test_single_link_clustering_chains_and_iou_does_not():
    """A(0,10) B(8,20) C(18,30): A and C are disjoint but single-link merges all three."""
    a = out("a", (0, 10, "x", "PERSON"))
    b = out("b", (8, 20, "x", "PERSON"))
    c = out("c", (18, 30, "x", "PERSON"))
    assert len(cluster_spans([a, b, c])) == 1
    assert len(cluster_spans([a, b, c], link="iou", iou=0.5)) == 3


def test_token_vote_gives_partial_credit_for_a_partly_correct_span():
    """Span rules score 'Mary Jones' vs 'Jones' as disagreement; token voting agrees on 'Jones'."""
    full = out("a", (14, 24, "Mary Jones", "PERSON"))
    part = out("b", (19, 24, "Jones", "PERSON"))
    third = out("c", (19, 24, "Jones", "PERSON"))
    spans = TokenVote().combine_document(DOC, [full, part, third])
    assert [(s.start, s.end) for s in spans] == [(19, 24)]


def test_token_vote_resolves_type_disagreement_as_presence_agreement():
    """Four detectors, split two PERSON / two ORG: all four agree something is there.

    Per-type span clustering sees two minorities of two, neither reaching a majority of four, and
    discards both -- so unanimous evidence of an entity yields nothing. Token voting pools presence
    first and settles the type afterwards, which is what a pseudonymisation study needs: a missed
    entity leaks, a mislabelled one is still replaced.
    """
    outs = [
        out("a", (28, 34, "Berlin", "PERSON")),
        out("b", (28, 34, "Berlin", "PERSON")),
        out("c", (28, 34, "Berlin", "ORG")),
        out("d", (28, 34, "Berlin", "ORG")),
    ]
    assert COMBINATORS.create("vote").combine(outs) == ()
    voted = TokenVote().combine_document(DOC, outs)
    assert [(s.start, s.end) for s in voted] == [(28, 34)]
    assert voted[0].type in {"PERSON", "ORG"}


def test_token_vote_still_drops_a_lone_detector():
    outs = [out("a", (28, 34, "Berlin", "LOC")), out("b"), out("c")]
    assert TokenVote().combine_document(DOC, outs) == ()


def test_token_vote_weights_let_one_trusted_detector_win():
    trusted = out("presidio", (28, 34, "Berlin", "LOC"))
    others = [out("llm_a", (28, 34, "Berlin", "PERSON")), out("llm_b", (28, 34, "Berlin", "PERSON"))]
    rule = TokenVote(weights={"presidio": 5.0, "llm_a": 1.0, "llm_b": 1.0})
    assert [s.type for s in rule.combine_document(DOC, [trusted, *others])] == ["LOC"]


def test_vote_labels_rejects_mismatched_grids():
    with pytest.raises(ValueError, match="one tokenisation"):
        vote_labels([["O", "O"], ["O"]])


def test_token_vote_refuses_the_span_only_interface():
    with pytest.raises(TypeError, match="combine_document"):
        TokenVote().combine([out("a", (0, 3, "Dr.", "PERSON"))])


def test_ground_snippets_recovers_offsets_from_returned_text():
    """An LLM returns strings, not offsets; grounding them is the one real alignment problem."""
    spans = ground_snippets(TEXT, [("Weber", "PERSON"), ("Berlin", "LOC")])
    assert [(s.start, s.end) for s in spans] == [(4, 9), (28, 34)]


def test_ground_snippets_survives_normalisation_by_the_model():
    text = "Contact Renée  Dupont today."
    spans = ground_snippets(text, [("renee dupont", "PERSON")])
    assert len(spans) == 1 and text[spans[0].start : spans[0].end] == "Renée  Dupont"


def test_ground_snippets_consumes_repeated_surfaces_left_to_right():
    text = "Weber called Weber."
    spans = ground_snippets(text, [("Weber", "PERSON"), ("Weber", "PERSON")])
    assert [(s.start, s.end) for s in spans] == [(0, 5), (13, 18)]


def test_union_emits_the_widest_member_not_the_cluster_envelope():
    """`union` is a union over overlap *clusters*, not over character ranges.

    It keeps every cluster — that is what distinguishes it from vote and intersection — and emits the
    single widest member span of each. So it never invents an extent, and it also never accumulates
    one: two staggered spans yield the longer of the two, and the characters only the shorter one
    covered are dropped. That makes the rule non-monotone — adding a detector can *reduce* covered
    tokens — which its own docstring's "maximises recall" does not lead you to expect.

    Measured on the max-sensitivity ensembles this costs 0.32 % of identifier tokens on CARDIO:DE
    and 0.04 % on TAB, because real detector spans are usually nested rather than staggered. Pinned
    here so the behaviour is a recorded choice rather than a surprise.
    """
    rule = COMBINATORS.create("union")
    a = DetectorOutput("d", "A", (Span(0, 10, "Anna Marie", "PERSON"),))
    b = DetectorOutput("d", "B", (Span(8, 20, "ie Schmidt X", "PERSON"),))

    assert [(s.start, s.end) for s in rule.combine([a, b])] == [(8, 20)]

    covered = lambda spans: {i for s in spans for i in range(s.start, s.end)}
    assert len(covered(rule.combine([a, b]))) == 12
    assert len(covered(rule.combine([a])) | covered(rule.combine([b]))) == 20


def test_union_chains_transitively_under_single_linkage():
    """A(0,10), B(8,20), C(18,30) become one cluster although A and C are disjoint."""
    rule = COMBINATORS.create("union")
    outputs = [
        DetectorOutput("d", "A", (Span(0, 10, "x" * 10, "PERSON"),)),
        DetectorOutput("d", "B", (Span(8, 20, "y" * 12, "PERSON"),)),
        DetectorOutput("d", "C", (Span(18, 30, "z" * 12, "PERSON"),)),
    ]
    assert [(s.start, s.end) for s in rule.combine(outputs)] == [(8, 20)]


def test_union_clusters_per_entity_type():
    """Overlapping spans of different types are different entities and both survive."""
    rule = COMBINATORS.create("union")
    outputs = [
        DetectorOutput("d", "A", (Span(0, 12, "Weber Clinic", "PERSON"),)),
        DetectorOutput("d", "B", (Span(0, 12, "Weber Clinic", "ORG"),)),
    ]
    assert len(rule.combine(outputs)) == 2
