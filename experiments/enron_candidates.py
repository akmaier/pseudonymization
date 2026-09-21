"""Which span sources the Enron leakage sweep should actually run.

The full sweep is 1,743 sources at ~257 s each — 124 hours, which does not fit before submission and
is not worth its cost: Enron is 46x TAB, every phase is linear in documents, and most of those
sources are subsets nobody would deploy.

AM, 2026-09-21: *"We only need to sweep across promising candidates on Enron. We take only the top
10% from cardio, ontonotes and tab; also I want the large ensemble; we should exclude gpt-oss and
qwen for the large ensemble. They are too slow and block the next experiments. Also no gpt or qwen
should be in the sweep subset candidates. It's enough if they have the single detector results."*

So the candidate set is:

* the **top decile** of span sources on each of CARDIO:DE, OntoNotes and TAB, ranked by
  sensitivity x specificity — the two axes the operating points are defined on — unioned across the
  three corpora, because a source promising anywhere is worth measuring here;
* plus the **large ensemble**, every detector except `gpt-oss-120b` and `Qwen/Qwen3.6-35B-A3B-FP8`,
  under each combination rule;
* minus anything containing either of those two models, which stay in the study through their
  single-detector rows.

Ranking on another corpus rather than on Enron is deliberate: choosing Enron's sources by Enron's own
scores would select on the outcome being measured.

    python experiments/enron_candidates.py --out results/leakage_sweep/enron_sources.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pseudonymkit.conditions import CONSTRUCTED, POOLED  # noqa: E402
from pseudonymkit.detectors.cache import DetectorCache  # noqa: E402
from pseudonymkit.paths import work_dir  # noqa: E402

REPLACED = frozenset(POOLED) | frozenset(CONSTRUCTED)
SLOW = ("llm:gpt-oss-120b", "llm:Qwen/Qwen3.6-35B-A3B-FP8")
"""Excluded from every ensemble here. Both cost 25-443 s a document and they gate the queue; §7's
axis D keeps them through their single-detector rows, which is what the paper reports them on."""


def label(ensemble, rule: str, k) -> str:
    """The `source` string sweep_leakage writes, so the two agree exactly."""
    return f"{'+'.join(ensemble)}|{rule}{k or ''}"


def scored(path: Path, corpus: str, total_tokens: int):
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("corpus") != corpus or "gold" in row.get("ensemble", ()):
            continue
        per_type = row.get("per_type") or {}
        gold = sum(v[0] for t, v in per_type.items() if t in REPLACED)
        hit = sum(v[2] for t, v in per_type.items() if t in REPLACED)
        if not gold:
            continue
        negatives = total_tokens - (row.get("gold_tokens") or 0)
        false_pos = (row.get("predicted_tokens") or 0) - (row.get("true_positive_tokens") or 0)
        row["score"] = (hit / gold) * (max(0.0, negatives - false_pos) / max(negatives, 1))
        yield row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-corpora", nargs="+", default=["cardiode", "ontonotes", "tab"])
    ap.add_argument("--decile", type=float, default=0.10)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    tokens = {"cardiode": 885059, "tab": 1844804, "ontonotes": 4726594}
    chosen: dict[str, str] = {}
    for corpus in args.from_corpora:
        path = work_dir() / "results" / "detection" / f"{corpus}.jsonl"
        rows = [r for r in scored(path, corpus, tokens[corpus])
                if not any(m in SLOW for m in r["ensemble"])]
        rows.sort(key=lambda r: -r["score"])
        take = rows[: max(1, int(len(rows) * args.decile))]
        for row in take:
            rule = row["rule"] if row["rule"] != "single" else "union"
            chosen.setdefault(label(row["ensemble"], rule, row.get("k")), corpus)
        print(f"  {corpus:<10} {len(rows):>5} sources without the slow pair, "
              f"top {args.decile:.0%} = {len(take)}")

    # The large ensemble: everything the cache holds except the two slow models.
    cache = DetectorCache(work_dir() / "results" / "detector_cache", "enron")
    large = sorted(p.stem.replace("__", "/") for p in cache.root.glob("*.jsonl"))
    large = [d for d in large if d not in SLOW]
    for rule, k in (("union", None), ("intersection", None), ("vote", 2), ("vote", 3)):
        chosen.setdefault(label(large, rule, k), "large ensemble")
    print(f"  large ensemble: {len(large)} detectors, 4 rules")

    print(f"\n{len(chosen)} distinct span sources (full sweep would be 1,743)")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("\n".join(sorted(chosen)) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
