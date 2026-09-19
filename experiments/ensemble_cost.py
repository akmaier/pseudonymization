"""What an ensemble costs, beside what it buys — the operating points worth deploying.

The §8.1 sweep ranks span sources by recall and precision alone, and on that table the best
ensembles are the ones that run the most models.  That is only half a decision.  A three-LLM
ensemble and a three-classical ensemble can land within a point of each other on recall while
differing by two orders of magnitude in what they cost to run, and the cost is the reason one of
them is deployable on a 58,636-document corpus and the other is not.

The measurement is already on disk and has been all along: :meth:`DetectorCache.append` records
``elapsed`` per document, so every detector carries its own observed latency on every corpus it was
run on — no estimate, no model card, no assumed hardware.  Two caveats travel with it and are
reported rather than smoothed away:

* The classical detectors ran on a GPU inside a Slurm allocation; the gateway detectors ran as a
  network client with a per-model concurrency.  ``elapsed`` is wall-clock per document in both cases,
  so a gateway number includes queueing at a shared deployment.  That is the honest cost of using it.
* An ensemble's cost is the **sum** of its members', because nothing here runs them concurrently.
  Run in parallel the cost would be the max; both are reported, and the sum is what the sweeps
  actually paid.

Three fronts, because "best" means different things to the three people who ask:

``recall``    most tokens caught, cost ignored — the de-identification reflex
``precision`` most of what is replaced deserved replacing — the utility-preserving choice
``cost``      the Pareto front itself: no cheaper ensemble scores higher

    python experiments/ensemble_cost.py --corpus cardiode
    python experiments/ensemble_cost.py --corpus cardiode --front precision --top 12
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pseudonymkit.detectors.cache import DetectorCache  # noqa: E402
from pseudonymkit.paths import work_dir  # noqa: E402


def latencies(cache: DetectorCache) -> dict[str, dict[str, float]]:
    """Observed seconds per document, per detector, from the cache's own records."""
    out: dict[str, dict[str, float]] = {}
    for path in sorted(cache.root.glob("*.jsonl")):
        detector = path.stem.replace("__", "/")
        seen: dict[str, float] = {}
        for record in cache._read(path):
            if record.get("error") is not None or record.get("elapsed") is None:
                continue
            seen[record["doc_id"]] = float(record["elapsed"])
        if not seen:
            continue
        values = sorted(seen.values())
        out[detector] = {
            "documents": len(values),
            "mean_s": statistics.fmean(values),
            "median_s": statistics.median(values),
            "p90_s": values[int(0.9 * (len(values) - 1))],
            "total_s": sum(values),
        }
    return out


def rows(path: Path, corpus: str):
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("corpus") == corpus and "gold" not in row.get("ensemble", ()):
            yield row


def pareto(candidates: list[dict], quality: str) -> list[dict]:
    """Ensembles that no cheaper ensemble beats on ``quality``.

    Walk cheapest first and keep a running best: an ensemble enters the front only by scoring higher
    than everything that costs less.  Ties lose, so the cheapest of several equal scorers is kept.
    """
    front, best = [], float("-inf")
    for row in sorted(candidates, key=lambda r: r["cost_serial_s"]):
        if row[quality] > best:
            best = row[quality]
            front.append(row)
    return front


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--detection", type=Path, default=None)
    ap.add_argument("--front", choices=["cost", "recall", "precision"], default="cost")
    ap.add_argument("--quality", choices=["token_recall", "information_weighted_precision"],
                    default="token_recall", help="the axis the cost front is drawn against")
    ap.add_argument("--max-size", type=int, default=3)
    ap.add_argument("--floor", type=float, default=0.0, help="minimum token recall")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", type=Path, default=None, help="write the annotated rows as JSONL")
    ap.add_argument("--timings-only", action="store_true",
                    help="per-detector cost, for a corpus whose sweep has not been run yet")
    args = ap.parse_args()

    root = args.cache or (work_dir() / "results" / "detector_cache")
    cache = DetectorCache(root, args.corpus)
    timing = latencies(cache)
    if not timing:
        raise SystemExit(f"no elapsed times in {cache.root}")

    print(f"=== {args.corpus}: observed cost per document ===")
    for detector, t in sorted(timing.items(), key=lambda kv: kv[1]["mean_s"]):
        family = "LLM      " if detector.startswith("llm:") else "classical"
        print(f"  {family} {detector:<56} mean {t['mean_s']:7.3f}s  median {t['median_s']:7.3f}s  "
              f"p90 {t['p90_s']:7.3f}s  n {t['documents']}")

    if args.timings_only:
        return 0

    path = args.detection or (work_dir() / "results" / "detection" / f"{args.corpus}.jsonl")
    if not path.exists():
        raise SystemExit(f"no sweep at {path}")

    candidates = []
    for row in rows(path, args.corpus):
        if row.get("size", 0) > args.max_size or (row.get("token_recall") or 0) < args.floor:
            continue
        members = row["ensemble"]
        if any(m not in timing for m in members):
            continue                     # a detector with no timing cannot be costed honestly
        serial = sum(timing[m]["mean_s"] for m in members)
        row["cost_serial_s"] = serial
        row["cost_parallel_s"] = max(timing[m]["mean_s"] for m in members)
        row["llm_members"] = sum(1 for m in members if m.startswith("llm:"))
        candidates.append(row)

    if not candidates:
        raise SystemExit("no ensemble could be costed")

    if args.front == "cost":
        selected = pareto(candidates, args.quality)
        title = (f"Pareto front: no cheaper ensemble scores higher on {args.quality} "
                 f"({len(selected)} of {len(candidates)})")
    else:
        key = "token_recall" if args.front == "recall" else "information_weighted_precision"
        selected = sorted(candidates, key=lambda r: (-r[key], r["cost_serial_s"]))[: args.top]
        title = f"top {args.top} by {key}, ties broken by cost"

    print(f"\n=== {args.corpus}: {title} ===")
    print(f"  {'cost/doc':>9} {'tokR':>6} {'entR':>6} {'iwP':>6} {'rule':<7} {'LLMs':>4}  ensemble")
    for row in selected[: args.top if args.front != "cost" else len(selected)]:
        names = "+".join(m.replace("llm:", "").replace("hf:", "").replace("gliner:", "")
                         for m in row["ensemble"])
        print(f"  {row['cost_serial_s']:8.3f}s {row['token_recall']:6.3f} "
              f"{row.get('entity_recall', float('nan')):6.3f} "
              f"{row['information_weighted_precision']:6.3f} {row['rule']:<7} "
              f"{row['llm_members']:>4}  {names}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as handle:
            for row in candidates:
                handle.write(json.dumps(row) + "\n")
        print(f"\nwrote {len(candidates)} costed rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
