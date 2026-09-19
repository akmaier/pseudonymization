"""Choose the ensemble that the downstream cells are run on — and record why.

§7's D″ axis makes ensemble *size* a factor, and the §8.1 sweep scores every subset up to size three:
2,151 span sources on a fifteen-detector pool.  Utility, leakage and stability cannot be run on all
of them — each is a model-bound or attack-bound pass over the whole corpus — so a few are chosen.

The choice has to be made by a **stated rule applied to the sweep**, not by reading a table and
picking a favourite.  Two rules are offered because they answer different questions, and both are
defensible:

``recall``
    Highest token recall.  This is what a de-identification pipeline is usually tuned for, and it is
    the operating point at which §9's leakage numbers mean "even with almost everything caught".
``product``
    Highest ``token_recall × information_weighted_precision``.  Recall alone rewards an ensemble that
    covers the corpus by over-detecting, which destroys utility for a gain that never shows up in a
    recall column.  The product is the operating point a deployment would actually accept.

Neither is *the* answer, which is why the choice is printed with its scores and written beside the
patch set it produces.  ``--constraint`` lets the second question be asked at a floor on the first.

    python experiments/best_ensemble.py --corpus tab --size 3 --criterion product
    python experiments/best_ensemble.py --corpus tab --size 3 --criterion product --names
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def rows(path: Path, corpus: str):
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("corpus") == corpus and "gold" not in row.get("ensemble", ()):
            yield row


def score(row: dict, criterion: str) -> float:
    recall = row.get("token_recall") or 0.0
    if criterion == "recall":
        return recall
    return recall * (row.get("information_weighted_precision") or 0.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--detection", type=Path, default=None)
    ap.add_argument("--size", type=int, default=3)
    ap.add_argument("--rule", default=None, help="restrict to one combination rule")
    ap.add_argument("--criterion", choices=["product", "recall"], default="product")
    ap.add_argument("--constraint", type=float, default=0.0,
                    help="minimum token recall a candidate must reach")
    ap.add_argument("--names", action="store_true",
                    help="print only the detector names, one per line, for a shell to consume")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    path = args.detection or Path("results/detection") / f"{args.corpus}.jsonl"
    if not path.exists():
        raise SystemExit(f"no sweep at {path}; run experiments/score_detection.py --corpus "
                         f"{args.corpus} first")

    candidates = [r for r in rows(path, args.corpus)
                  if r.get("size") == args.size
                  and (args.rule is None or r.get("rule") == args.rule)
                  and (r.get("token_recall") or 0.0) >= args.constraint]
    if not candidates:
        raise SystemExit(f"no size-{args.size} source in {path} meets recall >= {args.constraint}"
                         + (f" under rule {args.rule!r}" if args.rule else ""))

    candidates.sort(key=lambda r: score(r, args.criterion), reverse=True)
    best = candidates[0]

    if args.names:
        for detector in best["ensemble"]:
            print(detector)
        return 0

    print(f"{args.corpus}: {len(candidates)} size-{args.size} sources considered"
          + (f", rule {args.rule}" if args.rule else "")
          + (f", recall floor {args.constraint}" if args.constraint else ""))
    print(f"criterion: {args.criterion}\n")
    for rank, row in enumerate(candidates[: args.top], start=1):
        mark = "->" if rank == 1 else "  "
        print(f"{mark} {rank}. rule={row['rule']:<6} score={score(row, args.criterion):.4f}  "
              f"tokR={row['token_recall']:.3f}  entR={row.get('entity_recall', float('nan')):.3f}  "
              f"P={row['precision']:.3f}  iwP={row['information_weighted_precision']:.3f}")
        for detector in row["ensemble"]:
            print(f"        {detector}")
    print(f"\nchosen rule: {best['rule']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
