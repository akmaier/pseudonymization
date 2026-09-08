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
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Iterator

from ..domain import Span
from .base import DetectorOutput

__all__ = ["DetectorCache"]


class DetectorCache:
    """Read/write span records for one corpus, keyed by detector and document."""

    def __init__(self, root: Path | str, corpus: str) -> None:
        self.root = Path(root) / corpus
        self.corpus = corpus
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, detector: str) -> Path:
        safe = detector.replace("/", "__")
        return self.root / f"{safe}.jsonl"

    def done(self, detector: str) -> set[str]:
        """Document ids already recorded — what a resumed run may skip.

        Records that captured a failure are **not** counted as done, so a transient gateway error is
        retried on the next run instead of being silently frozen into the results.
        """
        path = self.path(detector)
        if not path.exists():
            return set()
        seen: set[str] = set()
        for record in self._read(path):
            if record.get("error") is None:
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
    ) -> None:
        """Record one document's result. Flushed immediately: an interrupted job keeps its work."""
        record = {
            "doc_id": doc_id,
            "detector": detector,
            "model": model,
            "prompt_version": prompt_version,
            "spans": [asdict(s) for s in spans],
            "error": error,
            "elapsed": elapsed,
            "ts": time.time(),
        }
        with self.path(detector).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def load(self, detector: str) -> dict[str, DetectorOutput]:
        """All successful output for one detector, latest record per document wins."""
        out: dict[str, DetectorOutput] = {}
        path = self.path(detector)
        if not path.exists():
            return out
        for record in self._read(path):
            if record.get("error") is not None:
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
