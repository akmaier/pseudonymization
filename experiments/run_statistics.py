#!/usr/bin/env python3
"""§8.3's statistical protocol over the per-document utility vectors.

The vectors are the primary artefact (§9); this turns them into the tests §8.3 mandates and nothing
more. Conditions run on the same documents, so every comparison is **paired**:

* **Wilcoxon signed-rank** for continuous scores — F1 is bounded and skewed, so a t-test's normality
  assumption is unsafe.
* **McNemar** for binary correctness. The score *kind* decides, not the task name: a vector whose
  values are all 0 or 1 is binary however it was produced, and applying a rank test to it would give
  a p-value that looks fine and answers a different question.
* **An effect size beside every p-value** — rank-biserial or the discordant counts — because with
  n ≈ 400 almost anything reaches p < 0.05.
* **Benjamini–Hochberg across the comparison family.** §8.3 leaves the family to the caller and calls
  it a reporting decision; the family used here is **one task**, which is the reading its own wording
  supports ("dozens of conditions per task"). The choice is recorded in every row so a different one
  can be recomputed from the same vectors.

**A task whose original-text score is near chance is excluded, with the reason stated** — §8.3 is
explicit that its numbers are uninterpretable, and averaging it away silently is the failure the rule
exists to prevent.

    . config/env.sh
    python experiments/run_statistics.py --corpus cardiode
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path

from pseudonymkit.metrics.utility import benjamini_hochberg, compare
from pseudonymkit.tasks import scored

NEAR_CHANCE = 0.05
"""A reference mean at or below this is treated as uninterpretable and the task is excluded.

Not a tuned threshold: CARDIO:DE's ``medication_ie:in_narrative`` scores 0.036-0.041 on the
*original* text across every span source, which is what §8.3 describes. Anything near zero on
condition A cannot show a condition effect, because there is no signal to lose."""


def log(message: str) -> None:
    print(message, flush=True)


def load(path: Path) -> dict[str, dict[str, dict[str, float]]]:
    """task -> condition -> {doc_id: score}."""
    out: dict[str, dict[str, dict[str, float]]] = collections.defaultdict(dict)
    for line in path.open(encoding="utf-8"):
        row = json.loads(line)
        if not row.get("doc_id") or "score" not in row:
            continue
        out[row["task"]].setdefault(row["condition"], {})[row["doc_id"]] = row["score"]
    return out


def kind_of(scores) -> str:
    return "binary" if set(scores) <= {0.0, 1.0} else "continuous"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--utility", type=Path, default=Path("results/utility"))
    ap.add_argument("--out", type=Path, default=Path("results/statistics"))
    ap.add_argument("--alpha", type=float, default=0.05)
    args = ap.parse_args()

    sources = sorted(args.utility.glob(f"{args.corpus}*.jsonl"))
    if not sources:
        raise SystemExit(f"no utility vectors for {args.corpus} in {args.utility}")
    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"{args.corpus}.jsonl"
    rows: list[dict] = []

    for source in sources:
        span_source = source.stem[len(args.corpus):].lstrip("_") or "full"
        by_task = load(source)
        log(f"\n=== {source.name} ===")
        for task, conditions in sorted(by_task.items()):
            if "A" not in conditions:
                log(f"  {task}: no condition A — EXCLUDED (§8.3 requires the original beside each)")
                continue
            all_a = list(conditions["A"].values())
            reference_mean = statistics.fmean(all_a)
            # Named `_all` deliberately: this is over every condition-A document, whereas the
            # `reference_mean` a comparison row carries is over the documents A shares with B or C.
            # One field name for two populations in one file was a trap worth closing.
            reference_sd_all = statistics.stdev(all_a) if len(all_a) > 1 else float("nan")
            if reference_mean <= NEAR_CHANCE:
                log(f"  {task}: original-text mean {reference_mean:.4f}±{reference_sd_all:.4f} "
                    f"(n={len(all_a)}) is near chance — EXCLUDED, not averaged away (§8.3)")
                rows.append({"corpus": args.corpus, "span_source": span_source, "task": task,
                             "excluded": "near chance on the original text",
                             "reference_mean_all": reference_mean,
                             "reference_sd_all": reference_sd_all,
                             "n_all": len(all_a),
                             "near_chance_threshold": NEAR_CHANCE,
                             "dispersion_unit": "document"})
                continue

            family: list = []
            for condition in ("B", "C"):
                if condition not in conditions:
                    continue
                shared = sorted(set(conditions["A"]) & set(conditions[condition]))
                if len(shared) < 5:
                    continue
                a_scores = [conditions["A"][d] for d in shared]
                c_scores = [conditions[condition][d] for d in shared]
                kind = kind_of(a_scores + c_scores)
                ref = scored(task, "A", zip(shared, a_scores), model="frozen", kind=kind)
                cond = scored(task, condition, zip(shared, c_scores), model="frozen", kind=kind)
                family.append(compare(ref, cond))
            if not family:
                continue
            for comparison in benjamini_hochberg(family, alpha=args.alpha):
                record = comparison.to_record()
                record.update(corpus=args.corpus, span_source=span_source,
                              family="task", alpha=args.alpha)
                rows.append(record)
                star = "*" if comparison.significant else " "
                # The observed values come first and the test second, because a q-value is not a
                # result on its own (AM, 2026-09-22). `±` is one SD over documents.
                log(f"  {task:<28} A vs {comparison.condition}  {comparison.test:<8} "
                    f"n={comparison.n:<4} "
                    f"A={comparison.reference_mean:.4f}±{comparison.reference_sd:.4f} "
                    f"{comparison.condition}={comparison.condition_mean:.4f}"
                    f"±{comparison.condition_sd:.4f} "
                    f"Δ={comparison.mean_difference:+.4f}±{comparison.difference_sd:.4f} "
                    f"p={comparison.p_value:.3g} q={comparison.q_value:.3g}{star} "
                    f"{comparison.effect_name}={comparison.effect:+.3f} "
                    f"median Δ={comparison.median_difference:+.4f}")

    destination.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    log(f"\nwrote {len(rows)} rows to {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
