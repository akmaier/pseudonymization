"""Putting detector outputs on a common grid before voting.

Fiscus's ROVER (1997) aligns several recognisers' word sequences into a transition network by
dynamic programming, then votes at each slot.  It needs the alignment step because ASR systems emit
*unaligned* sequences over a reference nobody has.

Our detectors all read the same string and emit character offsets into it, so the common coordinate
system is given and no dynamic programming is required.  What ROVER does *after* aligning is still
needed, and span-level overlap clustering only does part of it:

1. **Boundary disagreement** — handled by clustering, but single-link clustering chains: A(0,10),
   B(8,20), C(18,30) end up in one cluster although A and C do not overlap.  :func:`cluster_spans`
   therefore offers an IoU criterion as well.
2. **Type disagreement** — two detectors that agree an entity is present but disagree whether it is
   PERSON or ORG should count as agreement on *presence* and a tie on *type*.  Clustering per type
   scores that as two minorities and drops both.  Token voting resolves it.
3. **No shared unit to vote in** — a span-level rule votes on whole spans, so a detector that got
   three tokens of a four-token name right contributes nothing.  ROVER's per-slot vote is finer.

This module supplies the ROVER analogue for sequence labelling: project every detector's spans onto
one tokenisation as BIO tags, vote per token, and decode back to spans.  The grid is exact rather
than estimated, which is the one respect in which our problem is easier than ASR's.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Mapping, Sequence

from ..domain import Span

__all__ = [
    "tokenise",
    "spans_to_bio",
    "bio_to_spans",
    "ground_snippets",
    "text_windows",
    "dedupe_spans",
]

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def tokenise(text: str) -> list[tuple[int, int]]:
    """The voting grid: word and punctuation tokens as ``(start, end)`` offsets.

    Deterministic and dependency-free on purpose.  The grid only has to be *shared*; it does not
    have to match any model's own tokenizer, because spans are projected onto it rather than
    produced by it.
    """
    return [(m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


def spans_to_bio(spans: Sequence[Span], tokens: Sequence[tuple[int, int]]) -> list[str]:
    """Project spans onto the token grid as BIO labels.

    A token belongs to a span when it overlaps it at all, so a span whose boundaries fall inside a
    token still claims that token — detectors disagree about punctuation and clitics constantly.
    """
    labels = ["O"] * len(tokens)
    for span in sorted(spans, key=lambda s: (s.start, -s.length)):
        first = True
        for i, (ts, te) in enumerate(tokens):
            if ts < span.end and span.start < te:
                if labels[i] != "O":
                    continue
                labels[i] = f"{'B' if first else 'I'}-{span.type}"
                first = False
    return labels


def bio_to_spans(labels: Sequence[str], tokens: Sequence[tuple[int, int]], text: str) -> list[Span]:
    """Decode BIO labels back into character spans."""
    spans: list[Span] = []
    start: int | None = None
    type_: str | None = None
    for i, label in enumerate(labels):
        tag, _, name = label.partition("-")
        if tag == "B" or (tag == "I" and (start is None or name != type_)):
            if start is not None and type_ is not None:
                spans.append(_close(start, tokens[i - 1][1], type_, text))
            start, type_ = tokens[i][0], name
        elif tag == "O":
            if start is not None and type_ is not None:
                spans.append(_close(start, tokens[i - 1][1], type_, text))
            start, type_ = None, None
    if start is not None and type_ is not None:
        spans.append(_close(start, tokens[-1][1], type_, text))
    return spans


def _close(start: int, end: int, type_: str, text: str) -> Span:
    return Span(start=start, end=end, text=text[start:end], type=type_, source="vote")


def vote_labels(
    per_detector: Sequence[Sequence[str]],
    weights: Sequence[float] | None = None,
    threshold: float | None = None,
) -> list[str]:
    """Vote a single label sequence out of several, one token at a time.

    This is the step ROVER performs at each slot of its transition network, and the decision is
    made in two stages, which matters:

    1. **Presence** — the total weight of all non-``O`` labels is compared with ``threshold``
       (default: a strict majority of the total weight).  Evidence that *something* is here is
       therefore pooled across types.
    2. **Type** — among the non-``O`` labels, the heaviest type wins.

    Doing it in that order is the difference from per-type span clustering.  Four detectors split
    two-PERSON / two-ORG all agree an entity is present; clustering per type sees two minorities of
    two and discards both, whereas this keeps the entity and settles the type by weight.  A
    pseudonymisation study cares far more about the first question than the second: a missed entity
    leaks, a mislabelled one is still replaced.

    ``B``/``I`` is decided within the winning type by the same weights, so a boundary that most
    detectors marked survives and two adjacent entities of one type are not silently merged.  Ties
    between types are broken toward the label seen first in detector order, so the ordering of the
    pool is part of the experimental record.
    """
    if not per_detector:
        return []
    n = len(per_detector[0])
    if any(len(seq) != n for seq in per_detector):
        raise ValueError("label sequences must share one tokenisation")
    w = list(weights) if weights is not None else [1.0] * len(per_detector)
    if len(w) != len(per_detector):
        raise ValueError("one weight per detector is required")
    need = threshold if threshold is not None else sum(w) / 2.0

    out: list[str] = []
    for i in range(n):
        by_type: dict[str, float] = {}
        begins: dict[str, float] = {}
        order: list[str] = []
        present = 0.0
        for seq, weight in zip(per_detector, w):
            label = seq[i]
            if label == "O":
                continue
            prefix, _, type_ = label.partition("-")
            if type_ not in by_type:
                by_type[type_] = 0.0
                begins[type_] = 0.0
                order.append(type_)
            by_type[type_] += weight
            if prefix == "B":
                begins[type_] += weight
            present += weight
        if present <= need or not by_type:
            out.append("O")
            continue
        winner = max(order, key=lambda t: (by_type[t], -order.index(t)))
        prefix = "B" if begins[winner] * 2 >= by_type[winner] else "I"
        out.append(f"{prefix}-{winner}")
    return out


def ground_snippets(
    text: str, snippets: Sequence[tuple[str, str]], fuzzy: bool = True
) -> list[Span]:
    """Map ``(surface, type)`` pairs returned by a model back onto character offsets.

    This is the one place a real alignment problem remains.  A large language model returns *text*,
    not offsets, and it will normalise whitespace, quotation marks and diacritics on the way.  A
    literal ``str.find`` therefore drops spans that are perfectly correct, silently depressing that
    detector's recall and corrupting the ensemble comparison.

    Exact matching is tried first; ``fuzzy`` then retries against a Unicode-normalised,
    whitespace-collapsed view of the text and maps the hit back to original offsets.  Repeated
    surfaces are consumed left to right, so *n* occurrences yield *n* spans.
    """
    spans: list[Span] = []
    cursors: dict[str, int] = {}
    folded, back = _folded_index(text) if fuzzy else ("", [])

    for surface, type_ in snippets:
        key = f"{surface}\x1f{type_}"
        start = text.find(surface, cursors.get(key, 0))
        if start >= 0:
            end = start + len(surface)
        elif fuzzy:
            needle = _fold(surface)
            if not needle:
                continue
            pos = folded.find(needle, cursors.get(key + "\x1ff", 0))
            if pos < 0:
                continue
            cursors[key + "\x1ff"] = pos + len(needle)
            start, end = back[pos], back[pos + len(needle) - 1] + 1
        else:
            continue
        cursors[key] = end
        spans.append(Span(start, end, text[start:end], type_, source="llm"))
    return spans


def text_windows(text: str, size: int, overlap: int = 0) -> list[tuple[int, int]]:
    """Character windows over a document as ``(start, end)`` pairs.

    Every classical detector in axis D has a hard input limit — 512 word pieces for the fine-tuned
    de-ID models, roughly 384 for GLiNER v2.1 — while a TAB judgment runs to tens of thousands of
    characters.  Windowing is therefore not an optimisation but a correctness requirement: without
    it a model silently sees the first *n* tokens of a document and the rest of the text is scored
    as if the detector had found nothing there.

    ``overlap`` exists because a fixed cut lands inside an entity roughly as often as anywhere else,
    and an entity split across two windows is found by neither.  Overlapping windows see it whole in
    at least one of them, at the price of duplicate spans — which :func:`dedupe_spans` removes.

    Offsets are absolute in ``text``, so a span found in a window needs only ``start`` added to it.
    """
    if size <= 0:
        raise ValueError("window size must be positive")
    if not 0 <= overlap < size:
        raise ValueError(f"overlap must be in [0, {size}), got {overlap}")
    if not text:
        return []
    step = size - overlap
    out: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        out.append((start, min(start + size, len(text))))
        if start + size >= len(text):
            break
        start += step
    return out


def dedupe_spans(spans: Sequence[Span]) -> list[Span]:
    """Collapse spans that overlapping windows found twice, keeping the better-scored copy.

    Identity is ``(start, end, type)``: two windows that both saw the same entity produce the same
    offsets, because window offsets are absolute.  Anything genuinely different — a boundary
    disagreement between two *detectors* — is left alone; resolving that is the combination rule's
    job (:mod:`pseudonymkit.detectors.combinators`), not this function's.
    """
    best: dict[tuple[int, int, str], Span] = {}
    for span in spans:
        key = (span.start, span.end, span.type)
        current = best.get(key)
        if current is None or (span.score or 0.0) > (current.score or 0.0):
            best[key] = span
    return sorted(best.values(), key=lambda s: (s.start, -s.length, s.type))


def _fold(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).strip().casefold()


def _folded_index(text: str) -> tuple[str, list[int]]:
    """A folded view of ``text`` plus, for each folded character, its original offset."""
    out: list[str] = []
    back: list[int] = []
    prev_space = False
    for i, ch in enumerate(text):
        decomposed = unicodedata.normalize("NFKD", ch)
        kept = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
        if not kept:
            continue
        if kept.isspace():
            if prev_space:
                continue
            kept, prev_space = " ", True
        else:
            prev_space = False
        for c in kept:
            out.append(c)
            back.append(i)
    return "".join(out), back
