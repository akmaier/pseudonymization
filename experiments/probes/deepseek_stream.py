#!/usr/bin/env python3
"""Does streaming get DeepSeek past the gateway's ten-minute limit?

``deepseek_limits.py`` (2026-10-04) re-sent nine windows that had truncated, with a 131,072-token cap
and a one-hour client timeout. None reached the cap; three finished, and six were killed at about
600 seconds — ``HTTP 408 litellm.Timeout`` from the gateway, or ``HTTP 502`` from the proxy in front
of it. So the binding limit is a time limit on the request, not the output cap: at the 25–55 tokens
a second DeepSeek manages under load, ten minutes holds only ~15,000–33,000 tokens.

A proxy's time limit is usually on silence — how long it waits between two reads — rather than on
the whole exchange. With ``stream: true`` the reply arrives as it is generated, so the connection is
never silent for long. This sends the windows that were killed, exactly as the detector would (its
system prompt, its types, temperature 0, the same window), with streaming on, and records how each
reply ends. If they finish, streaming is the fix and the detector needs a streaming path; if they
are still cut at ten minutes, the limit is on the whole request and only the gateway's operators can
lift it.

Counts only. The API key is read by the detector's own loader and never printed.

    . config/env.sh
    PYTHONPATH=src python experiments/probes/deepseek_stream.py
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "experiments/probes")

from deepseek_limits import MODEL, truncated_windows
from pseudonymkit.detectors.llm import _SYSTEM, LlmDetector
from pseudonymkit.paths import cardiode_a, condition_a_dir

PRINT = threading.Lock()


def stream_once(detector: LlmDetector, text: str, max_tokens: int, timeout: int) -> dict:
    """One streamed request. Returns finish reason, token counts and timing — never the text."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"Types: {', '.join(detector._types)}\n\n{text}"},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    request = urllib.request.Request(
        f"{detector._base}/chat/completions", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {detector._key}"},
        method="POST")
    started = time.time()
    first = None
    finish = None
    usage: dict = {}
    chunks = 0
    longest_gap = 0.0
    last = started
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw in response:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                now = time.time()
                longest_gap = max(longest_gap, now - last)
                last = now
                chunks += 1
                first = first or now
                event = json.loads(data)
                if event.get("usage"):
                    usage = event["usage"]
                for choice in event.get("choices") or []:
                    if choice.get("finish_reason"):
                        finish = choice["finish_reason"]
        error = None
    except Exception as exc:
        error = f"{type(exc).__name__}: {str(exc)[:160]}"
    return {
        "finish_reason": finish, "error": error, "chunks": chunks,
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "seconds": round(time.time() - started, 1),
        "first_chunk_after": round((first or time.time()) - started, 1),
        "longest_silence": round(longest_gap, 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-tokens", type=int, default=131_072)
    ap.add_argument("--timeout", type=int, default=3_600)
    ap.add_argument("--previous", type=Path, default=Path("results/deepseek_limits.json"))
    ap.add_argument("--out", type=Path, default=Path("results/deepseek_stream.json"))
    args = ap.parse_args()

    previous = json.loads(args.previous.read_text())
    killed = {(r["corpus"], r["doc"], r["window"]) for r in previous["rows"] if r["error"]}
    detector = LlmDetector(MODEL, max_tokens=args.max_tokens, timeout=args.timeout, max_retries=1)
    window = detector._max_chars
    jobs = []
    root = Path("results/detector_cache_deepseek")
    for corpus, path in (("cardiode", cardiode_a()), ("enron2", condition_a_dir() / "enron2_A.jsonl.gz")):
        cache = root / corpus / "llm:deepseek-ai__DeepSeek-V4-Flash-0731.jsonl"
        n = sum(1 for r in previous["rows"] if r["corpus"] == corpus)
        for doc_id, index, text in truncated_windows(cache, path, n, window):
            if (corpus, doc_id.rsplit("/", 1)[-1], index) in killed:
                jobs.append((corpus, doc_id, index, text))
    print(f"{len(jobs)} windows the gateway killed last time, re-sent streamed: cap "
          f"{args.max_tokens:,}, client timeout {args.timeout:,} s", flush=True)

    def send(job):
        corpus, doc_id, index, text = job
        row = {"corpus": corpus, "doc": doc_id.rsplit("/", 1)[-1], "window": index,
               **stream_once(detector, text, args.max_tokens, args.timeout)}
        with PRINT:
            print(f"  {corpus:8s} window {index}  {row['finish_reason'] or row['error']!s:12.70s}  "
                  f"{row['completion_tokens']:>7,} tokens  {row['seconds']:>6.0f} s  "
                  f"longest silence {row['longest_silence']:.0f} s", flush=True)
        return row

    with ThreadPoolExecutor(max_workers=len(jobs) or 1) as pool:
        rows = list(pool.map(send, jobs))
    print(f"finished {sum(1 for r in rows if r['finish_reason'] == 'stop')}, cut at the cap "
          f"{sum(1 for r in rows if r['finish_reason'] == 'length')}, errors "
          f"{sum(1 for r in rows if r['error'])}", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"model": MODEL, "stream": True, "max_tokens": args.max_tokens,
                                    "rows": rows}, indent=1), encoding="utf-8")
    print(f"wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
