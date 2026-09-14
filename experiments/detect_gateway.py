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
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterator

from dataclasses import replace as _replace

from pseudonymkit.detectors.cache import DetectorCache, text_digest
from pseudonymkit.detectors.llm import LlmDetector
from pseudonymkit.detectors.prompting import PROMPT_VERSION
from pseudonymkit.domain import Document
from pseudonymkit.serialisation import iter_documents

# Condition A, as built by experiments/build_A.py — never the raw releases.  Two runs spent four
# days detecting over the *pre*-condition-A texts because these constants pointed at the releases:
# CARDIO:DE's tag markup instead of the filled letter, and Enron's 66,432-document sample instead of
# the 58,636 that survive the empty-body exclusion.  The text hash in every cache record now makes
# that class of mistake loud, but the paths have to be right as well.
CONDITION_A = Path("data/conditionA")
CARDIODE_A = Path("/cluster/maier/dua-restricted/cardiode/A/cardiode_A.jsonl.gz")

DEFAULT_MODELS = (
    "gpt-oss-120b",
    "Qwen/Qwen3.6-35B-A3B-FP8",
    "RedHatAI/gemma-4-31B-it-FP8-block",
    "RedHatAI/Mistral-Small-3.2-24B-Instruct-2506-FP8",
    "GaleneAI/Magistral-Small-2509-FP8-Dynamic",
    "google/gemma-4-E4B-it",
    "Microsoft/Phi-4-mini-instruct",
    "ibm-granite/granite-4.1-3b",
)
"""**Every** chat model the gateway serves that can extract spans — what ``experiment_plan.md`` §7
axis D asks for. Eight, as of the probe of 2026-09-12 (AM, 2026-09-12).

``Phi-4-mini-instruct`` and ``granite-4.1-3b`` were missing until then: a gap between §7's wording
and this list, not a decision. Both answered a span-extraction prompt in **0.5 s** with clean JSON
against 4–25 s for the rest, so they cost almost nothing in wall clock — the pool runs a thread per
model and the wall clock is the slowest one. At 3–4 B parameters against 24–120 B they are also the
only small models here, which is the diversity H5's hybrid-versus-LLMs-only comparison feeds on;
granite already misses names the larger models catch, which is what makes an ensemble worth having.

Two of the gateway's ten chat models stay out. ``lightonai/LightOnOCR-2-1B`` echoed the system prompt
back and ran to ``finish=length`` — OCR-oriented, not a span extractor. **DeepSeek is excluded by
decision** (AM, 2026-09-10: *"C1 - no deepseek"*), independently of whether its backend answers."""

MAX_TOKENS: int | None = None
"""``None`` hands the cap to :class:`~pseudonymkit.detectors.budget.TokenBudget`, which sizes it per
request from the chunk and the model's family. Set it only to reproduce an old run.

It was ``16384``, and that constant silently defeated the entire budget: every request went out at
16,384 whatever the model or the input. Phi-4-mini's whole context **is** 16,384, so once a prompt
was added the request could not fit and it failed on 400 of 400 documents. The same override is why
the truncation figures measured on 2026-09-12 were still the old cap's, not the budget's."""

# Smallest first.  Paths, not loaders: nothing is read until a model thread walks it, and then it is
# **streamed** rather than materialised.  CodEAlltag is absent: it is out of the study (§11).
CORPORA: tuple[tuple[str, int, Path], ...] = (
    ("cardiode", 400, CARDIODE_A),
    ("tab", 1268, CONDITION_A / "tab_A.jsonl.gz"),
    ("ontonotes", 5994, CONDITION_A / "ontonotes_A.jsonl.gz"),
    ("enron", 58636, CONDITION_A / "enron_A.jsonl.gz"),
)


