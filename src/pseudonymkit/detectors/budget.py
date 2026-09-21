"""How many output tokens one span-extraction request needs, and how much input to send it.

A fixed ``max_tokens`` cannot be right for this task. The reply is a JSON array of spans, so its
length scales with the **input**; and a reasoning model spends most of its budget thinking before it
emits a single span, so the same input costs it several times more than it costs a plain one. One
constant serves neither: 16,384 truncated the reasoning models on every long CARDIO:DE letter while
being four times more than the plain models ever used.

## The numbers here are measured, not chosen

From the 1 % sweep of 2026-09-12 (746 documents, six gateway models, 238 completed replies), taking
the ratio of completion to prompt tokens **per window**, since the cap applies per request:

| family | median | p90 | p99 | max | n |
|---|---:|---:|---:|---:|---:|
| plain — `gemma-4-31B`, `gemma-4-E4B`, `Mistral-Small-3.2`, `Magistral-Small` | 0.29 | 0.42 | 0.52 | 0.65 | 186 |
| reasoning — `Qwen3.6-35B`, `gpt-oss-120b` | 3.04 | 4.45 | 4.82 | 5.02 | 52 |

:data:`RATIO` takes the p99 and rounds up, which leaves headroom over the observed maximum in both
families. Re-measure it when the model pool changes: :func:`fit_ratio` does that from a cache.

## Two knobs, and they are not independent

Given a context limit *L*, a prompt of *p* tokens can be answered with at most *L − p* output
tokens. If the family needs *r·p* and *r·p > L − p*, no cap can help — the **window** is too big,
and it is the window that has to shrink:

    p ≤ L / (1 + r)

That is why :class:`TokenBudget` sizes the window and the cap together. For a 32,768 limit, less a
1,024-token reserve: a plain model at r = 1 may be sent 15,872 prompt tokens per window, a reasoning
model at r = 6 only 4,534. Sending a reasoning model the plain model's window guarantees truncation.

## Truncation is not a partial answer

A truncated reply is a runaway, not a short one — measured on the same sweep, Magistral averages
53.8 spans on a normal CARDIO:DE letter and 279.0 on a truncated one, Mistral 68.5 against 352.8.
The consumer drops them (:mod:`pseudonymkit.construction`), so a budget that truncates does not
merely lose detail, it loses the document.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

__all__ = ["Family", "CONTEXT", "RATIO", "REASONING_MODELS", "SCRIPT_CHARS_PER_TOKEN",
           "TokenBudget", "chars_per_token", "family_of", "fit_ratio"]

Family = str

RATIO: Mapping[Family, float] = {"plain": 1.0, "reasoning": 6.0}
"""Output tokens to allow per input token, by family — the measured p99 rounded up.

Plain: p99 0.52, max 0.65 → 1.0 leaves 54 % headroom over anything observed.
Reasoning: p99 4.82, max 5.02 → 6.0 leaves 20 %.
"""

REASONING_MODELS: frozenset[str] = frozenset({
    "gpt-oss-120b",
    "Qwen/Qwen3.6-35B-A3B-FP8",
    "deepseek-ai/DeepSeek-V4-Flash-0731",
})
"""Models that return ``message.reasoning_content`` and spend the budget before answering.

DeepSeek is listed although it is excluded from the run (AM, 2026-09-08, backend down): if it is ever
re-admitted it must not silently inherit the plain budget.
"""

CONTEXT: Mapping[str, int] = {
    "RedHatAI/gemma-4-31B-it-FP8-block": 262_144,
    "ibm-granite/granite-4.1-3b": 65_536,
    "GaleneAI/Magistral-Small-2509-FP8-Dynamic": 131_072,
    "google/gemma-4-E4B-it": 131_072,
    "Microsoft/Phi-4-mini-instruct": 16_384,
}
"""Measured 2026-09-12, not assumed.

