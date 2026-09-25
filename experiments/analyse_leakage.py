"""H1 and H5 read off the leakage sweep — with the denominator that makes them mean anything.

§6's H1 is *"leakage recomputed at each recall level"*, and the sweep produces exactly that: one row
per span source, carrying its detection numbers and its attack numbers together.  The trap is in
reading the attack numbers raw.

A2's top-1 accuracy is a rate over the candidates the attacker has to choose between, and that
denominator is not constant across the sweep — it *is* the thing recall changes.  A permissive
ensemble replaces more entities, so the attacker faces a larger pool; a restrictive one replaces few,
so the pool is small and a hit is cheap.  On TAB the raw rate therefore *falls* as recall rises
(0.0157 at recall < 0.3, 0.0103 at recall 0.7-0.9) and the obvious conclusion — that detecting more
protects better — is an artefact of the pool growing from 2,276 candidates to 7,226.

Measured against chance for its own pool, the same attack gets monotonically **stronger**:

    recall < 0.3      31x chance
    recall 0.3-0.5    44x
    recall 0.5-0.7    56x
    recall 0.7-0.9    75x

So this reports both: the raw rate, and the lift over the chance rate for that row's own candidate
set.  Reporting only the first would invert the finding.

    python experiments/analyse_leakage.py --corpus tab
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

BANDS = ((0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01))


def load(path: Path) -> list[dict]:
    rows = []
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("a2_top1") is not None:
            rows.append(row)
    return rows


def summarise(rows: list[dict], label: str) -> dict | None:
    if not rows:
        return None
    candidates = [r["a2_candidates"] for r in rows if r.get("a2_candidates")]
    lift = [r["a2_top1"] * r["a2_candidates"] for r in rows if r.get("a2_candidates")]
    rho = [r["a2_rho"] for r in rows if r.get("a2_rho") is not None]
    top1 = [r["a2_top1"] for r in rows]
    top5 = [r["a2_top5"] for r in rows]
    # `lift` is already the recovered count: (top1/n) * n. Named for what it is, and given the
    # binomial SD of that count within each row, which needs no resampling.
    recovered = lift
    within = [((r["a2_top1"] * (1.0 - r["a2_top1"]) * r["a2_candidates"]) ** 0.5)
              for r in rows if r.get("a2_candidates")]

    def spread(values):
        """SD over span sources — `None`, never 0.0, when a single source cannot have one."""
        return statistics.stdev(values) if len(values) > 1 else None

    out = {
        "group": label, "n": len(rows),
        "a2_top1": statistics.fmean(top1),
        "a2_top1_sd": spread(top1),
        "a2_top5": statistics.fmean(top5),
        "a2_top5_sd": spread(top5),
        "a2_top1_max": max(top1),
        "candidates": statistics.fmean(candidates) if candidates else None,
        "candidates_sd": spread(candidates) if candidates else None,
        "lift_over_chance": statistics.fmean(lift) if lift else None,
        "lift_over_chance_sd": spread(lift) if lift else None,
        "recovered_mean": statistics.fmean(recovered) if recovered else None,
        "recovered_binomial_sd": statistics.fmean(within) if within else None,
        "rank_correlation": statistics.fmean(rho) if rho else None,
        "rank_correlation_sd": spread(rho) if rho else None,
        "dispersion_unit": "span_source",
        "n_span_sources": len(rows),
    }

    def pm(value, sd, fmt=".4f"):
        return f"{value:{fmt}}" + ("" if sd is None else f"\u00b1{sd:{fmt}}")

    print(f"  {label:<32} n={out['n']:>5}  "
          f"top1 {pm(out['a2_top1'], out['a2_top1_sd'])}  "
          f"top5 {pm(out['a2_top5'], out['a2_top5_sd'])}  "
          f"cand {pm(out['candidates'], out['candidates_sd'], '.0f'):>16}  "
          f"lift {pm(out['lift_over_chance'], out['lift_over_chance_sd'], '.1f'):>14}x  "
          f"rho {pm(out['rank_correlation'], out['rank_correlation_sd'], '+.3f')}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--sweep", type=Path, default=None)
    ap.add_argument("--entity-type", default="PERSON")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    path = args.sweep or (Path("results/leakage_sweep") / f"{args.corpus}_{args.entity_type}.jsonl")
    rows = load(path)
    if not rows:
        raise SystemExit(f"no scored rows in {path}")
    relational = {r.get("relational_computable") for r in rows}
    print(f"=== {args.corpus}: {len(rows)} span sources, entity type {args.entity_type} ===")
    if relational == {False}:
        note = next((r.get("relational_note") for r in rows if r.get("relational_note")), None)
        print(f"  A3/A5 not computable here — {note}")

    out = []
    print("\n--- H1: leakage at each recall level ---")
    for low, high in BANDS:
        band = [r for r in rows if low <= (r.get("token_recall") or 0) < high]
        got = summarise(band, f"token recall [{low:.1f},{high:.1f})")
        if got:
            out.append(got | {"kind": "recall_band", "low": low, "high": high})

    print("\n--- H5: LLMs-only against the same plus a classical detector ---")
    for label, sel in (("LLMs only", [r for r in rows if r.get("llms_only")]),
                       ("with a classical detector", [r for r in rows if not r.get("llms_only")])):
        got = summarise(sel, label)
        if got:
            out.append(got | {"kind": "h5"})

    print("\n--- by combination rule ---")
    for rule in ("single", "union", "intersection", "vote"):
        got = summarise([r for r in rows if r.get("rule") == rule], rule)
        if got:
            out.append(got | {"kind": "rule", "rule": rule})

    print("\n--- by ensemble size ---")
    for size in (1, 2, 3):
        got = summarise([r for r in rows if r.get("size") == size], f"size {size}")
        if got:
            out.append(got | {"kind": "size", "size": size})

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        destination = args.out / f"{args.corpus}_{args.entity_type}_summary.jsonl"
        destination.write_text(
            "\n".join(json.dumps(r | {"corpus": args.corpus}) for r in out) + "\n",
            encoding="utf-8")
        print(f"\nwrote {len(out)} rows to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
