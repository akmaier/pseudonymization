"""Utility protocol: per-document vectors, paired tests, effect sizes, BH correction."""

from __future__ import annotations

import math

import pytest

from pseudonymkit.metrics.utility import (
    PairedComparison,
    ScoreVector,
    UtilityReport,
    absolute_error,
    benjamini_hochberg,
    compare,
    exact_match,
    mcnemar,
    multilabel_micro_f1,
    span_f1,
    spearman,
    wilcoxon_signed_rank,
)


def vector(condition: str, scores, kind="continuous", task="t", ids=None) -> ScoreVector:
    ids = ids or tuple(f"d{i}" for i in range(len(scores)))
    return ScoreVector(task, condition, tuple(ids), tuple(float(s) for s in scores), kind)


# ------------------------------------------------------------------------------------- scorers


def test_span_f1_rewards_exact_matches_only():
    gold = [(0, 5, "PERSON"), (10, 14, "LOC")]
    assert span_f1(gold, gold) == 1.0
    assert span_f1(gold, [(0, 5, "PERSON")]) == pytest.approx(2 / 3)
    # Right span, wrong label: a miss when typed, a hit when untyped.
    assert span_f1(gold, [(0, 5, "ORG"), (10, 14, "LOC")]) == pytest.approx(0.5)
    assert span_f1(gold, [(0, 5, "ORG"), (10, 14, "LOC")], typed=False) == 1.0


def test_span_f1_empty_document_is_a_success_not_a_failure():
    # No gold and no prediction means the system was right that nothing was there.
    assert span_f1([], []) == 1.0
    assert span_f1([], [(0, 3, "PERSON")]) == 0.0
    assert span_f1([(0, 3, "PERSON")], []) == 0.0


def test_multilabel_micro_f1():
    assert multilabel_micro_f1({"3", "6"}, {"3", "6"}) == 1.0
    assert multilabel_micro_f1({"3", "6"}, {"3"}) == pytest.approx(2 / 3)
    assert multilabel_micro_f1(set(), set()) == 1.0


def test_exact_match_and_absolute_error():
    assert exact_match("inbox", "inbox") == 1.0
    assert exact_match("inbox", "sent") == 0.0
    assert absolute_error(0.8, 0.5) == pytest.approx(0.3)


def test_spearman_is_rank_based():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)
    # Monotone but non-linear: Pearson would not give 1.0, Spearman does.
    assert spearman([1, 2, 3, 4], [1, 4, 9, 16]) == pytest.approx(1.0)
    assert math.isnan(spearman([1, 1, 1], [1, 2, 3]))


# ------------------------------------------------------------------------------- score vectors


def test_score_vector_summary_uses_sample_sd():
    v = vector("original", [0.0, 1.0])
    assert v.n == 2
    assert v.mean == pytest.approx(0.5)
    assert v.sd == pytest.approx(0.7071, abs=1e-3)  # ddof=1, not the population 0.5


def test_score_vector_rejects_misaligned_and_duplicate_ids():
    with pytest.raises(ValueError, match="doc_ids"):
        ScoreVector("t", "c", ("a", "b"), (1.0,), "continuous")
    with pytest.raises(ValueError, match="duplicate"):
        ScoreVector("t", "c", ("a", "a"), (1.0, 1.0), "continuous")


def test_pairing_takes_the_intersection_not_the_positions():
    reference = vector("original", [1.0, 0.5, 0.0], ids=("a", "b", "c"))
    condition = vector("cell", [0.2, 0.9], ids=("c", "a"))
    a, b, shared = reference.paired_with(condition)
    assert shared == ("a", "c")
    assert list(a) == [1.0, 0.0]  # reference order preserved
    assert list(b) == [0.9, 0.2]  # condition realigned onto it, not zipped positionally


# --------------------------------------------------------------------------------------- tests


def test_wilcoxon_detects_a_consistent_drop_and_signs_the_effect():
    reference = [0.9] * 12
    condition = [0.7] * 12
    statistic, p, effect = wilcoxon_signed_rank(reference, condition)
    assert p < 0.01
    assert effect == pytest.approx(-1.0)  # every document got worse
    assert wilcoxon_signed_rank(condition, reference)[2] == pytest.approx(1.0)


def test_wilcoxon_on_identical_vectors_is_not_an_error():
    # A cell that changes nothing the task depends on: p = 1, effect 0 — the correct answer.
    statistic, p, effect = wilcoxon_signed_rank([0.5] * 8, [0.5] * 8)
    assert (statistic, p, effect) == (0.0, 1.0, 0.0)


def test_wilcoxon_on_empty_input_is_nan_not_a_crash():
    assert all(math.isnan(x) for x in wilcoxon_signed_rank([], []))


def test_mcnemar_counts_only_discordant_pairs():
    # 6 documents the reference got right and the condition wrong; 0 the other way.
    reference = [1, 1, 1, 1, 1, 1, 1, 0]
    condition = [0, 0, 0, 0, 0, 0, 1, 0]
    statistic, p, b, c = mcnemar(reference, condition)
    assert (b, c) == (6, 0)
    assert p == pytest.approx(2 ** -5)  # exact binomial, 6 discordant all one way


