"""The one prompt and the one parser every LLM detector uses.

Two backends produce LLM spans in this study — the NHR@FAU gateway (:mod:`.llm`) and vLLM on the
cluster's own GPUs (:mod:`.local`) — and their output goes into **the same cache** and the same
ensemble.  If the prompt or the parser drifted between them, the ensemble would be combining
incomparable output while every record still claimed the same ``prompt_version``.  So both live
here, once, and both backends import them rather than owning a copy.

``PROMPT_VERSION`` is written into every cached record.  Bump it whenever ``SYSTEM``, ``TYPES`` or
the windowing changes, so old and new output can never be silently mixed.
"""

from __future__ import annotations

import json
import re
from typing import Iterator, Sequence

__all__ = [
    "PROMPT_VERSION",
    "DEFAULT_TYPES",
    "SYSTEM",
    "build_messages",
    "parse_reply",
    "windows",
]

PROMPT_VERSION = "v2"
"""Bump when the prompt changes: cached records carry it, so old and new output never mix.

v1 -> v2 (2026-09-08): the generation budget went from 2,048 to 16,384 tokens. That is not a
cosmetic change. At 2,048 the reasoning models were truncated mid-thought and returned **no spans
and no error** -- Qwen3.6 scored zero on every CARDIO:DE letter it saw, which an ensemble reads as
"found nothing" rather than "never answered". The v1 records are a different condition and are
archived rather than mixed in."""

DEFAULT_TYPES: tuple[str, ...] = (
    "PERSON",
    "LOC",
    "ORG",
    "DATETIME",
    "EMAIL",
    "PHONE",
    "ID",
    "PROFESSION",
)

SYSTEM = (
    "You extract personally identifying information from text. "
    "Return ONLY a JSON array, no prose, no code fence. "
    'Each element is {"text": "<exact substring from the input>", "type": "<TYPE>"}. '
    "Copy the substring exactly as it appears, including case and punctuation. "
    "Return an empty array if there is nothing to extract."
)

_JSON_RE = re.compile(r"\[.*]", re.DOTALL)


def build_messages(chunk: str, types: Sequence[str] = DEFAULT_TYPES) -> list[dict[str, str]]:
    """The chat messages for one window of text — identical for both backends."""
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Types: {', '.join(types)}\n\n{chunk}"},
    ]


def windows(text: str, max_chars: int) -> Iterator[tuple[int, str]]:
    """Split a document into non-overlapping windows, skipping blank ones.

    Yields ``(start, chunk)``.  The offset is not used for grounding — grounding searches the whole
    document, so a snippet found in one window still maps to the right place — but it is what lets a
    caller reassemble a document's windows after a batched call returns them out of order.
    """
    for start in range(0, max(len(text), 1), max_chars):
        chunk = text[start : start + max_chars]
        if chunk.strip():
            yield start, chunk


def parse_reply(reply: str) -> list[tuple[str, str]]:
    """Parse the JSON array, tolerating truncation at ``max_tokens``.

    A long array cut mid-element leaves invalid JSON; salvaging the complete elements keeps the
    spans the model did produce instead of discarding the whole document.  Note the second branch:
    truncation removes the closing bracket, so the greedy regex matches nothing at all and the
    search has to restart from the opening bracket.
    """
    match = _JSON_RE.search(reply or "")
    if match:
        blob = match.group(0)
    else:
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
    out: list[tuple[str, str]] = []
    for item in items:
        if isinstance(item, dict) and item.get("text"):
            out.append((str(item["text"]), str(item.get("type", "MISC")).upper()))
    return out
