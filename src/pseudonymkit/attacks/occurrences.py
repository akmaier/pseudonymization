"""Occurrence-level labels for the name-like spans of a release (plan §10 item 3, §8.3).

The attacker reads name-like spans out of the released text (:data:`~.frequency._NAME_LIKE`) and has
to tell a **surrogate** — text the defender wrote — from a **survivor** — a real name the defender's
detector missed. Every analysis of that decision needs to know, for each span, which of the two it
is. ``frequency._truth_tables`` answers by surface: it maps each string to what stands behind it,
and a string that is both a surrogate and a real name is called a surrogate. That silently
relabels a survivor whose name collides with some other entity's surrogate, and collisions are
10.1 % on CARDIO:DE PERSON (plan §7.8, §10).

This module labels by **position**. A span inside a replacement that changed the text is a
surrogate; a span over a gold mention that no such replacement covers is a survivor; anything else
is ``other``. The same string can therefore be a surrogate at one position and a survivor at the
next, which is what the release actually contains.

Two rules, both stated because they decide labels:

* **A replacement that left the text unchanged is not a surrogate.** Condition B renders
  ``DATETIME``, ``QUANTITY`` and ``MISC`` verbatim (:func:`~pseudonymkit.construction.changed_text`),
  so a person detected as ``MISC`` is still in the release character for character. It is labelled
  by the gold beneath it, exactly as if nothing had been replaced.
* **A name-like span that straddles a replacement boundary is split there.** ``_NAME_LIKE`` matches
  runs of up to three capitalised tokens, so a surrogate followed by a surviving surname reads as
  one run; each piece is labelled for what it is. A run that joins a survivor to an ordinary
  capitalised word ("Then Weber") is *not* split: it is one candidate to the attacker, and it is a
  survivor because a real name is in it.

Evaluator-side only. The labels are the scoring key and never part of what an attacker sees.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from ..domain import Document
from ..engine import PseudonymisedCorpus, PseudonymisedDocument, replacements
from .frequency import _NAME_LIKE

__all__ = ["LABELS", "Occurrence", "label_document", "label_occurrences"]

LABELS = ("surrogate", "survivor", "other")


@dataclass(frozen=True, slots=True)
class Occurrence:
    """One name-like piece of released text, and what stands behind it."""

    doc_id: str
    start: int
    """Offsets in the **released** text."""
    end: int
    old_start: int
    """Offsets in the condition-A text: the replaced span for a surrogate, the mapped span
    otherwise. This is where a phase-1 attacker's condition-A detector output is looked up."""
    old_end: int
    surface: str
    label: str
    entity: str | None
    """The gold entity behind the span: the chain of the replaced mention for a surrogate (``None``
    for a replacement over no gold mention, i.e. a false positive), the gold mention's entity for a
    survivor, ``None`` for ``other``."""
    replaced_type: str | None = None
    """For a surrogate, the type the defender replaced it as."""


def _gold_spans(gold: Document, entity_type: str) -> list[tuple[int, int, str | None]]:
    return sorted(
        (m.span.start, m.span.end, m.gold_entity_id)
        for m in gold.mentions
        if m.type == entity_type
    )


def _best_gold(start: int, end: int, gold: Sequence[tuple[int, int, str | None]]):
    """The gold mention overlapping ``[start, end)`` most, or ``None``."""
    best, best_overlap = None, 0
    for g_start, g_end, entity in gold:
        if g_start >= end:
            break
        overlap = min(end, g_end) - max(start, g_start)
        if overlap > best_overlap:
            best, best_overlap = (g_start, g_end, entity), overlap
    return best


def label_document(
    pdoc: PseudonymisedDocument, gold: Document, entity_type: str = "PERSON"
) -> list[Occurrence]:
    """Label every name-like span of one released document.

    ``gold`` is the condition-A document with its gold mentions; ``pdoc`` is that document's
    release. The two must address the same condition-A text.
    """
    original = gold.text
    if pdoc.document.doc_id != gold.doc_id:
        raise ValueError(f"release {pdoc.document.doc_id!r} is not document {gold.doc_id!r}")
    golds = _gold_spans(gold, entity_type)

    # The released text as alternating segments: a replacement that changed the text is opaque;
    # everything else (untouched text, and a replacement that rendered its source verbatim) maps
    # back to condition-A offsets by a constant shift.
    segments: list[tuple[int, int, int, object]] = []    # (new_start, new_end, shift, replacement)
    cursor_new = cursor_old = 0
    for r in replacements(pdoc):
        if r.new_start > cursor_new:
            segments.append((cursor_new, r.new_start, cursor_old - cursor_new, None))
        effective = r.assignment.surface != original[r.old_start:r.old_end]
        if effective:
            segments.append((r.new_start, r.new_end, 0, r))
        elif r.new_end > r.new_start:
            segments.append((r.new_start, r.new_end, r.old_start - r.new_start, None))
        cursor_new, cursor_old = r.new_end, r.old_end
    if cursor_new < len(pdoc.text):
        segments.append((cursor_new, len(pdoc.text), cursor_old - cursor_new, None))

    out: list[Occurrence] = []
    text = pdoc.text
    for match in _NAME_LIKE.finditer(text):
        m_start, m_end = match.start(), match.end()
        for s_start, s_end, shift, r in segments:
            if s_end <= m_start:
                continue
            if s_start >= m_end:
                break
            start, end = max(m_start, s_start), min(m_end, s_end)
            piece = text[start:end].strip()
            if not piece:
                continue
            # Trim the piece to its non-space extent so offsets name the characters themselves.
            lead = len(text[start:end]) - len(text[start:end].lstrip())
            start, end = start + lead, start + lead + len(piece)
            if r is not None:
                out.append(Occurrence(
                    doc_id=gold.doc_id, start=start, end=end,
                    old_start=r.old_start, old_end=r.old_end, surface=piece,
                    label="surrogate", entity=r.mention.gold_entity_id,
                    replaced_type=r.mention.type,
                ))
                continue
            old_start, old_end = start + shift, end + shift
            hit = _best_gold(old_start, old_end, golds)
            out.append(Occurrence(
                doc_id=gold.doc_id, start=start, end=end, old_start=old_start, old_end=old_end,
                surface=piece, label="survivor" if hit else "other",
                entity=hit[2] if hit else None,
            ))
    return out


def label_occurrences(
    result: PseudonymisedCorpus,
    gold_documents: Iterable[Document] | Mapping[str, Document],
    entity_type: str = "PERSON",
) -> list[Occurrence]:
    """:func:`label_document` over a whole release, in release order."""
    if not isinstance(gold_documents, Mapping):
        gold_documents = {d.doc_id: d for d in gold_documents}
    out: list[Occurrence] = []
    for pdoc in result.documents:
        out.extend(label_document(pdoc, gold_documents[pdoc.document.doc_id], entity_type))
    return out
