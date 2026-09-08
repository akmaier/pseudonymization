#!/usr/bin/env python3
"""A3 and A5 on Enron: can an entity be re-identified from the facts and relations around it?

Pseudonymisation replaces the name and leaves the profile.  A3 compares profiles with a fixed
cosine; A5 learns the metric on entities it never sees again.  The gap between them is what learning
buys the adversary.

Prediction under test: strong under a deterministic policy, weaker under document-randomised,
failing under fully-randomised, and flat across all five techniques.

    python experiments/run_reid.py --enron <tarball> --limit 20000 --stride 25
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pseudonymkit import NORMALISERS, POLICIES, SURROGATES, TECHNIQUES, Pseudonymiser
from pseudonymkit.adapters import enron
from pseudonymkit.attacks import (
    LearnedLinkage, StructuralLinkage, build_gallery, build_queries, truth_map,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--enron", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--stride", type=int, default=25)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    corpus = enron.load(args.enron, limit=args.limit, stride=args.stride)
    gallery = build_gallery(corpus)
    print(f"Enron: {len(corpus)} messages | gallery: {len(gallery)} entities\n")

    header = "policy         tech      | attack        | queries gallery | Rank-1 Rank-5    mAP"
    print(header); print("-" * len(header))
    rows = []
    for policy in ("deterministic", "document", "full"):
        for technique in TECHNIQUES.names():
            engine = Pseudonymiser(
                NORMALISERS.create("N2"), POLICIES.create(policy),
                TECHNIQUES.create(technique), SURROGATES.create("tag"),
            )
            result = engine.pseudonymise_corpus(corpus)
            queries, truth = build_queries(result), truth_map(result)
            for attack in (StructuralLinkage(), LearnedLinkage(seed=0)):
                r = attack.run(queries, gallery, truth, policy, technique)
                rows.append(r.as_dict())
                print(f"{policy:14s} {technique:9s} | {r.attack:13s} | {r.queries:7d} "
                      f"{r.gallery:7d} | {r.rank1:6.3f} {r.rank5:6.3f} {r.mean_average_precision:6.3f}")
        print()

    if args.out:
        args.out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