``GET /models`` reports only ``id``/``object``/``owned_by``, so the limits were probed: a request
with an absurd ``max_tokens`` makes vLLM name its own — *"max_tokens=10000000 cannot be greater than
max_model_len=max_total_tokens=262144"*.  Three deployments answered that way.  ``gpt-oss-120b`` and
``Mistral-Small-3.2`` **accepted** the absurd value without validating, and ``Qwen3.6`` returned a
rate limit before it got that far, so those three fall back to :data:`DEFAULT_CONTEXT`.

Context is not the binding constraint in practice.  At the 6,000-character window a reasoning model
asks for ~12,500 tokens in total, comfortably inside even the conservative fallback.  What actually
throttles the run is the gateway's **per-key rolling token budget** — the 429 reads *"Limit type:
tokens. Current limit: 100000"* — which is a reason to size ``max_tokens`` correctly rather than
generously, quite apart from truncation.
"""

DEFAULT_CONTEXT = 32_768
"""Fallback for a model whose limit could not be probed. Conservative on purpose: assuming too much
truncates, assuming too little only makes the window smaller."""

SCRIPT_CHARS_PER_TOKEN: Mapping[str, float] = {"cjk": 1.0, "arabic": 1.5, "default": 2.5}
"""Characters per token **by script**, because one constant is wrong by a factor on two of them.

Measured against what the gateway itself reports for prompt tokens, over OntoNotes:

    English   3.81 chars/token     the 2.5 default is conservative, which is the safe direction
    Arabic    1.71                 2.5 overstates it by 1.5x
    Chinese   1.18                 2.5 overstates it by 2.1x

Overestimating characters-per-token *under*estimates the prompt, and the cap is
``prompt_tokens x ratio``, so it underestimates the cap by the same factor. A 1,341-character
Chinese document was costed as 536 tokens when it is really 1,138, and received a 3,728-token cap
where an English document of the same true size would have received about 7,800. **92.2 % of
Qwen3.6's Chinese replies truncated** — on the shortest documents in the corpus — and truncated
replies are dropped entirely by the consumer, so its Chinese sensitivity read 0.156 against 0.371 on
the documents that survived. The one Chinese-developed model in the pool was being starved of output
budget on Chinese.

The values err low deliberately: too low only shrinks the window and raises the cap, and neither
costs a document."""


def chars_per_token(text: str) -> float:
    """Characters per token for this text, from the scripts it is written in.

    A weighted mean rather than a lookup, because real documents mix scripts — a Chinese newswire
    article carries Latin digits and names, and an English one can carry a CJK quotation.
    """
    if not text:
        return SCRIPT_CHARS_PER_TOKEN["default"]
    cjk = arabic = 0
    for ch in text:
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF or 0x3000 <= code <= 0x303F:
            cjk += 1
        elif 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F or 0xFB50 <= code <= 0xFDFF:
            arabic += 1
    other = len(text) - cjk - arabic
    total = float(len(text))
    return (cjk * SCRIPT_CHARS_PER_TOKEN["cjk"]
            + arabic * SCRIPT_CHARS_PER_TOKEN["arabic"]
            + other * SCRIPT_CHARS_PER_TOKEN["default"]) / total


CHARS_PER_TOKEN = 2.5
"""Fallback where no text is in hand — the window sizing, which predates a document.

