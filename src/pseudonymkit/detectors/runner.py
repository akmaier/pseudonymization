"""Running one detector over a corpus and writing through the cache.

Every detector in axis D — the four classical ones and both LLM backends — has the same operational
requirements, and they were previously re-implemented in each experiment script:

* **Resume.** Detection is the only step that costs model time (§7).  A job killed by the 24 h wall
  clock must restart by skipping what is already recorded, not by starting over.
* **Record failures rather than swallowing them.**  A document that errored is written with its
  error and is *not* counted as done, so the next run retries it instead of freezing an empty span
  list into the results.  A silently empty result is the worst failure a detector pool can have: the
  ensemble reads it as "found nothing" rather than "never answered" (§12.2).
* **Stamp the record.**  Model id and prompt version go into every record, because which model was
  live is part of the experimental record (§7).

**Staleness is handled by the cache, not here.**  This docstring used to say the opposite — that a
record carried no text version and had to be deleted by hand when a corpus was rebuilt.  Every record
now carries ``text_sha256``, and :meth:`DetectorCache.done` re-detects a document whose text has
changed rather than skipping it, so passing ``texts`` (which this function always does) is what keeps
an ensemble from mixing spans over two different versions of the same document.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol, Sequence, runtime_checkable

from ..domain import Document
from .base import Detector, DetectorOutput
from .cache import DetectorCache

__all__ = ["RunReport", "BatchDetector", "run_detector"]


@runtime_checkable
class BatchDetector(Protocol):
    """A detector that is materially faster when handed many documents at once.

    vLLM's continuous batching and a transformers pipeline both are; Presidio is not.  The runner
    uses this path when it exists and falls back to :meth:`Detector.detect` otherwise, so a detector
    never has to implement batching it cannot exploit.
    """

    def detect_many(self, documents: Iterable[Document]) -> Sequence[DetectorOutput]: ...


@dataclass(frozen=True, slots=True)
class RunReport:
    """What one detector did on one corpus — printed by the job and kept with the results."""

    detector: str
    corpus: str
    documents: int
    """Documents in the requested set."""
    skipped: int
    """Already in the cache from an earlier run."""
    written: int
    failed: int
    spans: int
    elapsed: float

    def __str__(self) -> str:
        return (
            f"{self.corpus} / {self.detector}: {self.written} written, {self.skipped} cached, "
            f"{self.failed} failed, {self.spans} spans in {self.elapsed:.1f}s"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "detector": self.detector, "corpus": self.corpus, "documents": self.documents,
            "skipped": self.skipped, "written": self.written, "failed": self.failed,
            "spans": self.spans, "elapsed": self.elapsed,
        }


def run_detector(
    detector: Detector,
    documents: Iterable[Document],
    cache: DetectorCache,
    *,
    model: str | None = None,
    prompt_version: str | None = None,
    batch_size: int | None = None,
    resume: bool = True,
    retries: int = 2,
    retry_wait: float = 2.0,
    progress: Callable[[str], None] | None = None,
) -> RunReport:
    """Detect over ``documents``, appending each result to ``cache``.

    ``batch_size`` engages :meth:`BatchDetector.detect_many` when the detector offers it.  A batch
    that raises records the error against **every** document in it and moves on: one document with
    pathological text must not take a whole corpus down with it, and the failed ones are retried on
    the next run because a record carrying an error does not count as done.

    ``retries`` is attempted *in place* first, because the failures actually seen here were
    transient GPU faults rather than bad documents — see :func:`attempt`.
    """
    docs = list(documents)
    started = time.time()
    # From ``docs``, not ``documents``: the latter is an Iterable and ``list()`` has consumed it.
    texts = {d.doc_id: d.text for d in docs}
    done = cache.done(detector.name, texts=texts) if resume else set()
    todo = [d for d in docs if d.doc_id not in done]
    if progress:
        progress(f"{cache.corpus} / {detector.name}: {len(done)} cached, {len(todo)} to do")

    written = failed = spans = 0

    def record(doc_id: str, output: DetectorOutput | None, error: str | None, elapsed: float) -> None:
        nonlocal written, failed, spans
        cache.append(
            detector.name,
            doc_id,
            output.spans if output is not None else (),
            model=model or getattr(detector, "model", None) or detector.name,
            prompt_version=prompt_version,
            error=error,
            elapsed=elapsed,
            meta={"family": detector.family},
            text=texts.get(doc_id),
        )
        if error is None:
            written += 1
            spans += len(output.spans) if output is not None else 0
        else:
            failed += 1

    def attempt(call):
        """Run ``call``, retrying a transient failure before recording one.

        Most GPU failures here are not about the document.  Both privacy-tagger runs that failed on
        this cluster died on ``NVML_SUCCESS == DriverAPI::get()->nvmlInit_v2_() INTERNAL ASSERT
        FAILED`` inside torch's caching allocator, in bursts on consecutive documents, on a cluster
        whose NVML is mismatched on every node.  A bare re-run recovered 8 of Enron's 24 failures and
        lost 16 new ones to the same assertion, which is the signature of something intermittent
        rather than of text the detector cannot handle.

        Retrying in place is worth more than retrying the job: the failed documents are otherwise
        scattered through a 58,636-document pass that has to be scheduled, reloaded and streamed
        again to reach them.  The error string records how many attempts were made, so a record that
        does end up as a failure says it was not a single unlucky call.
        """
        last = None
        for index in range(retries + 1):
            try:
                return call(), None
            except Exception as exc:                                   # noqa: BLE001 - recorded
                last = exc
                if index < retries:
                    time.sleep(retry_wait * (index + 1))
        return None, f"{type(last).__name__}: {last} [after {retries + 1} attempts]"

    batched = batch_size and isinstance(detector, BatchDetector)
    step = batch_size or 1
    for offset in range(0, len(todo), step):
        chunk = todo[offset : offset + step]
        t0 = time.time()
        if batched:
            outputs, error = attempt(
                lambda: detector.detect_many(chunk))  # type: ignore[attr-defined]
            elapsed = (time.time() - t0) / max(len(chunk), 1)
            if error is not None:
                for document in chunk:
                    record(document.doc_id, None, error, elapsed)
            else:
                for document, output in zip(chunk, outputs):
                    record(document.doc_id, output, None, elapsed)
        else:
            for document in chunk:
                t0 = time.time()
                output, error = attempt(lambda doc=document: detector.detect(doc))
                record(document.doc_id, output if error is None else None, error,
                       time.time() - t0)
        if progress and (offset // step) % 25 == 24:
            progress(f"  {cache.corpus} / {detector.name}: {written + failed}/{len(todo)}")

    report = RunReport(
        detector=detector.name, corpus=cache.corpus, documents=len(docs), skipped=len(done),
        written=written, failed=failed, spans=spans, elapsed=time.time() - started,
    )
    if progress:
        progress(str(report))
    return report
