"""Streaming for the models the gateway's ten-minute silence limit would cut (2026-10-04)."""

from __future__ import annotations

import json

from pseudonymkit.detectors.budget import MODEL_CAP, TokenBudget
from pseudonymkit.detectors.llm import STREAMED_MODELS, _assemble_stream

DEEPSEEK = "deepseek-ai/DeepSeek-V4-Flash-0731"


def sse(*events) -> list[bytes]:
    return [f"data: {json.dumps(e)}\n".encode() for e in events] + [b"data: [DONE]\n"]


def test_a_stream_is_reassembled_into_the_ordinary_response_shape() -> None:
    body = _assemble_stream(sse(
        {"choices": [{"delta": {"reasoning_content": "Let me "}}]},
        {"choices": [{"delta": {"reasoning_content": "think."}}]},
        {"choices": [{"delta": {"content": '[{"text": "Ann", '}}]},
        {"choices": [{"delta": {"content": '"type": "PERSON"}]'}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"completion_tokens": 7, "prompt_tokens": 3}},
    ))
    message = body["choices"][0]["message"]
    assert message["content"] == '[{"text": "Ann", "type": "PERSON"}]'
    assert message["reasoning_content"] == "Let me think."
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["usage"] == {"completion_tokens": 7, "prompt_tokens": 3}


def test_a_stream_cut_at_the_cap_says_length() -> None:
    body = _assemble_stream(sse(
        {"choices": [{"delta": {"reasoning_content": "still thinking"}}]},
        {"choices": [{"delta": {}, "finish_reason": "length"}]},
    ))
    assert body["choices"][0]["finish_reason"] == "length"
    assert body["choices"][0]["message"]["content"] is None


def test_comment_and_keepalive_lines_are_ignored() -> None:
    lines = [b": keep-alive\n", b"\n"] + sse({"choices": [{"delta": {"content": "[]"},
                                                         "finish_reason": "stop"}]})
    assert _assemble_stream(lines)["choices"][0]["message"]["content"] == "[]"


def test_only_deepseek_is_streamed_the_rest_run_as_they_were() -> None:
    assert DEEPSEEK in STREAMED_MODELS
    assert "gpt-oss-120b" not in STREAMED_MODELS
    assert "Qwen/Qwen3.6-35B-A3B-FP8" not in STREAMED_MODELS


def test_deepseek_has_a_fixed_cap_the_other_reasoning_models_keep_the_ratio() -> None:
    assert MODEL_CAP[DEEPSEEK] == 131_072
    deepseek, gpt = TokenBudget.for_model(DEEPSEEK), TokenBudget.for_model("gpt-oss-120b")
    assert deepseek.max_tokens(600) == deepseek.max_tokens(6000) == 131_072
    assert gpt.max_tokens(6000) == 29_312 and gpt.max_tokens(600) == 8_192


def test_a_fixed_cap_still_cannot_exceed_the_context_that_is_left() -> None:
    small = TokenBudget(model="x", family="reasoning", ratio=12.0, context=32_768, cap=131_072)
    assert small.max_tokens(6000) == 32_768 - 1024 - 2400
