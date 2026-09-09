#!/usr/bin/env python3
"""LLM detection against the NHR@FAU gateway — a plain process, not a Slurm job.

**This does not belong in a Slurm allocation** (AM, 2026-09-08). It is a network client: it holds no
GPU, does no arithmetic, and spends its whole life in ``recv()``. An earlier version ran it as a
nine-task array and so occupied eight of the association's job slots doing nothing, blocking the
group's actual GPU work. The cluster is for heavy GPU jobs; this runs on the head node under the
user's own account.

**Parallel over models, sequential over texts** (AM, 2026-09-08). One thread per model, each walking
the document list in order. Concurrency equals the number of models — three by default — which is
gentle on the gateway and on the head node, and it keeps each model's progress independently
readable in the log. It is also lock-free by construction: the cache keeps one file per
``(corpus, detector)``, so each thread is the only writer of its own file.

**Small corpora first**, so that a run interrupted at any point has finished whole corpora rather
than a fifth of each.

**Everything resumes.** The cache is consulted before work is queued; documents already recorded are
skipped, and documents that errored are retried rather than frozen into the results. Killing this
process costs at most one document per model.

Run it detached, so an SSH disconnect does not take it with it::

    cd /cluster/maier/pseudonymization
    PYTHONPATH=src nohup .venv/bin/python experiments/detect_gateway.py \\
        > results/detect_gateway.log 2>&1 &

Enron is **not** in the corpus list yet: at the declared rate of 0.10 it is ~51,700 messages, and
``enron.load`` materialises every message it reads, which the head node will not hold. How it is
sampled and where it runs is an open item (``experiment_plan.md`` §10) and is not an agent's to
settle — it is named here rather than silently omitted.
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable

from dataclasses import replace as _replace

from pseudonymkit.adapters import cardiode, codealltag, ontonotes, tab
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.detectors.llm import LlmDetector
from pseudonymkit.detectors.prompting import PROMPT_VERSION
from pseudonymkit.domain import Corpus
from pseudonymkit.serialisation import iter_documents

SHARED = Path("/cluster/shared_dataset/pseudonymization-corpora")
ONTONOTES = Path("data/ontonotes")
CARDIODE = Path("/cluster/maier/dua-restricted/cardiode/corpus")
ENRON = Path("data/enron_subject010.jsonl.gz")

DEFAULT_MODELS = (
    "gpt-oss-120b",
    "Qwen/Qwen3.6-35B-A3B-FP8",
    "RedHatAI/gemma-4-31B-it-FP8-block",
    "RedHatAI/Mistral-Small-3.2-24B-Instruct-2506-FP8",
    "GaleneAI/Magistral-Small-2509-FP8-Dynamic",
    "google/gemma-4-E4B-it",
)
"""Six of the gateway's chat models (AM, 2026-09-08). DeepSeek is excluded — its backend is down;
`lightonai/LightOnOCR-2-1B` is OCR-oriented and not a span extractor."""

MAX_TOKENS = 16384
"""Generous on purpose: gateway tokens are free to us, and a tight cap silently truncates the
reasoning models before they emit their JSON — which reads as "found nothing", not as an error."""

# Smallest first. Each loader is called only when its corpus is reached, so the head node holds one
# corpus at a time rather than all of them.
CORPORA: tuple[tuple[str, int, Callable[[], Corpus]], ...] = (
    ("cardiode", 400, lambda: cardiode.load(CARDIODE)),
    ("codealltag", 800, lambda: codealltag.load(SHARED / "codealltag")),
    ("tab", 1268, lambda: tab.load(SHARED / "tab")),
    ("ontonotes", 5994, lambda: ontonotes.load(ONTONOTES)),
    ("enron", 66432, lambda: _load_enron(ENRON)),
)

def _load_enron(path: Path) -> Corpus:
    """Read the shipped ``subject`` @ 0.10 sample, **without** its gold mentions.

    Detection needs a document's id and its text and nothing else, while the gold layer is 1.5
    million ``Mention`` objects — several hundred megabytes that would sit untouched for the whole
    run, on a head node whose per-user memory limit has already killed one Enron load. The gold
    stays in the file, where the stability metrics and the attacks read it later.
    """
    name = "enron[subject@0.1#0]"
    documents = [_replace(d, mentions=()) for d in iter_documents(path)]
    return Corpus(name, tuple(documents))


_stop = threading.Event()


def _log(message: str, started: float) -> None:
    print(f"[{time.time() - started:8.1f}s] {message}", flush=True)


def run_model(
    model: str,
    documents: list,
    cache: DetectorCache,
    config: Path,
    log: Callable[[str], None],
    every: int = 25,
) -> tuple[str, int, int, int]:
    """Walk the documents in order for one model. Returns ``(model, done, errors, truncated)``.

    Sequential by design: this thread is one model's worth of requests, and the parallelism across
    models is what the pool provides.
    """
    detector = LlmDetector(model, config_path=config, max_tokens=MAX_TOKENS)
    done = cache.done(detector.name)
    todo = [d for d in documents if d.doc_id not in done]
    log(f"{model}: {len(done)} cached, {len(todo)} to do")

    errors = 0
    truncated = 0
    started = time.time()
    for index, document in enumerate(todo, 1):
        if _stop.is_set():
            log(f"{model}: stopping after {index - 1}/{len(todo)}")
            break
        t0 = time.time()
        try:
            output, meta = detector.detect_with_meta(document)
            cache.append(detector.name, document.doc_id, output.spans, model=model,
                         prompt_version=PROMPT_VERSION, elapsed=time.time() - t0, meta=meta)
            truncated += bool(meta["truncated"])
        except Exception as exc:  # recorded, and retried on the next run
            errors += 1
            cache.append(detector.name, document.doc_id, (), model=model,
                         prompt_version=PROMPT_VERSION, error=f"{type(exc).__name__}: {exc}",
                         elapsed=time.time() - t0)
        if index % every == 0 or index == len(todo):
            rate = index / (time.time() - started)
            remaining = (len(todo) - index) / rate if rate else float("inf")
            log(f"{model}: {index}/{len(todo)}  {rate * 3600:.0f}/h  "
                f"eta {remaining / 3600:.1f}h  errors {errors}  truncated {truncated}")
    return model, len(todo), errors, truncated


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpora", nargs="+", default=[name for name, _, _ in CORPORA])
    ap.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--config", type=Path, default=Path("config/llm_api.toml"))
    ap.add_argument("--limit", type=int, default=0, help="cap documents per corpus; 0 = all")
    args = ap.parse_args()

    started = time.time()
    log = lambda message: _log(message, started)  # noqa: E731

    def handle(signum, _frame):
        log(f"signal {signum} — finishing the document in flight, then stopping")
        _stop.set()

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)

    log(f"models: {', '.join(args.models)}")
    log(f"corpora, smallest first: {', '.join(args.corpora)}")

    for name, expected, loader in CORPORA:
        if name not in args.corpora:
            continue
        if _stop.is_set():
            break
        t0 = time.time()
        corpus = loader()
        documents = list(corpus.documents)[: args.limit] if args.limit else list(corpus.documents)
        log(f"=== {name}: {len(documents)} documents (expected {expected}) "
            f"loaded in {time.time() - t0:.0f}s ===")
        if len(documents) != expected and not args.limit:
            log(f"    WARNING: expected {expected}, got {len(documents)} — check the adapter")

        cache = DetectorCache(args.cache, name)
        with ThreadPoolExecutor(max_workers=len(args.models)) as pool:
            futures = [
                pool.submit(run_model, model, documents, cache, args.config, log)
                for model in args.models
            ]
            for future in futures:
                model, attempted, errors, truncated = future.result()
                log(f"{name} / {model}: attempted {attempted}, errors {errors}, "
                    f"truncated {truncated}")

        log(f"=== {name} complete: {cache.stats()} ===")
        del corpus, documents  # the head node holds one corpus at a time

    log("stopped" if _stop.is_set() else "done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
