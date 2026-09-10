"""One client for the NHR@FAU gateway, shared by everything that prompts a model.

``experiment_plan.md`` §14 puts three roles on this gateway — the LLM detectors, the A4 attacker and
the zero-shot utility tasks — and they are three different consumers of one HTTP contract.  Writing
the contract once means a change to the retry policy, the truncation handling or the reasoning-model
quirk lands in all three at once.

## The retry policy is not generic backoff

The gateway enforces a **rolling per-key token window**.  A burst is rejected with ``429`` and an
*accept-time* is reported — in the ``Retry-After`` header and, more often, only in the body text.
Guessing an exponential delay thrashes against that window; waiting the time the gateway names does
not.  ``429`` here means *the model is cold or the window is full*, not that the quota is exhausted,
so it is retried until the attempt cap.  **Dropping a planned model because it returned 429 would
silently shrink the detector pool, which §1 forbids.**

## Two failures that are invisible unless they are recorded

**A truncated reply is indistinguishable from an empty one.**  Under a 2,048-token budget one
reasoning model returned zero spans on every document it saw, with no error at all: it was cut off
mid-thought, and the ensemble read "found nothing" rather than "never answered" (§12.2).  Every reply
therefore carries its ``finish_reason`` and its token usage, and the caller is expected to keep them.

**Reasoning models put the answer somewhere else.**  ``gpt-oss-120b``, DeepSeek and Qwen3.6 may
return ``message.content = null`` with the text in ``message.reasoning_content``.  Both are read.

Credentials come from ``config/llm_api.toml`` **at runtime, by this code only**.  The file is not to
be opened, printed, diffed or quoted by anyone working on the repository, and the key never enters a
log, a results row or a commit message.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

try:                                    # Python >= 3.11
    import tomllib
except ModuleNotFoundError:             # 3.10, which is what the cluster runs
    import tomli as tomllib             # type: ignore[no-redef]

__all__ = ["Reply", "GatewayClient", "list_models"]

DEFAULT_CONFIG = "config/llm_api.toml"

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_ACCEPT_TIME_PATTERNS = (
    r"(?:retry|reset)[-_ ]?after[\"\']?\s*[:=]\s*[\"\']?(\d+(?:\.\d+)?)",
    r"(?:retry|reset|again|wait|available)\D{0,24}?(\d+(?:\.\d+)?)\s*second",
)


@dataclass(frozen=True, slots=True)
class Reply:
    """One completion, with everything a results row needs to know about how it ended."""

    text: str
    finish_reason: str | None
    usage: Mapping[str, Any] = field(default_factory=dict)
    model: str = ""

    @property
    def truncated(self) -> bool:
        """``True`` when the model ran out of budget rather than finishing its answer."""
        return self.finish_reason == "length"

    def meta(self) -> dict[str, object]:
        return {
            "model": self.model,
            "finish_reason": self.finish_reason,
            "truncated": self.truncated,
            "completion_tokens": int(self.usage.get("completion_tokens") or 0),
            "prompt_tokens": int(self.usage.get("prompt_tokens") or 0),
        }


class GatewayClient:
    """A minimal OpenAI-compatible chat client with this gateway's own retry semantics."""

    _BACKOFF_CAP = 120.0

    def __init__(
        self,
        model: str,
        config_path: Path | str = DEFAULT_CONFIG,
        *,
        timeout: int = 300,
        max_retries: int = 40,
        max_tokens: int = 16384,
    ) -> None:
        self.model = model
        # Generous by decision (AM, 2026-09-08): gateway tokens cost nothing, and a tight budget is
        # actively harmful — see the module docstring on truncation.
        self.max_tokens = max_tokens
        self._timeout = timeout
        self._max_retries = max_retries
        config = tomllib.load(Path(config_path).open("rb"))["llm"]
        self._base = config["base_url"].rstrip("/")
        self._key = config["api_key"]

    # ------------------------------------------------------------------ transport

    def _post(self, path: str, payload: dict) -> tuple[int, str]:
        """POST once, returning ``(status, body)``.  The read timeout scales with request size."""
        blob = json.dumps(payload).encode()
        read_timeout = max(self._timeout, 15 + len(blob) / 1024)
        request = urllib.request.Request(
            f"{self._base}{path}",
            data=blob,
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=read_timeout) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    @staticmethod
    def accept_time(body: str, retry_after: str | None = None) -> float | None:
        """When the gateway says it will accept again, in seconds, or ``None`` if it did not say."""
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        for pattern in _ACCEPT_TIME_PATTERNS:
            found = re.search(pattern, body or "", re.IGNORECASE)
            if found:
                try:
                    return float(found.group(1))
                except ValueError:
                    continue
        return None

    # ------------------------------------------------------------------ chat

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Reply:
        """One chat completion, retried until the gateway answers or the attempt cap is reached."""
        payload = {
            "model": self.model,
            "messages": [dict(m) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        delay = 10.0
        last = ""
        for _ in range(self._max_retries):
            try:
                status, body = self._post("/chat/completions", payload)
            except Exception as exc:                       # transport, DNS, read timeout
                last = type(exc).__name__
                time.sleep(delay)
                delay = min(delay * 2, self._BACKOFF_CAP)
                continue
            if status == 200:
                try:
                    parsed = json.loads(body)
                    choice = parsed["choices"][0]
                    message = choice.get("message", {})
                except (KeyError, IndexError, json.JSONDecodeError) as exc:
                    last = f"malformed 200: {type(exc).__name__}"
                    time.sleep(delay)
                    continue
                return Reply(
                    text=message.get("content") or message.get("reasoning_content") or "",
                    finish_reason=choice.get("finish_reason"),
                    usage=parsed.get("usage") or {},
                    model=self.model,
                )
            last = f"HTTP {status}"
            if status in _RETRY_STATUS:
                wait = self.accept_time(body)
                if wait is None:
                    wait = delay
                    delay = min(delay * 2, self._BACKOFF_CAP)
                time.sleep(min(wait + 1.0, self._BACKOFF_CAP))
                continue
            raise RuntimeError(f"gateway refused: HTTP {status}: {body[:200]}")
        raise RuntimeError(f"gateway failed after {self._max_retries} attempts: {last}")

    def ask(self, system: str, user: str, **kwargs: object) -> Reply:
        """The common two-message shape: one instruction, one payload."""
        return self.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            **kwargs,  # type: ignore[arg-type]
        )


def list_models(config_path: Path | str = DEFAULT_CONFIG, timeout: int = 60) -> list[str]:
    """Ask the gateway which models it serves **right now**.

    §7 does not fix the LLM list in advance: *every chat model the gateway serves at run time* is
    used, DeepSeek excluded, and **which models were live is recorded with the run** because
    availability is part of the experimental record.  A run that hard-codes the list cannot record
    that, so it is asked rather than assumed.
    """
    config = tomllib.load(Path(config_path).open("rb"))["llm"]
    request = urllib.request.Request(
        f"{config['base_url'].rstrip('/')}/models",
        headers={"Authorization": f"Bearer {config['api_key']}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", "replace"))
    return sorted(str(entry["id"]) for entry in payload.get("data", []) if entry.get("id"))
