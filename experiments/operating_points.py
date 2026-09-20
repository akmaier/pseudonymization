"""The four operating points: fast against maximum, on specificity and sensitivity.

AM, 2026-09-20: *"Want fast vs. Maximum on specificity and sensitivity. As we can run methods in
parallel fast should be the max of the three methods considered. For fast, we exclude solutions that
are not within 10% of the max."*

Two qualities, two cost regimes, four cells:

=================  ======================================  ==================================
                   **sensitivity** (token recall)          **specificity**
=================  ======================================  ==================================
**maximum**        the most identifiers caught, at any     the most non-identifier text left
                   cost                                    alone, at any cost
**fast**           the cheapest ensemble still within      the cheapest ensemble still within
                   10 % of that maximum                    10 % of that maximum
=================  ======================================  ==================================

**Sensitivity and specificity, not precision.**  They are the two error rates of the detector read
against their own denominators — sensitivity over the identifier tokens, specificity over everything
else — and between them they say what a pseudonymisation pipeline did and did not touch.  Precision
mixes the two denominators and is reported alongside, not optimised for.

**Cost is the *maximum* over the ensemble's members, not their sum.**  The detectors are independent
passes over the same text and nothing in this pipeline makes one wait for another, so an ensemble run
in parallel costs what its slowest member costs.  That changes the ranking substantially: summing
punishes a three-detector ensemble for its two cheap members, and the whole point of the fast cells
is that adding a fast detector to a slow one is free.

**The 10 % band is relative to the achievable maximum**, so a candidate qualifies when its score is
at least 0.9 x the best score any candidate reaches.  How much that binds depends on the spread of
the quality being banded, and the two differ sharply — see the note the driver prints.

**A recall floor is kept for the specificity cells and is not optional.**  Specificity is
``1 - FP/negatives``; an ensemble that predicts nothing has no false positives and scores a perfect
1.0 while catching nothing at all.  Maximising specificity without a sensitivity constraint therefore
selects the emptiest ensemble available, which is not an operating point but a degenerate solution.
The floor is reported with every selection.

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

from pseudonymkit.conditions import CONSTRUCTED, POOLED, UNCHANGED  # noqa: E402
from pseudonymkit.detectors.cache import DetectorCache  # noqa: E402
from pseudonymkit.metrics.detection import tokenise  # noqa: E402
from pseudonymkit.paths import work_dir  # noqa: E402
from pseudonymkit.serialisation import iter_documents  # noqa: E402


def corpus_tokens(corpus: str) -> int:
    """Total tokens, counted the way the scorer counts them."""
    return sum(len(list(tokenise(d.text))) for d in iter_documents(CORPORA[corpus]()))


REPLACED = frozenset(POOLED) | frozenset(CONSTRUCTED)
"""The types condition B replaces. Sensitivity is scored over these and no others."""


def sensitivity(row: dict) -> float | None:
    """Recall over the identifiers condition B actually replaces.

    ``token_recall`` in the sweep is over *every* gold token, and ``UNCHANGED`` — DATETIME, QUANTITY,
    MISC — is passed through by design (AM, 2026-09-13). That is 84.7 % of CARDIO:DE's gold tokens,
    45.1 % of TAB's and 35.6 % of OntoNotes'. Selecting an operating point on it means selecting
    largely on dates nobody intends to replace, and it does not merely blur the ranking — it changes
    the winner. On CARDIO:DE the all-gold maximum reaches 0.9849 while scoring **0.9328** on the
    identifiers that matter, where a different ensemble reaches 0.9887 on those. Five and a half
    points of real sensitivity were being handed over to a metric dominated by dates.

    Specificity needs no such correction: a flagged DATETIME token is routed to ``PassThrough`` and
    left unchanged, so it costs nothing and is already counted as a true positive rather than a false
    one.
    """
    per_type = row.get("per_type") or {}
    gold = sum(v[0] for t, v in per_type.items() if t in REPLACED)
    hit = sum(v[2] for t, v in per_type.items() if t in REPLACED)
    return (hit / gold) if gold else None


def specificity(row: dict, total_tokens: int) -> float | None:
    """Share of non-identifier tokens the ensemble correctly left alone."""
    negatives = total_tokens - (row.get("gold_tokens") or 0)
    if negatives <= 0:
        return None
    false_positives = (row.get("predicted_tokens") or 0) - (row.get("true_positive_tokens") or 0)
    return max(0.0, (negatives - false_positives)) / negatives


BAND = 0.10
"""How far below the achievable maximum a "fast" candidate may fall (AM, 2026-09-20)."""


def leakage(row: dict) -> dict:
    """What escapes into the released text at this operating point.

    Sensitivity is a rate; this is the count behind it, and the entity view beside it.  The two say
    different things and the second is the one that matters for re-identification: an entity counts
    as *protected* only when **every** one of its mentions was caught, so a single missed occurrence
    of a name puts that person back in the clear no matter how many other mentions were replaced.
    Token recall of 0.98 can still leave a fifth of the people in a corpus identifiable.
    """
    gold_tokens = row.get("gold_tokens") or 0
    missed_tokens = gold_tokens - (row.get("true_positive_tokens") or 0)
    gold_entities = row.get("gold_entities") or 0
    exposed = gold_entities - (row.get("protected_entities") or 0)
    documents = row.get("documents") or 1
    return {
        "gold_tokens": gold_tokens,
        "tokens": missed_tokens,
        "token_rate": missed_tokens / max(gold_tokens, 1),
        "tokens_per_document": missed_tokens / max(documents, 1),
        "gold_entities": gold_entities,
        "entities": exposed,
        "entity_rate": exposed / max(gold_entities, 1),
        "entities_per_document": exposed / max(documents, 1),
    }


def select(candidates: list[dict], metric: str) -> dict[str, dict]:
    """The maximum-quality and the fastest-within-band ensemble for one metric.

    Ties on cost are broken by quality, so the fast cell never prefers a worse ensemble that happens
    to cost the same.
    """
    best = max(candidates, key=lambda r: (r[metric], -r["cost_parallel_s"]))
    threshold = best[metric] * (1.0 - BAND)
    within = [r for r in candidates if r[metric] >= threshold]
    fastest = min(within, key=lambda r: (r["cost_parallel_s"], -r[metric]))
    return {"max": best, "fast": fastest, "threshold": threshold, "within": len(within)}


METRICS = {
    "sensitivity": ("sensitivity", "identifier tokens caught, over the types B replaces"),
    "specificity": ("specificity", "non-identifier tokens left alone"),
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
        if row.get("size", 0) > args.max_size:
            continue
        if any(m not in timing for m in row["ensemble"]):
            continue
        row["sensitivity"] = sensitivity(row)
        if row["sensitivity"] is None or row["sensitivity"] < args.floor:
            continue
        # Parallel: the ensemble costs what its slowest member costs (AM, 2026-09-20).
        row["cost_parallel_s"] = max(timing[m]["mean_s"] for m in row["ensemble"])
        row["cost_serial_s"] = sum(timing[m]["mean_s"] for m in row["ensemble"])
        row["specificity"] = specificity(row, total)
        if row["specificity"] is None:
            continue
        candidates.append(row)
    if not candidates:
        raise SystemExit(f"no ensemble clears recall {args.floor} on {args.corpus}")

    print(f"=== {args.corpus}: {len(candidates)} ensembles, {total:,} tokens, "
          f"sensitivity floor {args.floor} ===")
    print("cost is the slowest member, not the sum — the detectors run in parallel\n")

    chosen: dict[str, dict] = {}
    for label, (metric, gloss) in METRICS.items():
        picked = select(candidates, metric)
        spread = (min(r[metric] for r in candidates), max(r[metric] for r in candidates))
        print(f"--- {label} ({gloss}) — observed {spread[0]:.4f} to {spread[1]:.4f}, "
              f"10 % band admits {picked['within']} of {len(candidates)} ---")
        for cell in ("max", "fast"):
            r = picked[cell]
            members = "+".join(m.replace("llm:", "").replace("hf:", "").replace("gliner:", "")
                               for m in r["ensemble"])
            chosen[f"{cell.upper()}-{label.upper()}"] = r
            print(f"  {cell.upper():<4} {r['cost_parallel_s']:7.3f}s  "
                  f"sens {r['sensitivity']:.3f}  spec {r['specificity']:.5f}  "
                  f"iwP {r['information_weighted_precision']:.3f}  {r['rule']:<13} {members}")
            leak = leakage(r)
            print(f"       leaks {leak['tokens']:,} of {leak['gold_tokens']:,} identifier tokens "
                  f"({leak['token_rate']:.2%}), {leak['tokens_per_document']:.2f}/document; "
                  f"{leak['entities']:,} of {leak['gold_entities']:,} entities keep at least one "
                  f"mention in the clear ({leak['entity_rate']:.2%})")
        print()

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        destination = args.out / f"{args.corpus}_operating_points.json"
        destination.write_text(json.dumps({
            "corpus": args.corpus, "corpus_tokens": total, "sensitivity_floor": args.floor,
            "sensitivity_scored_over": sorted(REPLACED),
            "types_retained_by_design": sorted(UNCHANGED),
            "band": BAND, "cost_model": "parallel: max over members",
            "decision": "AM, 2026-09-20: fast vs maximum on specificity and sensitivity; "
                        "parallel cost; fast excludes anything not within 10% of the max",
            "candidates": len(candidates),
            "points": {n: {"ensemble": r["ensemble"], "rule": r["rule"],
                           "cost_parallel_s": r["cost_parallel_s"],
                           "cost_serial_s": r["cost_serial_s"],
                           "sensitivity": r["sensitivity"],
                           "token_recall_all_gold": r["token_recall"],
                           "specificity": r["specificity"],
                           "precision": r["precision"],
                           "information_weighted_precision": r["information_weighted_precision"],
                           "leakage": leakage(r)}
                       for n, r in chosen.items()},
        }, indent=2), encoding="utf-8")
        print(f"wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
