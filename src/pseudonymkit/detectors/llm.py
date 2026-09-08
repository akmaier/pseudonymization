"""An LLM detector that runs against the NHR@FAU gateway.

Three properties matter more than the prompt:

* **It writes through a cache.**  Detection is the expensive step; ensembling must never pay for it
  twice.  See :mod:`pseudonymkit.detectors.cache`.
* **It resumes.**  A wall-clock kill or a dropped connection loses at most the document in flight.
* **It grounds its output.**  A language model returns *text*, not offsets, and normalises whitespace
  and diacritics on the way; a literal ``str.find`` silently drops correct spans and depresses that
  model's recall, which would then corrupt every ensemble it appears in.

Credentials are read from ``config/llm_api.toml`` **by this code at runtime only** — the file is not
to be opened, printed or quoted by anyone working on the repository, and the key never enters a log
or a result.

The retry semantics follow the client already proven against this gateway in the group's mailassist
project (``src/mailassist/llm.py``).  They are not generic backoff: the gateway enforces a **rolling
per-key token window**, so a burst is rejected with 429 and an *accept-time* is reported — in the
``Retry-After`` header and, often, only in the body.  Guessing an exponential delay thrashes against
that window; waiting the time the gateway names does not.  The attempt cap is large for the same
reason a batch job cannot finish unless every call eventually completes.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

try:                                    # Python >= 3.11
    import tomllib
except ModuleNotFoundError:             # 3.10, which is what the cluster runs
    import tomli as tomllib             # type: ignore[no-redef]
from typing import Sequence

from ..domain import Document, Span
from .alignment import ground_snippets
from .base import DetectorOutput

__all__ = ["LlmDetector", "PROMPT_VERSION", "DEFAULT_TYPES"]

PROMPT_VERSION = "v1"
"""Bump when the prompt changes: cached records carry it, so old and new output never mix."""

DEFAULT_TYPES = ("PERSON", "LOC", "ORG", "DATETIME", "EMAIL", "PHONE", "ID", "PROFESSION")

_SYSTEM = (
    "You extract personally identifying information from text. "
    "Return ONLY a JSON array, no prose, no code fence. "
    'Each element is {"text": "<exact substring from the input>", "type": "<TYPE>"}. '
    "Copy the substring exactly as it appears, including case and punctuation. "
    "Return an empty array if there is nothing to extract."
)
_JSON_RE = re.compile(r"\[.*]", re.DOTALL)


class LlmDetector:
    """One gateway model, prompted for span extraction."""

    family = "llm"
    _BACKOFF_CAP = 120.0

    def __init__(
        self,
        model: str,
        config_path: Path | str = "config/llm_api.toml",
        types: Sequence[str] = DEFAULT_TYPES,
        max_chars: int = 6000,
        timeout: int = 300,
        max_retries: int = 40,
        max_tokens: int = 16384,
    ) -> None:
        self.model = model
        self.name = f"llm:{model}"
        self._types = tuple(types)
        self._max_chars = max_chars
        # Generous by decision (AM, 2026-09-08): gateway tokens cost us nothing, and a tight budget
        # is actively harmful here. The reasoning models -- gpt-oss-120b, Qwen3.6 -- spend tokens
        # thinking before they emit the JSON array, so a 2048 cap made Qwen return *zero* spans on
        # every CARDIO:DE letter with no error at all: it was truncated mid-thought. A silent empty
        # result is the worst possible failure for a detector pool, because the ensemble treats it
        # as "found nothing" rather than "never answered".
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._max_retries = max_retries
        cfg = tomllib.load(Path(config_path).open("rb"))["llm"]
        self._base = cfg["base_url"].rstrip("/")
        self._key = cfg["api_key"]

    def _post(self, payload: dict) -> tuple[int, str]:
        """POST once, returning (status, body). The read timeout scales with request size.

        The gateway can take minutes on a large request, so a fixed short timeout would abort calls
        that were about to succeed; ``timeout_seconds`` from the config is treated as the floor.
        """
        blob = json.dumps(payload).encode()
        read_timeout = max(self._timeout, 15 + len(blob) / 1024)
        request = urllib.request.Request(
            f"{self._base}/chat/completions",
            data=blob,
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=read_timeout) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    @staticmethod
    def _accept_time(status: int, body: str, headers_retry_after: str | None) -> float | None:
        """When the gateway says it will accept again, in seconds.

        Checked in the ``Retry-After`` header first, then in the body, because this gateway often
        reports the window only in the message text.
        """
        if headers_retry_after:
            try:
                return float(headers_retry_after)
            except ValueError:
                pass
        for pattern in (
            r"(?:retry|reset)[-_ ]?after[\"\']?\s*[:=]\s*[\"\']?(\d+(?:\.\d+)?)",
            r"(?:retry|reset|again|wait|available)\D{0,24}?(\d+(?:\.\d+)?)\s*second",
        ):
            found = re.search(pattern, body or "", re.IGNORECASE)
            if found:
                try:
                    return float(found.group(1))
                except ValueError:
                    continue
        return None

    def _complete(self, text: str) -> tuple[str, str | None, dict]:
        """Call the model, returning ``(text, finish_reason, usage)``.

        ``finish_reason`` is the difference between "the model found nothing" and "the model was cut
        off mid-answer", which are indistinguishable in the span list alone.  It is recorded with
        every document because a silently truncated reply reads to an ensemble as an empty one — the
        exact failure that made Qwen3.6 score zero on every letter under the old 2,048-token cap.

        Waits the accept-time the gateway names rather than guessing.

        HTTP 429 here means the rolling token window is full, not that the quota is exhausted.
        Dropping a planned model on a 429 would silently shrink the detector pool, so it is retried
        until the cap.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"Types: {', '.join(self._types)}\n\n{text}"},
            ],
            "temperature": 0,
            "max_tokens": self._max_tokens,
        }
        delay = 10.0
        last = ""
        for _ in range(self._max_retries):
            try:
                status, body = self._post(payload)
            except Exception as exc:                       # transport, DNS, read timeout
                last = type(exc).__name__
                time.sleep(delay)
                delay = min(delay * 2, self._BACKOFF_CAP)
                continue
            if status == 200:
                try:
                    parsed = json.loads(body)
                    message = parsed["choices"][0].get("message", {})
                except (KeyError, IndexError, json.JSONDecodeError) as exc:
                    last = f"malformed 200: {type(exc).__name__}"
                    time.sleep(delay)
                    continue
                # Reasoning models return content=None with the text in reasoning_content.
                text = message.get("content") or message.get("reasoning_content") or ""
                return text, parsed["choices"][0].get("finish_reason"), parsed.get("usage") or {}
            last = f"HTTP {status}"
            if status in (429, 500, 502, 503, 504):
                wait = self._accept_time(status, body, None)
                if wait is None:
                    wait = delay
                    delay = min(delay * 2, self._BACKOFF_CAP)
                time.sleep(min(wait + 1.0, self._BACKOFF_CAP) )
                continue
            raise RuntimeError(f"gateway refused: HTTP {status}: {body[:200]}")
        raise RuntimeError(f"gateway failed after {self._max_retries} attempts: {last}")

    @staticmethod
    def _parse(reply: str) -> list[tuple[str, str]]:
        """Parse the JSON array, tolerating truncation at ``max_tokens``.

        A long array cut mid-element leaves invalid JSON; salvaging the complete elements keeps the
        spans the model did produce instead of discarding the whole document.
        """
        match = _JSON_RE.search(reply or "")
        if match:
            blob = match.group(0)
        else:
            # Truncation at max_tokens removes the closing bracket, so the greedy regex finds
            # nothing at all. Salvage from the opening bracket instead of discarding the document.
            start = (reply or "").find("[")
            if start < 0:
                return []
            blob = reply[start:]
        try:
            items = json.loads(blob)
        except json.JSONDecodeError:
            cut = blob.rfind("}")
            if cut < 0:
                return []
            try:
                items = json.loads(blob[: cut + 1] + "]")
            except json.JSONDecodeError:
                return []
        out = []
        for item in items:
            if isinstance(item, dict) and item.get("text"):
                out.append((str(item["text"]), str(item.get("type", "MISC")).upper()))
        return out

    def detect(self, document: Document) -> DetectorOutput:
        """Extract spans from one document, in windows if it is long.

        Windows overlap by nothing and are grounded independently; grounding searches the whole
        document, so a snippet found in one window still maps to the right offset.
        """
        return self.detect_with_meta(document)[0]

    def detect_with_meta(self, document: Document) -> tuple[DetectorOutput, dict]:
        """As :meth:`detect`, plus what the gateway said about how the reply ended.

        The metadata is per **window**, because a long document is several calls and only some of
        them may have been truncated.  ``truncated`` counts the windows whose ``finish_reason`` was
        ``"length"`` — those are documents whose span list is short because the model ran out of
        budget, not because the text was clean.
        """
        snippets: list[tuple[str, str]] = []
        reasons: list[str | None] = []
        completion_tokens = 0
        prompt_tokens = 0
        text = document.text
        for start in range(0, max(len(text), 1), self._max_chars):
            chunk = text[start : start + self._max_chars]
            if not chunk.strip():
                continue
            reply, reason, usage = self._complete(chunk)
            snippets.extend(self._parse(reply))
            reasons.append(reason)
            completion_tokens += int(usage.get("completion_tokens") or 0)
            prompt_tokens += int(usage.get("prompt_tokens") or 0)
        spans: list[Span] = [
            Span(s.start, s.end, s.text, s.type, source=self.name)
            for s in ground_snippets(text, snippets)
        ]
        meta = {
            "windows": len(reasons),
            "finish_reasons": reasons,
            "truncated": sum(1 for r in reasons if r == "length"),
            "completion_tokens": completion_tokens,
            "prompt_tokens": prompt_tokens,
            "max_tokens": self._max_tokens,
        }
        return DetectorOutput(document.doc_id, self.name, tuple(spans)), meta
