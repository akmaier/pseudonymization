"""The output budget is derived from the input and the model family, not fixed.

Ratios come from the 1 % sweep of 2026-09-12, per window, over completed replies only: plain p99
0.52 (max 0.65), reasoning p99 4.82 (max 5.02).
"""

from __future__ import annotations

import pytest

from pseudonymkit.detectors.budget import (
    DEFAULT_CONTEXT,
    RATIO,
    TokenBudget,
    family_of,
    fit_ratio,
)

PLAIN = "google/gemma-4-E4B-it"
REASONING = "gpt-oss-120b"


def test_the_two_families_are_recognised():
    assert family_of(PLAIN) == "plain"
    assert family_of(REASONING) == "reasoning"
    assert family_of("some/model-nobody-has-seen") == "plain"


def test_the_cap_scales_with_the_input():
    budget = TokenBudget.for_model(PLAIN)
    small, large = budget.max_tokens(300), budget.max_tokens(6000)
    assert small < large
    assert small >= 512                       # the floor: a stub still needs the JSON scaffolding


def test_a_reasoning_model_gets_far_more_for_the_same_input():
    """It spends the budget thinking before it emits a span; a 2,048 cap once made Qwen score zero."""
    plain = TokenBudget.for_model(PLAIN).max_tokens(6000)
    reasoning = TokenBudget.for_model(REASONING).max_tokens(6000)
    assert reasoning > 4 * plain


def test_a_plain_model_is_still_bounded_well_below_the_old_constant():
    """The cap is looser than it was, and still far from the 16,384 it replaced.

    The original reasoning — every plain-model truncation on the CARDIO:DE sweep was a runaway, so a
    loose cap only pays for more of it — held while the only corpus was German clinical text. It did
    not survive OntoNotes: Phi-4-mini, a plain model, truncated 55.9 % of documents at ratio 1.0, and
    a truncated reply is discarded whole rather than kept short. Doubled to 2.0 (AM, 2026-09-21).
    """
    assert TokenBudget.for_model(PLAIN).max_tokens(6000) < 16384 / 2


def test_the_window_is_what_the_family_can_actually_answer():
    """p tokens of prompt leave (context - p) to reply in, so p <= context / (1 + r)."""
    for model in (PLAIN, REASONING):
        budget = TokenBudget.for_model(model)
        assert budget.max_prompt_tokens + budget.max_tokens(budget.max_chars) <= budget.context


def test_a_reasoning_model_gets_a_smaller_window_than_a_plain_one():
    """At the same context — otherwise this would be measuring the context, not the family."""
    context = 32_768
    assert (TokenBudget.for_model(REASONING, context=context).max_chars
            < TokenBudget.for_model(PLAIN, context=context).max_chars)


def test_a_probed_context_is_used_in_preference_to_the_fallback():
    """GET /models reports no context field, so three limits were probed; the rest fall back."""
    from pseudonymkit.detectors.budget import CONTEXT

    probed = "RedHatAI/gemma-4-31B-it-FP8-block"
    assert CONTEXT[probed] == 262_144
    assert TokenBudget.for_model(probed).context == 262_144
    assert TokenBudget.for_model("gpt-oss-120b").context == DEFAULT_CONTEXT


def test_the_cap_never_exceeds_what_the_context_leaves():
    budget = TokenBudget.for_model(REASONING, context=8192)
    huge = budget.max_tokens(100_000)
    assert huge <= 8192


def test_a_smaller_context_shrinks_the_window():
    assert TokenBudget.for_model(PLAIN, context=8192).max_chars < \
        TokenBudget.for_model(PLAIN, context=32768).max_chars


def test_the_budget_is_recorded_so_a_result_can_be_audited():
    described = TokenBudget.for_model(REASONING).describe()
    assert described["family"] == "reasoning"
    assert described["ratio"] == RATIO["reasoning"]
    assert described["context"] == DEFAULT_CONTEXT


def test_ratios_can_be_refitted_from_cache_records():
    records = [
        {"model": PLAIN, "prompt_tokens": 1000, "completion_tokens": 300, "windows": 1},
        {"model": PLAIN, "prompt_tokens": 1000, "completion_tokens": 500, "windows": 1},
        {"model": REASONING, "prompt_tokens": 1000, "completion_tokens": 4000, "windows": 1},
    ]
    fitted = fit_ratio(records)
    assert fitted["plain"] == pytest.approx(0.5, abs=0.01)
    assert fitted["reasoning"] == pytest.approx(4.0, abs=0.01)


def test_a_truncated_record_is_excluded_from_the_fit():
    """It hit the cap, so its ratio measures the cap rather than the model."""
    records = [
        {"model": PLAIN, "prompt_tokens": 1000, "completion_tokens": 300, "windows": 1},
        {"model": PLAIN, "prompt_tokens": 1000, "completion_tokens": 99999, "windows": 1,
         "truncated": 1},
    ]
    assert fit_ratio(records)["plain"] == pytest.approx(0.3, abs=0.01)