def _stream_a(path: Path) -> Iterator[Document]:
    """Stream a condition-A corpus, gold mentions dropped, **one document at a time**.

    Detection needs a document's id and its text and nothing else, while Enron's gold layer alone is
    845,156 ``Mention`` objects.  The gold stays in the file, where the metrics and the attacks read
    it later.

    The corpus is never materialised.  The previous version handed every model thread one shared
    in-memory list, which pinned all 58,636 Enron documents for the life of the process on a head
    node with 7 GB shared between users, and meant a condition A rebuilt underneath a running job
    could not be picked up without a restart (AM, 2026-09-14).  Re-reading the gzip once per model
    costs seconds against a run measured in days.
    """
    for document in iter_documents(path):
        yield _replace(document, mentions=())


_stop = threading.Event()

_INDEX_LOCK = threading.Lock()
_INDEX: dict[str, dict[str, str]] = {}


def _corpus_index(name: str, path: Path, args) -> dict[str, str]:
    """``doc_id -> digest of its condition-A text`` — the corpus reduced to what resume needs.

    This is what replaces holding the documents.  Eight model threads sit at different corpora at
    once, so whatever is kept per corpus is kept for the whole run; sixteen hex characters per
    document is a few megabytes for Enron, where the text itself is on the order of a gigabyte.

    One streaming pass, shared under a lock, used for exactly two things: the "N cached, M to do"
    counts a thread needs before it starts, and the sample/limit selection.
    """
    with _INDEX_LOCK:
        if name in _INDEX:
            return _INDEX[name]
    index: dict[str, str] = {}
    for document in _stream_a(path):
        index[document.doc_id] = text_digest(document.text)
    if args.sample:
        # Random under a recorded seed, never a prefix: document order is archive order in every one
        # of these corpora, so a prefix is a slice of one mailbox, one genre or one date.  Sampling
        # the ids in archive order picks the same positions the old document-level sample did.
        keep = min(len(index), max(args.sample_floor, round(len(index) * args.sample)))
        chosen = set(random.Random(f"{args.sample_seed}:{name}").sample(list(index), keep))
        index = {k: v for k, v in index.items() if k in chosen}
    elif args.limit:
        index = dict(list(index.items())[: args.limit])
    with _INDEX_LOCK:
        _INDEX.setdefault(name, index)
        return _INDEX[name]


def _log(message: str, started: float) -> None:
    print(f"[{time.time() - started:8.1f}s] {message}", flush=True)


