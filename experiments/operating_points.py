"""The four operating points — fast, specific, precise, and fast-and-precise.

AM asked which ensembles maximise *fast and precise / specific*, and which maximise *precise / fast*.
That is four points, and an earlier pass recorded three: it kept FAST and PRECISE, invented a CEILING
(highest recall at any cost) that had not been asked for, and dropped SPECIFIC entirely — which was
the one requiring a metric the sweep did not carry.

**Specificity is not precision.**  Precision asks what share of the tokens the detector *flagged*
really were identifiers.  Specificity asks what share of the tokens that were *not* identifiers the
detector correctly left alone.  They answer different questions and they diverge exactly where it
matters here: identifiers are a small minority of any corpus, so a detector can be mediocre at
precision and still excellent at specificity, and a permissive ensemble that wrecks utility shows
that damage far more sharply in specificity than in precision.  Specificity is, in this study, the
direct measure of how much of the text pseudonymisation left untouched — which is the quantity §8.3's
utility tasks are indirectly reacting to.

    specificity = TN / (TN + FP),  over tokens
                = (negatives - FP) / negatives
    negatives   = corpus tokens - gold tokens
    FP          = predicted tokens - true positive tokens

Computed post hoc from what the sweep already records, so no sweep is re-run: `gold_tokens`,
`predicted_tokens` and `true_positive_tokens` are per row, and the corpus token total is a single
number per corpus.

    python experiments/operating_points.py --corpus cardiode
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ensemble_cost import latencies, rows  # noqa: E402
from score_detection import CORPORA  # noqa: E402

from pseudonymkit.detectors.cache import DetectorCache  # noqa: E402
from pseudonymkit.metrics.detection import tokenise  # noqa: E402
from pseudonymkit.paths import work_dir  # noqa: E402
from pseudonymkit.serialisation import iter_documents  # noqa: E402


def corpus_tokens(corpus: str) -> int:
    """Total tokens, counted the way the scorer counts them."""
    return sum(len(list(tokenise(d.text))) for d in iter_documents(CORPORA[corpus]()))


def specificity(row: dict, total_tokens: int) -> float | None:
    """Share of non-identifier tokens the ensemble correctly left alone."""
    negatives = total_tokens - (row.get("gold_tokens") or 0)
    if negatives <= 0:
        return None
    false_positives = (row.get("predicted_tokens") or 0) - (row.get("true_positive_tokens") or 0)
    return max(0.0, (negatives - false_positives)) / negatives


POINTS = {
    "FAST": {
        "why": "cheapest ensemble that still clears the recall floor — what is deployable at scale",
        "key": lambda r: (-r["cost_serial_s"], r["token_recall"]),
    },
    "SPECIFIC": {
        "why": "leaves the most non-identifier text untouched — the direct utility-preserving choice",
        "key": lambda r: (r["specificity"], -r["cost_serial_s"]),
    },
    "PRECISE": {
        "why": "most of what it replaced deserved replacing — information-weighted, so a rare "
               "identifier counts for more than a common token",
        "key": lambda r: (r["information_weighted_precision"], -r["cost_serial_s"]),
    },
    "FAST+PRECISE": {
        "why": "the joint optimum: information-weighted precision bought per second of detection",
        "key": lambda r: (r["information_weighted_precision"] / max(r["cost_serial_s"], 1e-9),),
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(CORPORA))
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--detection", type=Path, default=None)
    ap.add_argument("--floor", type=float, default=0.5, help="minimum token recall to qualify")
    ap.add_argument("--max-size", type=int, default=3)
    ap.add_argument("--tokens", type=int, default=0, help="corpus token total, if already known")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    total = args.tokens or corpus_tokens(args.corpus)
    root = args.cache or (work_dir() / "results" / "detector_cache")
    timing = latencies(DetectorCache(root, args.corpus))
    path = args.detection or (work_dir() / "results" / "detection" / f"{args.corpus}.jsonl")

    candidates = []
    for row in rows(path, args.corpus):
        if row.get("size", 0) > args.max_size or (row.get("token_recall") or 0) < args.floor:
            continue
        if any(m not in timing for m in row["ensemble"]):
            continue
        row["cost_serial_s"] = sum(timing[m]["mean_s"] for m in row["ensemble"])
        row["specificity"] = specificity(row, total)
        if row["specificity"] is None:
            continue
        candidates.append(row)
    if not candidates:
        raise SystemExit(f"no ensemble clears recall {args.floor} on {args.corpus}")

    print(f"=== {args.corpus}: {len(candidates)} ensembles at token recall >= {args.floor}, "
          f"{total:,} corpus tokens ===\n")
    chosen = {}
    for name, spec in POINTS.items():
        best = max(candidates, key=spec["key"])
        chosen[name] = best
        members = "+".join(m.replace("llm:", "").replace("hf:", "").replace("gliner:", "")
                           for m in best["ensemble"])
        print(f"{name}")
        print(f"  {spec['why']}")
        print(f"  {best['cost_serial_s']:7.3f}s/doc  tokR {best['token_recall']:.3f}  "
              f"spec {best['specificity']:.5f}  iwP {best['information_weighted_precision']:.3f}  "
              f"P {best['precision']:.3f}  rule {best['rule']}")
        print(f"  {members}\n")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        destination = args.out / f"{args.corpus}_operating_points.json"
        destination.write_text(json.dumps({
            "corpus": args.corpus, "corpus_tokens": total, "recall_floor": args.floor,
            "candidates": len(candidates),
            "points": {n: {"ensemble": r["ensemble"], "rule": r["rule"],
                           "cost_serial_s": r["cost_serial_s"], "token_recall": r["token_recall"],
                           "specificity": r["specificity"], "precision": r["precision"],
                           "information_weighted_precision": r["information_weighted_precision"],
                           "why": POINTS[n]["why"]}
                       for n, r in chosen.items()},
        }, indent=2), encoding="utf-8")
        print(f"wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
