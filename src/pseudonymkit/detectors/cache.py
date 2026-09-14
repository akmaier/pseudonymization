"""A durable, resumable store of detector output.

LLM detection is the only slow step in this study: thousands of gateway calls, minutes per hundred
documents, and a job that may be interrupted by a wall clock or a cold model.  Ensembling, by
contrast, is set arithmetic over spans and takes seconds.

Tying the two together would be a serious mistake — every new combination rule, every new subset of
the detector pool, would mean paying for the model calls again.  So detection **writes once** into
this cache and every ensemble afterwards is a **post-hoc read**.  The consequence worth stating: the
hybrid-versus-LLMs-only sweep, which is hundreds of subset/rule combinations, costs no model calls at
all once the pool has been run.

One JSONL file per (corpus, detector).  Append-only, one record per document, so an interrupted run
resumes by skipping what is already present rather than starting over.

## Every record carries the hash of the text it was computed against

Without it, a cache is silently wrong the moment the corpus underneath it changes, and nothing
anywhere notices.  That is not hypothetical: two runs spent **four days** producing spans over
CARDIO:DE's ``<[Pseudo] …>`` marker strings after the condition-A fill had removed them, and over the
66,432-document Enron sample after the empty-body exclusion cut it to 58,636.  The output looked
perfectly well formed.

So :meth:`append` records ``text_sha256`` and :meth:`done` and :meth:`load` will not hand back a
record whose hash does not match the document in front of them — a changed text now *invalidates*
its records rather than quietly mismatching them.  Records written before this existed carry no hash
and are treated as unverifiable: usable only when the caller passes no text to check against, which
is why :func:`text_digest` is cheap enough to always pass.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Iterator

from ..domain import Span
from .base import DetectorOutput

__all__ = ["DetectorCache", "text_digest"]


def text_digest(text: str) -> str:
    """The identity of the text a detector actually saw.  Sixteen hex characters is ample here —
    this guards against a corpus being rebuilt, not against an adversary."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class DetectorCache:
    """Read/write span records for one corpus, keyed by detector and document."""

    def __init__(self, root: Path | str, corpus: str) -> None:
        self.root = Path(root) / corpus
        self.corpus = corpus
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, detector: str) -> Path:
        safe = detector.replace("/", "__")
        return self.root / f"{safe}.jsonl"

    def done(self, detector: str, texts: dict[str, str] | None = None) -> set[str]:
        """Document ids already recorded — what a resumed run may skip.

        Records that captured a failure are **not** counted as done, so a transient gateway error is
        retried on the next run instead of being silently frozen into the results.

        When ``texts`` is given (``doc_id -> text``), a record only counts as done if its
        ``text_sha256`` matches the text now in hand.  A document whose text has changed is therefore
        **re-detected**, not skipped, which is the whole point of storing the hash.
        """
        path = self.path(detector)
        if not path.exists():
            return set()
        seen: set[str] = set()
        for record in self._read(path):
            if record.get("error") is not None:
                continue
            if texts is not None:
                current = texts.get(record["doc_id"])
                if current is not None and record.get("text_sha256") != text_digest(current):
                    seen.discard(record["doc_id"])
                    continue
            seen.add(record["doc_id"])
        return seen

    def append(
        self,
        detector: str,
        doc_id: str,
        spans: Iterable[Span],
        *,
        model: str | None = None,
        prompt_version: str | None = None,
        error: str | None = None,
        elapsed: float | None = None,
        meta: dict | None = None,
        text: str | None = None,
    ) -> None:
        """Record one document's result. Flushed immediately: an interrupted job keeps its work.

        ``text`` is the document the detector actually read; its digest goes into the record so a
        later run can tell whether the corpus has changed underneath it.
        """
        record = {
            "doc_id": doc_id,
            "detector": detector,
            "model": model,
            "prompt_version": prompt_version,
            "text_sha256": text_digest(text) if text is not None else None,
            "spans": [asdict(s) for s in spans],
            "error": error,
            "elapsed": elapsed,
            "ts": time.time(),
            **(meta or {}),
        }
        with self.path(detector).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def digests(self, detector: str) -> dict[str, str]:
        """``doc_id -> text_sha256`` for every successful record.  The resume index for a **streamed**
        run.

        :meth:`done` answers the same question but needs the corpus' texts in hand, which means
        holding them.  On Enron that is 58,636 documents of text pinned for the life of the process,
        per model thread, on a head node with 7 GB shared between users.  This returns sixteen hex
        characters per document instead — a few megabytes for the largest corpus — so a runner can
        decide what to skip while reading the corpus one document at a time.

        Later records win, and a record carrying an error removes the document again: a transient
        gateway failure must not freeze an earlier success into place, nor count as done.
        """
        out: dict[str, str] = {}
        path = self.path(detector)
        if not path.exists():
            return out
        for record in self._read(path):
            doc_id = record.get("doc_id")
            if doc_id is None:
                continue
            if record.get("error") is not None:
                out.pop(doc_id, None)
                continue
            digest = record.get("text_sha256")
            if digest is None:
                out.pop(doc_id, None)   # pre-hash record: unverifiable, so not resumable
                continue
            out[doc_id] = digest
        return out

    def load(self, detector: str, texts: dict[str, str] | None = None) -> dict[str, DetectorOutput]:
        """All successful output for one detector, latest record per document wins.

        With ``texts``, records whose digest does not match are dropped rather than returned: an
        ensemble must never be built half from spans over the current text and half from spans over
        a text that no longer exists.
        """
        out: dict[str, DetectorOutput] = {}
        path = self.path(detector)
        if not path.exists():
            return out
        for record in self._read(path):
            if record.get("error") is not None:
                continue
            if texts is not None:
                current = texts.get(record["doc_id"])
                if current is not None and record.get("text_sha256") != text_digest(current):
                    out.pop(record["doc_id"], None)
                    continue
            out[record["doc_id"]] = DetectorOutput(
                doc_id=record["doc_id"],
                detector=detector,
                spans=tuple(Span(**s) for s in record["spans"]),
            )
        return out

    def load_pool(self, detectors: Iterable[str]) -> dict[str, list[DetectorOutput]]:
        """doc_id -> every detector's output for it, for documents **all** of them covered.

        Ensembling on partial coverage would silently change the denominator between combinations,
        so a document missing from any pool member is excluded and the caller can count the loss.
        """
        detectors = list(detectors)
        per_detector = {d: self.load(d) for d in detectors}
        shared = set.intersection(*(set(v) for v in per_detector.values())) if detectors else set()
        return {doc: [per_detector[d][doc] for d in detectors] for doc in sorted(shared)}

    def stats(self) -> dict[str, dict[str, int]]:
        """Per detector: documents recorded, failures, total spans. For monitoring a long run."""
        report: dict[str, dict[str, int]] = {}
        for path in sorted(self.root.glob("*.jsonl")):
            ok = failed = spans = 0
            for record in self._read(path):
                if record.get("error") is not None:
                    failed += 1
                else:
                    ok += 1
                    spans += len(record.get("spans", ()))
            report[path.stem.replace("__", "/")] = {"documents": ok, "errors": failed, "spans": spans}
        return report

    @staticmethod
    def _read(path: Path) -> Iterator[dict]:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue          # a torn final line from a killed job; skip it, keep the rest