Phi-4-mini reports 369 prompt tokens for 1,000 characters of German clinical text: **2.71 characters
per token**.  The earlier value of 3.5 was not conservative but optimistic, and in the direction that
hurts: a *higher* figure divides the character count by more and so *under*-estimates what a chunk
costs, which makes the window too large.  2.5 sits below the worst case measured, and erring low only
shrinks the window.
"""

FLOOR = 512
"""Smallest cap worth issuing. A one-line Enron stub still needs room for the JSON scaffolding."""


def family_of(model: str) -> Family:
    return "reasoning" if model in REASONING_MODELS else "plain"


@dataclass(frozen=True)
class TokenBudget:
    """The output cap and the input window for one model, derived from each other."""

    model: str
    family: Family
    ratio: float
    context: int = DEFAULT_CONTEXT
    reserve: int = 1024
    """Held back for the system prompt, the instructions and the gateway's own overhead."""

    @classmethod
    def for_model(
        cls, model: str, context: int | None = None, ratio: float | None = None
    ) -> TokenBudget:
        """``context`` defaults to the model's measured limit, else :data:`DEFAULT_CONTEXT`."""
        family = family_of(model)
        return cls(
            model=model,
            family=family,
            ratio=ratio or RATIO[family],
            context=context or CONTEXT.get(model, DEFAULT_CONTEXT),
        )

    @property
    def max_prompt_tokens(self) -> int:
        """Largest prompt whose expected answer still fits: ``p ≤ (L − reserve) / (1 + r)``."""
        return max(FLOOR, int((self.context - self.reserve) / (1.0 + self.ratio)))

    @property
    def max_chars(self) -> int:
        """That window, in characters — what the detector actually slices on."""
        return int(self.max_prompt_tokens * CHARS_PER_TOKEN)

    def max_tokens(self, prompt_chars: int, text: str | None = None) -> int:
        """The cap for one request, from the input actually being sent.

        Scaling with the input is what makes this a budget rather than a constant: a 300-character
        Enron stub asks for the floor, a 20,000-character letter asks for its share, and neither is
        given the other's.

        ``text`` lets the character-to-token rate come from the script actually present rather than
        from a constant calibrated on German — see :func:`chars_per_token`. Without it the constant
        is used, which is right for Latin script and starves CJK and Arabic.
        """
        rate = chars_per_token(text) if text is not None else CHARS_PER_TOKEN
        prompt_tokens = max(1, math.ceil(prompt_chars / rate))
        want = math.ceil(prompt_tokens * self.ratio) + FLOOR
        headroom = self.context - self.reserve - prompt_tokens
        return max(FLOOR, min(want, headroom))

    def describe(self) -> dict[str, object]:
        return {
            "family": self.family,
            "ratio": self.ratio,
            "context": self.context,
            "max_prompt_tokens": self.max_prompt_tokens,
            "max_chars": self.max_chars,
        }


def fit_ratio(
    records: Iterable[Mapping[str, object]], quantile: float = 0.99
) -> dict[Family, float]:
    """Re-measure :data:`RATIO` from cache records — use when the model pool changes.

    Only completed replies count: a truncated one hit the cap, so its ratio is a measurement of the
    cap rather than of the model.
    """
    by_family: dict[Family, list[float]] = {}
    for record in records:
        if record.get("error") is not None or record.get("truncated"):
            continue
        prompt = float(record.get("prompt_tokens") or 0)
        completion = float(record.get("completion_tokens") or 0)
        windows = float(record.get("windows") or 1) or 1.0
        if prompt <= 0:
            continue
        model = str(record.get("model") or "")
        by_family.setdefault(family_of(model), []).append(
            (completion / windows) / (prompt / windows)
        )
    out: dict[Family, float] = {}
    for family, ratios in by_family.items():
        ratios.sort()
        # Round *up*: this is an upper quantile used to size a budget, and truncating would take
        # the p99 of two observations to be the smaller of them.
        index = min(len(ratios) - 1, math.ceil(quantile * (len(ratios) - 1)))
        out[family] = ratios[index]
    return out


def fit_ratio_from_cache(root: Path | str, quantile: float = 0.99) -> dict[Family, float]:
    """:func:`fit_ratio` over every JSONL under a detector-cache directory."""
    records = []
    for path in sorted(Path(root).glob("*/*.jsonl")):
        model = path.stem.replace("llm:", "").replace("__", "/")
        for line in path.open(encoding="utf-8"):
            record = json.loads(line)
            record.setdefault("model", model)
            records.append(record)
    return fit_ratio(records, quantile)
