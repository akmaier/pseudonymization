"""Building conditions B and C from condition A, in one pass, as patches.

``experiment_plan.md`` §7 fixes three conditions: A is the corpus as it stands, B replaces each
detected identifier with a realistic locale-appropriate surrogate, C with a typed placeholder.  B and
C differ in **exactly one thing** — what string goes in — and everything upstream of that is shared:
which spans, the N2 normaliser, the scope key, the HMAC.

## Why one pass, and why that is a correctness argument

If B were built from ``union`` and C from ``vote(3)``, the difference between them would confound the
condition with detector coverage, and the study's independent variable would stop being the
independent variable.  :func:`construct` therefore takes a **list** of conditions and drives them all
from one span set, so the two cannot come apart.  It is also cheaper — the span walk, the splice and
the offset remapping are identical work — but that is the smaller reason.

## Why patches rather than corpora

A materialised Enron B is ~40 MB gzipped, and the cells multiply: 4 corpora × 2 conditions × 504
detector sets (§7 axis D, H5) × 6 combination rules.  Materialising even a fraction of that is tens
of gigabytes on a filesystem at 95 %.

A patch stores only what changed — the spans, their replacements and where they landed — plus a
provenance header.  The transformed text is a pure function of (condition-A document, patch) and
:func:`materialise` reconstructs it in memory, so nothing downstream needs the copy on disk.

## Post-hoc ensembling

Detection is the only step that costs model time, and it is cached per detector
(:mod:`pseudonymkit.detectors.cache`).  Everything here is set arithmetic and string splicing over
that cache, so any detector subset and any combination rule is re-derivable in seconds, with no
model calls.  :func:`detected_documents` is the seam: give it a pool of detector ids and a rule, and
it returns condition-A documents whose mentions are that ensemble's output.

Three things it refuses to do quietly:

* **A truncated LLM response is dropped, not used.**  Measured on the 1 % sweep, a truncated
  response is not a short one — it is a runaway: Magistral averages 53.8 spans on a normal CARDIO:DE
  letter and **279.0** on a truncated one, Mistral 68.5 against 352.8.  Counting those as detections
  would inflate recall and destroy precision at once.
* **A cached span set whose text has changed is dropped**, via the digest the cache records.
* **A detector with no record for a document is a hole, not a zero.**  Treating "not run" as "found
  nothing" silently converts a missing detector into a vote against every span.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace as _replace
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .conditions import SPECS, build as build_condition
from .detectors.base import DetectorOutput
from .detectors.cache import DetectorCache
from .detectors.combinators import COMBINATORS, Combinator
from .domain import Corpus, Document, Mention, Span
from .engine import OffsetMap, Pseudonymiser, replacements
from .taxonomy import Harmoniser, source_for
from .inventories import Inventory

__all__ = [
    "PatchEntry",
    "Patch",
    "PatchSet",
    "detected_documents",
    "construct",
    "materialise",
    "write_patchset",
    "read_patchset",
]


@dataclass(frozen=True, slots=True)
class PatchEntry:
    """One replacement: where it came from, what went in, and where that landed."""

    old_start: int
    old_end: int
    """Offsets into the **condition-A** text."""
    new_start: int
    new_end: int
    """Offsets into the materialised text."""
    replacement: str
    entity_key: str
    """The normalised key the technique was applied to.  Empty for a placeholder that carries no
    entity — but C keeps it populated anyway, because the leakage attacks need to know which entity
    each placeholder stood for even though the text no longer says."""
    entity_type: str
    type_src: str | None = None
    voters: tuple[str, ...] = ()
    """Which detectors produced the span.  Kept so per-detector attribution survives into analysis;
    it is a few short strings per span and compresses well."""


@dataclass(frozen=True, slots=True)
class Patch:
    """Everything that changed in one document."""

    doc_id: str
    entries: tuple[PatchEntry, ...]
    skipped: int = 0
    """Detected mentions dropped because they overlapped one already replaced.  A union ensemble
    produces overlaps by construction and their rate is a result, not noise (§8.1)."""


@dataclass(frozen=True)
class PatchSet:
    """One condition, over one corpus, under one detector set and one combination rule."""

    condition: str
    corpus: str
    provenance: Mapping[str, object] = field(default_factory=dict)
    patches: tuple[Patch, ...] = ()

    def __len__(self) -> int:
        return len(self.patches)

    @property
    def replacements(self) -> int:
        return sum(len(p.entries) for p in self.patches)

    def by_doc(self) -> dict[str, Patch]:
        return {p.doc_id: p for p in self.patches}


# --------------------------------------------------------------------------------------------
# the seam: cached detector output -> documents carrying an ensemble's spans


def detected_documents(
    documents: Sequence[Document],
    cache: DetectorCache,
    detectors: Sequence[str],
    rule: str | Combinator = "union",
    *,
    rule_kwargs: Mapping[str, object] | None = None,
    drop_truncated: bool = True,
    require_all: bool = False,
    report: dict | None = None,
) -> tuple[list[Document], dict]:
    """Attach one ensemble's spans to condition-A documents, as their mentions.

    ``detectors`` may name ``"gold"``, which is not read from the cache at all: the documents' own
    gold mentions are used, giving the perfect-detection ceiling through the identical code path
    (§7 lists gold spans as a level of axis D).

    ``require_all`` refuses a document that is missing any detector's record, rather than combining
    over a partial pool — an intersection rule over a pool that is silently short by one detector
    measures something else entirely.
    """
    combinator = (
        COMBINATORS.create(rule, **(dict(rule_kwargs or {})))
        if isinstance(rule, str)
        else rule
    )
    texts = {d.doc_id: d.text for d in documents}
    gold_wanted = "gold" in detectors
    model_detectors = [d for d in detectors if d != "gold"]

    pool: dict[str, dict[str, DetectorOutput]] = {}
    dropped_stale = dropped_truncated = 0
    harmonisation: dict[str, dict[str, object]] = {}
    for name in model_detectors:
        records = _load_usable(cache, name, texts, drop_truncated)
        # **Harmonise here, not at detection time.**  The classical detectors route their labels as
        # they produce them; the gateway pool does not, and writes whatever the model said — which
        # for a zero-shot prompt is an open vocabulary.  On CARDIO:DE the eight models between them
        # emitted 160 distinct labels: ID, PROFESSION and PHONE, which the taxonomy routes, but also
        # LAB_VALUE, BLOOD_PRESSURE, DIAGNOSIS and TRANSTHORAKTAL ECHOKARDIOGRAPHIE, which it cannot.
        # Leaving them raw reached the renderer as unknown types and stopped the build.
        #
        # Doing it on read rather than on write keeps the model's own string in the cache, where it
        # is part of the experimental record, and :meth:`Harmoniser.span` takes the raw label from
        # ``type_src or type`` so applying it to an already-harmonised span is a no-op.
        harmoniser = Harmoniser(source_for(name, cache.corpus))
        pool[name] = {
            doc_id: _replace(output, spans=harmoniser.spans(output.spans))
            for doc_id, output in records.output.items()
        }
        # §10 requires the unmapped count to be reported; a caller that discards it drops a result.
        harmonisation[name] = {
            "spans": harmoniser.seen,
            "unmapped_spans": harmoniser.unmapped_spans,
            "unmapped_labels": dict(harmoniser.unmapped),
        }
        dropped_stale += records.stale
        dropped_truncated += records.truncated

    out: list[Document] = []
    incomplete = 0
    for document in documents:
        outputs: list[DetectorOutput] = []
        missing = False
        for name in model_detectors:
            record = pool[name].get(document.doc_id)
            if record is None:
                missing = True          # a hole, never a zero
                continue
            outputs.append(record)
        if gold_wanted:
            outputs.append(
                DetectorOutput(
                    doc_id=document.doc_id,
                    detector="gold",
                    spans=tuple(m.span for m in document.mentions),
                )
            )
        if missing:
            incomplete += 1
            if require_all:
                continue
        if not outputs:
            continue
        spans = combinator.combine(outputs)
        voters = _voters(outputs)
        out.append(document.with_mentions(_mentions(document.doc_id, spans, voters)))

    summary = {
        "detectors": list(detectors),
        "documents_in": len(documents),
        "documents_out": len(out),
        "documents_missing_a_detector": incomplete,
        "records_dropped_stale_text": dropped_stale,
        "records_dropped_truncated": dropped_truncated,
        "harmonisation": harmonisation,
        **getattr(combinator, "settings", {"rule": getattr(combinator, "name", str(rule))}),
    }
    if report is not None:
        report.update(summary)
    return out, summary


@dataclass(frozen=True, slots=True)
class _Usable:
    output: dict[str, DetectorOutput]
    stale: int
    truncated: int


def _load_usable(
    cache: DetectorCache, detector: str, texts: Mapping[str, str], drop_truncated: bool
) -> _Usable:
    """Cached output for one detector, minus records that must not be believed."""
    path = cache.path(detector)
    if not path.exists():
        return _Usable({}, 0, 0)
    from .detectors.cache import text_digest

    out: dict[str, DetectorOutput] = {}
    stale = truncated = 0
    for record in cache._read(path):
        doc_id = record["doc_id"]
        if record.get("error") is not None:
            continue
        current = texts.get(doc_id)
        if current is not None and record.get("text_sha256") != text_digest(current):
            out.pop(doc_id, None)
            stale += 1
            continue
        if drop_truncated and record.get("truncated"):
            out.pop(doc_id, None)
            truncated += 1
            continue
        out[doc_id] = DetectorOutput(
            doc_id=doc_id,
            detector=detector,
            spans=tuple(Span(**s) for s in record["spans"]),
        )
    return _Usable(out, stale, truncated)


def _voters(outputs: Sequence[DetectorOutput]) -> dict[tuple[int, int], tuple[str, ...]]:
    """Which detectors covered each character range, for attribution after the fact."""
    seen: dict[tuple[int, int], set[str]] = {}
    for output in outputs:
        for span in output.spans:
            seen.setdefault((span.start, span.end), set()).add(output.detector)
    return {k: tuple(sorted(v)) for k, v in seen.items()}


def _mentions(
    doc_id: str, spans: Sequence[Span], voters: Mapping[tuple[int, int], tuple[str, ...]]
) -> tuple[Mention, ...]:
    return tuple(
        Mention(
            doc_id=doc_id,
            mention_id=f"{doc_id}:det:{index}",
            span=span,
            attributes={"voters": ",".join(voters.get((span.start, span.end), ()))},
        )
        for index, span in enumerate(spans)
    )


# --------------------------------------------------------------------------------------------
# the one pass that produces every condition


def construct(
    documents: Sequence[Document],
    corpus: str,
    conditions: Sequence[str] = ("B", "C"),
    *,
    inventory: Inventory | None = None,
    key: bytes | None = None,
    key_id: str = "unset",
    provenance: Mapping[str, object] | None = None,
) -> dict[str, PatchSet]:
    """Produce one :class:`PatchSet` per condition, from **one** span set.

    ``documents`` must already carry the ensemble's spans as their mentions — see
    :func:`detected_documents`.  Every condition sees the same document objects, so the span set
    cannot differ between them; that is the invariant this function exists to hold.

    Each condition gets its own :class:`~pseudonymkit.engine.Pseudonymiser`, because the mapping is
    per condition: B's entity → surrogate table and C's entity → placeholder table are different
    objects and must not be shared.
    """
    unknown = [c for c in conditions if c.upper() not in SPECS]
    if unknown:
        raise KeyError(f"unknown condition(s): {unknown}; available: {sorted(SPECS)}")
    if any(c.upper() == "A" for c in conditions):
        raise ValueError("condition A is the input, not an output; it is not constructed here")

    engines = {
        c.upper(): build_condition(c, inventory=inventory, key=key) for c in conditions
    }
    out: dict[str, PatchSet] = {
        c: PatchSet(condition=c, corpus=corpus, patches=()) for c in engines
    }
    collected: dict[str, list[Patch]] = {c: [] for c in engines}

    for document in documents:
        for condition, engine in engines.items():
            result = engine.pseudonymise(document)
            entries = tuple(
                PatchEntry(
                    old_start=r.old_start,
                    old_end=r.old_end,
                    new_start=r.new_start,
                    new_end=r.new_end,
                    replacement=r.assignment.surface,
                    entity_key=r.assignment.entity_key,
                    entity_type=r.assignment.entity_type,
                    type_src=r.mention.span.type_src,
                    voters=tuple(
                        v for v in (r.mention.attributes.get("voters") or "").split(",") if v
                    ),
                )
                for r in replacements(result)
            )
            collected[condition].append(
                Patch(doc_id=document.doc_id, entries=entries, skipped=len(result.skipped))
            )

    base = dict(provenance or {})
    for condition, engine in engines.items():
        spec = SPECS[condition]
        out[condition] = PatchSet(
            condition=condition,
            corpus=corpus,
            provenance={**base, **spec.describe(key_id=key_id), "documents": len(documents)},
            patches=tuple(collected[condition]),
        )
    return out


# --------------------------------------------------------------------------------------------
# reconstruction


def materialise(document: Document, patch: Patch) -> Document:
    """Rebuild the transformed document from condition A and a patch.

    The annotation layers move with the text — CARDIO:DE's medication and section spans, every
    corpus's gold mentions — through :class:`~pseudonymkit.engine.OffsetMap`'s rule for a gold span
    that overlaps a replacement of a different length.
    """
    pieces: list[str] = []
    cursor = 0
    for entry in patch.entries:
        pieces.append(document.text[cursor : entry.old_start])
        pieces.append(entry.replacement)
        cursor = entry.old_end
    pieces.append(document.text[cursor:])
    text = "".join(pieces)

    offsets = OffsetMap(
        tuple((e.old_start, e.old_end, e.new_start, e.new_end) for e in patch.entries)
    )
    mentions = tuple(
        _replace(
            mention,
            span=_replace(
                mention.span,
                start=offsets.start(mention.span.start),
                end=offsets.end(mention.span.end),
                text=text[
                    offsets.start(mention.span.start) : offsets.end(mention.span.end)
                ],
            ),
        )
        for mention in document.mentions
    )
    task = _remap_task(document.task, offsets, text)
    return _replace(document, text=text, mentions=mentions, task=task)


def _remap_task(task: Mapping[str, object], offsets: OffsetMap, text: str) -> dict:
    """Carry span-bearing task layers onto the new offsets, leaving everything else alone."""
    out = dict(task)
    for name, value in task.items():
        if not isinstance(value, (list, tuple)) or not value:
            continue
        if not all(hasattr(v, "start") and hasattr(v, "end") for v in value):
            continue
        moved = []
        for span in value:
            start, end = offsets.span(span.start, span.end)
            fields = {"start": start, "end": end}
            if hasattr(span, "text"):
                fields["text"] = text[start:end]
            moved.append(_replace(span, **fields))
        out[name] = tuple(moved)
    return out


def materialise_corpus(
    documents: Iterable[Document], patchset: PatchSet, name: str | None = None
) -> Corpus:
    """Apply a whole patch set. Documents with no patch pass through unchanged."""
    patches = patchset.by_doc()
    out = []
    for document in documents:
        patch = patches.get(document.doc_id)
        out.append(materialise(document, patch) if patch is not None else document)
    return Corpus(name or f"{patchset.corpus}[{patchset.condition}]", tuple(out))


# --------------------------------------------------------------------------------------------
# storage


def write_patchset(patchset: PatchSet, path: Path | str) -> int:
    """Header line, then one patch per line.  Returns the number of patches written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "__patchset__": {
                "condition": patchset.condition,
                "corpus": patchset.corpus,
                "provenance": dict(patchset.provenance),
            }
        }, ensure_ascii=False) + "\n")
        for patch in patchset.patches:
            handle.write(json.dumps({
                "doc_id": patch.doc_id,
                "skipped": patch.skipped,
                "entries": [
                    [e.old_start, e.old_end, e.new_start, e.new_end, e.replacement,
                     e.entity_key, e.entity_type, e.type_src, list(e.voters)]
                    for e in patch.entries
                ],
            }, ensure_ascii=False) + "\n")
    return len(patchset.patches)


def read_patchset(path: Path | str) -> PatchSet:
    """Read a patch set back, header included — a patch without its provenance is unciteable."""
    path = Path(path)
    header: dict = {}
    patches: list[Patch] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if "__patchset__" in record:
                header = record["__patchset__"]
                continue
            patches.append(Patch(
                doc_id=record["doc_id"],
                skipped=record.get("skipped", 0),
                entries=tuple(
                    PatchEntry(
                        old_start=e[0], old_end=e[1], new_start=e[2], new_end=e[3],
                        replacement=e[4], entity_key=e[5], entity_type=e[6],
                        type_src=e[7], voters=tuple(e[8]),
                    )
                    for e in record["entries"]
                ),
            ))
    return PatchSet(
        condition=header.get("condition", "?"),
        corpus=header.get("corpus", "?"),
        provenance=header.get("provenance", {}),
        patches=tuple(patches),
    )
