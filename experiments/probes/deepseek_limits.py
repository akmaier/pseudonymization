#!/usr/bin/env python3
"""Does DeepSeek finish if the limits are high enough? Re-send windows that truncated, with room.

AM, 2026-10-04: *"Check the limits. I think the limits are too low and need to be increased to stop
the truncation."* Three limits sit between DeepSeek and a finished reply, and only one of them had
been examined:

* **the output cap** — ``TokenBudget.max_tokens``, computed per window from the *estimated* prompt
  size (characters / 2.5). At the reasoning family's ratio that is 29,312 tokens for a full
  6,000-character window. Doubling it on 2026-10-02 still truncated 25 of 29 letters, but that only
  shows twice the cap is not enough, not that no cap is;
* **the client's read timeout** — ``LlmDetector`` waits ``max(300 s, …)`` for a reply. At the speed
  DeepSeek generates, a cap much above ~50,000 tokens would turn a long reply into a timeout and a
  retry instead of a finished answer, so the cap could never have been raised alone;
* **the gateway's own limits** — what it accepts as ``max_tokens`` and how long it lets a request
  run. Not documented; this measures them.

This sends windows that truncated in the family-cap re-run exactly as the detector does — its own
system prompt, temperature 0, the same 6,000-character windowing — with one change: a large fixed
cap and a long read timeout. For each window it records how the reply ended, how many tokens it
took and how long. A window that now ends on ``stop`` says the cap was too low; one that hits the
large cap says the reply has no natural end; an error or a time-out names the next limit.

Counts only: the CARDIO:DE text is read on the cluster and never printed or stored.

    . config/env.sh
    PYTHONPATH=src python experiments/probes/deepseek_limits.py --max-tokens 131072
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "src")

from pseudonymkit.detectors.llm import LlmDetector
from pseudonymkit.paths import cardiode_a, condition_a_dir
from pseudonymkit.serialisation import iter_documents

MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731"
PRINT = threading.Lock()


def truncated_windows(cache_file: Path, corpus_file: Path, per_corpus: int, window: int):
    """``(doc_id, window_index, text)`` for windows that ended on ``length`` in the cached run."""
    records = {}
    for line in cache_file.open():
        r = json.loads(line)
        records[r["doc_id"]] = r
    texts = {d.doc_id: d.text for d in iter_documents(corpus_file)}
    out = []
    for doc_id in sorted(records):
        reasons = records[doc_id].get("finish_reasons") or []
        if doc_id not in texts:
            continue
        chunks = [texts[doc_id][s:s + window] for s in range(0, max(len(texts[doc_id]), 1), window)]
        chunks = [c for c in chunks if c.strip()]
        for index, reason in enumerate(reasons):
            if reason == "length" and index < len(chunks):
                out.append((doc_id, index, chunks[index]))
                break
        if len(out) >= per_corpus:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-tokens", type=int, default=131_072)
    ap.add_argument("--timeout", type=int, default=3_600, help="client read timeout, seconds")
    ap.add_argument("--cardiode", type=int, default=6, help="truncated CARDIO:DE windows to re-send")
    ap.add_argument("--enron2", type=int, default=3, help="truncated ENRON 2.0 windows to re-send")
    ap.add_argument("--out", type=Path, default=Path("results/deepseek_limits.json"))
    args = ap.parse_args()

    detector = LlmDetector(MODEL, max_tokens=args.max_tokens, timeout=args.timeout, max_retries=2)
    window = detector._max_chars
    jobs = []
    root = Path("results/detector_cache_deepseek")
    for corpus, path, n in (("cardiode", cardiode_a(), args.cardiode),
                            ("enron2", condition_a_dir() / "enron2_A.jsonl.gz", args.enron2)):
        cache = root / corpus / "llm:deepseek-ai__DeepSeek-V4-Flash-0731.jsonl"
        for doc_id, index, text in truncated_windows(cache, path, n, window):
            jobs.append((corpus, doc_id, index, text))
    print(f"{len(jobs)} truncated windows to re-send, cap {args.max_tokens:,}, read timeout "
          f"{args.timeout:,} s, window {window} characters", flush=True)

    def send(job):
        corpus, doc_id, index, text = job
        started = time.time()
        try:
            _, reason, usage = detector._complete(text)
            error = None
        except Exception as exc:                      # the next limit, named
            reason, usage, error = None, {}, f"{type(exc).__name__}: {str(exc)[:200]}"
        row = {
            "corpus": corpus, "doc": doc_id.rsplit("/", 1)[-1], "window": index,
            "characters": len(text), "finish_reason": reason, "error": error,
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "seconds": round(time.time() - started, 1),
        }
        with PRINT:
            print(f"  {corpus:8s} window {index}  {row['finish_reason'] or row['error']!s:12.80s}  "
                  f"{row['completion_tokens']:>7,} tokens  {row['seconds']:>6.0f} s", flush=True)
        return row

    with ThreadPoolExecutor(max_workers=len(jobs) or 1) as pool:
        rows = list(pool.map(send, jobs))
    finished = sum(1 for r in rows if r["finish_reason"] == "stop")
    capped = sum(1 for r in rows if r["finish_reason"] == "length")
    print(f"finished {finished}, still cut at {args.max_tokens:,}: {capped}, "
          f"errors {sum(1 for r in rows if r['error'])}", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"model": MODEL, "max_tokens": args.max_tokens,
                                    "timeout": args.timeout, "window": window, "rows": rows},
                                   indent=1), encoding="utf-8")
    print(f"wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