def test_an_explicit_max_tokens_still_wins():
    """A caller pinning the cap — to reproduce an old run — must not be silently overridden."""
    from pseudonymkit.detectors.llm import LlmDetector

    assert "max_tokens" in LlmDetector.__init__.__annotations__


def test_chars_per_token_follows_the_script():
    """One constant is wrong by a factor on CJK and Arabic, and the cap is derived from it."""
    from pseudonymkit.detectors.budget import chars_per_token

    assert chars_per_token("The applicant lived in Bonn.") == pytest.approx(2.5)
    assert chars_per_token("被告人张伟于二零零三年在北京") == pytest.approx(1.0, abs=0.2)
    assert chars_per_token("المدعي يعيش في القاهرة") == pytest.approx(1.5, abs=0.3)
    # Mixed scripts land between, weighted by how much of each is present.
    mixed = chars_per_token("Beijing 北京 2003")
    assert 1.0 < mixed < 2.5


def test_a_chinese_document_is_not_starved_of_output_budget():
    """The defect: a CJK document was costed at 2.5 chars/token and capped at a fraction of need.

    Measured on OntoNotes, Chinese runs at 1.18 characters per token against the constant's 2.5, so a
    1,341-character document was scored as 536 prompt tokens rather than 1,138 and received roughly
    half the cap an English document of the same true size would get. 92.2 % of Qwen3.6's Chinese
    replies truncated, on the *shortest* documents in the corpus, and a truncated reply is discarded
    whole.
    """
    from pseudonymkit.detectors.budget import TokenBudget

    budget = TokenBudget.for_model("Qwen/Qwen3.6-35B-A3B-FP8")
    # Long enough that the ratio decides rather than the reasoning floor, which now covers both.
    chinese = "被告人张伟于二零零三年在北京市海淀区" * 84      # ~1,500 CJK characters
    blind = budget.max_tokens(len(chinese))
    aware = budget.max_tokens(len(chinese), chinese)
    assert aware > blind * 2, (blind, aware)


def test_latin_text_is_unchanged_by_the_script_awareness():
    """English and German must keep the cap they had — only CJK and Arabic were mis-costed."""
    from pseudonymkit.detectors.budget import TokenBudget

    budget = TokenBudget.for_model("Qwen/Qwen3.6-35B-A3B-FP8")
    german = "Der Patient wurde am 3. Januar in der Klinik aufgenommen. " * 20
    assert budget.max_tokens(len(german), german) == budget.max_tokens(len(german))


def test_phi_4_mini_is_budgeted_as_a_reasoning_model():
    """Classified by what it emits, not by what it is called (AM, 2026-09-21).

    Phi-4-mini is not marketed as a reasoning model and was budgeted as plain. It truncated 55.9 % of
    OntoNotes and 78.2 % of CARDIO:DE — the worst in the pool — and 88.9 % of its first Chinese and
    Arabic replies even after the plain ratio was doubled. `Family` is a budget class here, not an
    architectural claim.
    """
    from pseudonymkit.detectors.budget import RATIO, TokenBudget, family_of

    assert family_of("Microsoft/Phi-4-mini-instruct") == "reasoning"
    chinese = "被告人张伟于二零零三年在北京市海淀区" * 75
    budget = TokenBudget.for_model("Microsoft/Phi-4-mini-instruct")
    plain_cap = int(len(chinese) * RATIO["plain"]) + 512
    assert budget.max_tokens(len(chinese), chinese) > plain_cap * 2


def test_a_reasoning_model_gets_a_floor_not_just_a_ratio():
    """A short document must not starve a model whose thinking is fixed cost.

    Qwen3.6 emits a mean of 4,708 completion tokens on OntoNotes Chinese whether the document is 400
    characters or 1,400 — most of the answer is reasoning, which does not scale with the question. A
    ratio-only budget therefore starved exactly the short documents, and 68.8 % of Chinese replies
    truncated even after the ratio was doubled and the character rate corrected.
    """
    from pseudonymkit.detectors.budget import FAMILY_FLOOR, TokenBudget

    budget = TokenBudget.for_model(REASONING)
    short_chinese = "被告人张伟于二零零三年" * 36          # ~400 CJK characters
    assert budget.max_tokens(len(short_chinese), short_chinese) >= FAMILY_FLOOR["reasoning"]


def test_the_floor_does_not_shrink_a_larger_ratio_grant():
    """It is a floor, not a grant: a long document still gets ratio x prompt."""
    from pseudonymkit.detectors.budget import TokenBudget

    budget = TokenBudget.for_model(REASONING)
    long_latin = "The applicant lived in Bonn and worked for the ministry. " * 60
    assert budget.max_tokens(len(long_latin), long_latin) > 8192


def test_a_plain_model_keeps_the_small_floor():
    """Only reasoning models pay for thinking; a plain model on a stub still asks for very little."""
    from pseudonymkit.detectors.budget import FLOOR, TokenBudget

    assert TokenBudget.for_model(PLAIN).max_tokens(80, "a short note") < FLOOR * 4