def test_mcnemar_switches_to_chi_square_above_25_discordant_pairs():
    reference = [1] * 30 + [0] * 30
    condition = [0] * 30 + [1] * 30  # 30 vs 30, perfectly balanced
    statistic, p, b, c = mcnemar(reference, condition)
    assert (b, c) == (30, 30)
    # Edwards' continuity correction gives (|b-c|-1)^2 / (b+c) = 1/60, so p is high but not 1.
    assert statistic == pytest.approx(1 / 60)
    assert p > 0.85  # balanced discordance is no evidence of a difference


def test_mcnemar_with_no_disagreement():
    assert mcnemar([1, 0, 1], [1, 0, 1]) == (0.0, 1.0, 0, 0)


# ----------------------------------------------------------------------------------- compare


def test_compare_picks_mcnemar_for_binary_and_wilcoxon_for_continuous():
    reference = vector("original", [1, 1, 1, 1, 1, 1], kind="binary")
    condition = vector("cell", [0, 0, 0, 0, 1, 1], kind="binary")
    result = compare(reference, condition)
    assert result.test == "mcnemar"
    assert result.effect_name == "accuracy_difference"
    assert result.effect == pytest.approx(-4 / 6)
    assert result.discordant == (4, 0)

    result = compare(vector("original", [0.9] * 10), vector("cell", [0.6] * 10))
    assert result.test == "wilcoxon"
    assert result.effect_name == "rank_biserial"
    assert result.median_difference == pytest.approx(-0.3)


def test_compare_refuses_to_mix_kinds():
    with pytest.raises(ValueError, match="kind mismatch"):
        compare(vector("original", [1, 0], kind="binary"), vector("cell", [1.0, 0.5]))


def test_compare_reports_the_reference_mean_beside_the_condition():
    result = compare(vector("original", [1.0, 0.8, 0.6]), vector("cell", [0.5, 0.4, 0.3]))
    assert result.reference_mean == pytest.approx(0.8)
    assert result.condition_mean == pytest.approx(0.4)


# ---------------------------------------------------------------------- multiplicity correction


def comparison(p: float, name: str = "c") -> PairedComparison:
    return PairedComparison(
        task="t", reference="original", condition=name, test="wilcoxon", n=10,
        statistic=0.0, p_value=p, effect=0.0, effect_name="rank_biserial",
        reference_mean=0.0, condition_mean=0.0, median_difference=0.0,
    )


def test_benjamini_hochberg_matches_the_worked_example():
    # Benjamini & Hochberg (1995) §2 example.
    p_values = [0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344,
                0.0459, 0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.0000]
    out = benjamini_hochberg([comparison(p, f"c{i}") for i, p in enumerate(p_values)])
    rejected = [c for c in out if c.significant]
    assert len(rejected) == 4  # the first four, as in the paper
    assert [c.condition for c in rejected] == ["c0", "c1", "c2", "c3"]


def test_benjamini_hochberg_is_monotone_and_preserves_order():
    out = benjamini_hochberg([comparison(0.04, "a"), comparison(0.01, "b"), comparison(0.9, "c")])
    assert [c.condition for c in out] == ["a", "b", "c"]  # input order kept
    q = {c.condition: c.q_value for c in out}
    assert q["b"] <= q["a"] <= q["c"]
    assert q["a"] == pytest.approx(0.06)  # 0.04 * 3 / 2
    assert q["b"] == pytest.approx(0.03)  # 0.01 * 3 / 1


def test_benjamini_hochberg_excludes_nan_from_the_family_size():
    # A degenerate cell must not shrink every other comparison's chance of surviving.
    out = benjamini_hochberg([comparison(0.02, "a"), comparison(float("nan"), "b")])
    q = {c.condition: c.q_value for c in out}
    assert q["a"] == pytest.approx(0.02)  # m = 1, not 2
    assert q["b"] is None


# ---------------------------------------------------------------------------------- the report


def test_report_requires_the_original_text_as_reference():
    with pytest.raises(ValueError, match="original"):
        UtilityReport.build(vector("some_cell", [1.0]), [])


def test_report_flags_a_task_the_frozen_model_cannot_do():
    report = UtilityReport.build(
        vector("original", [0.5, 0.5, 0.5], kind="binary"),
        [vector("cell", [0.5, 0.5, 0.5], kind="binary")],
        chance_level=0.5,
    )
    ok, reason = report.interpretable()
    assert not ok
    assert "chance level" in reason


def test_report_rows_lead_with_the_original_score():
    report = UtilityReport.build(
        vector("original", [0.9] * 10),
        [vector("cell_a", [0.6] * 10), vector("cell_b", [0.85] * 10)],
        chance_level=0.1,
    )
    rows = report.rows()
    assert rows[0]["condition"] == "original"
    assert rows[0]["comparison"] is None
    assert [r["condition"] for r in rows[1:]] == ["cell_a", "cell_b"]
    assert all(r["comparison"]["q_value"] is not None for r in rows[1:])
    assert report.interpretable()[0]


def test_report_record_round_trips_the_full_vectors():
    report = UtilityReport.build(vector("original", [0.9, 0.8]), [vector("cell", [0.5, 0.4])])
    record = report.to_record()
    assert record["reference"]["scores"] == [0.9, 0.8]
    assert record["conditions"][0]["doc_ids"] == ["d0", "d1"]
    assert record["comparisons"][0]["test"] == "wilcoxon"
