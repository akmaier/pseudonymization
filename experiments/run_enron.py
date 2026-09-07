#!/usr/bin/env python3
"""Test the prediction the TAB run produced: does frequency skew convert into identification?

TAB gave Spearman rho = 1.000 under a deterministic policy and A2 top-1 of only 1.3 %, because its
entity-frequency distribution is nearly flat -- most people are named once or twice inside a single
judgment, and rank alignment inside a tie block that large is arbitrary.

Enron is the opposite shape: the same people recur across thousands of messages.  If the reading is
right, rho stays at 1.000 and top-1 rises sharply.  If top-1 stays low here too, the reading is
wrong and A2 is weaker than H1 supposes.

    python experiments/run_enron.py --enron <tarball-or-maildir> --limit 20000 --stride 25
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from pseudonymkit import NORMALISERS, POLICIES, SURROGATES, TECHNIQUES, Pseudonymiser
from pseudonymkit.adapters import enron
from pseudonymkit.attacks import FrequencyAttack
from pseudonymkit.metrics import evaluate_stability


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--enron", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--stride", type=int, default=25)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    corpus = enron.load(args.enron, limit=args.limit, stride=args.stride)
    mentions = sum(len(d.mentions) for d in corpus)
    people = Counter(
        m.gold_entity_id for d in corpus for m in d.mentions if m.type == "PERSON"
    )
    print(f"Enron: {len(corpus)} messages, {mentions} mentions, {len(people)} distinct people")
    if people:
        top = people.most_common(5)
        print("  most frequent entities:", ", ".join(f"{v}" for _, v in top))
        singles = sum(1 for v in people.values() if v == 1)
        print(f"  entities mentioned once: {singles}/{len(people)} = {singles / len(people):.1%}")
    print()

    header = "policy         tech      | people  frag   coll   drift  | A2@1   A2@5   rho"
    print(header)
    print("-" * len(header))
    rows = []
    for policy in ("deterministic", "document", "full"):
        for technique in TECHNIQUES.names():
            engine = Pseudonymiser(
                NORMALISERS.create("N2"),
                POLICIES.create(policy),
                TECHNIQUES.create(technique),
                SURROGATES.create("tag"),
            )
            result = engine.pseudonymise_corpus(corpus)
            stab = evaluate_stability(result, "PERSON", policy, cross_document=True)
            atk = FrequencyAttack().run(result, "PERSON", policy, technique)
            rho = "None" if atk.rank_correlation is None else f"{atk.rank_correlation:.3f}"
            print(
                f"{policy:14s} {technique:9s} | {stab.chains:6d} {stab.fragmentation_rate:.3f} "
                f"{stab.collision_rate:.3f} {stab.drift_rate:.3f} | "
                f"{atk.accuracy_top1:.3f} {atk.accuracy_top5:.3f} {rho:>6s}"
            )
            row = {"corpus": "enron", "policy": policy, "technique": technique, **atk.as_dict(),
                   **{f"stab_{k}": v for k, v in stab.as_dict().items()}}
            rows.append(row)
            if policy == "deterministic" and technique == "hmac" and atk.by_frequency_band:
                bands = ", ".join(f"{k}={v:.3f}" for k, v in atk.by_frequency_band.items())
                print(f"     A2 top-1 by mention-frequency band: {bands}")
        print()

    if args.out:
        args.out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