def run_model(
    model: str,
    name: str,
    path: Path,
    index: dict[str, str],
    cache: DetectorCache,
    config: Path,
    log: Callable[[str], None],
    every: int = 25,
) -> tuple[str, int, int, int]:
    """Walk one corpus for one model, **streaming**.  Returns ``(model, done, errors, truncated)``.

    Sequential by design: this thread is one model's worth of requests, and the parallelism across
    models is what the pool provides.  Nothing is accumulated — every result is appended to the cache
    the moment it arrives, with ``flush()`` and ``fsync()``, so a killed job keeps everything it had
    finished and a restart resumes from the file rather than from memory.
    """
    # max_tokens=None hands the decision to TokenBudget, which sizes it from the chunk and the
    # model's family.  Passing a constant here silently overrode the whole budget: every request went
    # out at 16,384 regardless, which is one token more than Phi-4-mini's entire 16,384 context can
    # hold once a prompt is added — so that model failed on 400 of 400 documents.
    detector = LlmDetector(model, config_path=config, max_tokens=MAX_TOKENS)
    # What is already recorded, as digests rather than texts, so deciding what to skip costs no
    # memory.  A document whose text was rebuilt since it was cached has a different digest and is
    # re-detected: skipping it is how four days went into spans over a text that no longer existed.
    recorded = cache.digests(detector.name)
    todo = {doc_id for doc_id, digest in index.items() if recorded.get(doc_id) != digest}
    stale = sum(1 for doc_id in todo if doc_id in recorded)
    log(f"{model}: {len(index) - len(todo)} cached, {len(todo)} to do"
        + (f", {stale} stale (text changed) — re-detecting" if stale else ""))
    del recorded          # the id set is all that is needed from here on

    errors = truncated = seen = 0
    total = len(todo)
    started = time.time()
    for document in _stream_a(path):
        if document.doc_id not in todo:
            continue
        if _stop.is_set():
            log(f"{model}: stopping after {seen}/{total}")
            break
        seen += 1
        t0 = time.time()
        try:
            output, meta = detector.detect_with_meta(document)
            cache.append(detector.name, document.doc_id, output.spans, model=model,
                         prompt_version=PROMPT_VERSION, elapsed=time.time() - t0, meta=meta,
                         text=document.text)
            truncated += bool(meta["truncated"])
        except Exception as exc:  # recorded, and retried on the next run
            errors += 1
            cache.append(detector.name, document.doc_id, (), model=model,
                         prompt_version=PROMPT_VERSION, error=f"{type(exc).__name__}: {exc}",
                         elapsed=time.time() - t0, text=document.text)
        if seen % every == 0 or seen == total:
            rate = seen / (time.time() - started)
            remaining = (total - seen) / rate if rate else float("inf")
            log(f"{model}: {seen}/{total}  {rate * 3600:.0f}/h  "
                f"eta {remaining / 3600:.1f}h  errors {errors}  truncated {truncated}")
    return model, seen, errors, truncated


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpora", nargs="+", default=[name for name, _, _ in CORPORA])
    ap.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--config", type=Path, default=Path("config/llm_api.toml"))
    ap.add_argument("--limit", type=int, default=0, help="cap documents per corpus; 0 = all")
    ap.add_argument("--sample", type=float, default=0.0,
                    help="draw this fraction of each corpus at random instead of all of it; "
                         "for parameter sweeps, never for a reported cell")
    ap.add_argument("--sample-floor", type=int, default=50,
                    help="never draw fewer than this many per corpus — 1 %% of CARDIO:DE is 4 "
                         "documents, which measures nothing")
    ap.add_argument("--sample-seed", type=int, default=0)
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

    # Iteration follows CORPORA, not the order given on the command line, so **Enron is always last**
    # (AM, 2026-09-12).  It is 58,636 of the 66,298 documents: running it first would mean the three
    # small corpora sit behind a multi-day job, and nothing downstream could be checked until it
    # finished.  Last, every other corpus is complete within hours and Enron accumulates behind them.
    assert CORPORA[-1][0] == "enron", "Enron must be processed last"
    # One thread per model, each walking every corpus in order — **not** a corpus loop with a
    # model pool inside it.  That was the first shape, and it made every model wait at a barrier for
    # the slowest: granite finished TAB at 3,001/h and then sat idle for twelve hours while Qwen
    # ground through the same corpus at 37/h.  Six of eight threads doing nothing is the whole cost
    # of the barrier, and there is no reason for one — the cache keeps one file per
    # (corpus, detector), so each thread is still the only writer of its own files.
    wanted = [(n, e, p) for n, e, p in CORPORA if n in args.corpora]
    log(f"corpora in order: {', '.join(n for n, _, _ in wanted)}")

    def walk(model: str) -> tuple[str, int, int, int]:
        """One model, every corpus, in order.  Independent of every other model's progress."""
        attempted = errors = truncated = 0
        for name, expected, path in wanted:
            if _stop.is_set():
                break
            index = _corpus_index(name, path, args)
            cache = DetectorCache(args.cache, name)
            _, a, e, t = run_model(model, name, path, index, cache, args.config,
                                   lambda m: log(f"[{name}] {m}"))
            attempted += a
            errors += e
            truncated += t
            log(f"{name} / {model}: attempted {a}, errors {e}, truncated {t}")
        return model, attempted, errors, truncated

    with ThreadPoolExecutor(max_workers=len(args.models)) as pool:
        for future in [pool.submit(walk, model) for model in args.models]:
            model, attempted, errors, truncated = future.result()
            log(f"DONE {model}: attempted {attempted}, errors {errors}, truncated {truncated}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
