#!/usr/bin/env python3
"""Run a slice of the factorial on a real corpus and print the results table.

Deliberately small: it wires the library together and prints, so the first end-to-end numbers can
be reproduced from one command.  The Slurm-backed sweep replaces the loop, not the composition.

    python experiments/run_cells.py --tab /path/to/text-anonymization-benchmark
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pseudonymkit import NORMALISERS, POLICIES, SURROGATES, TECHNIQUES, Pseudonymiser
from pseudonymkit.adapters import tab
from pseudonymkit.attacks import FrequencyAttack
from pseudonymkit.inventories import SyntheticInventory
from pseudonymkit.metrics import evaluate_stability


def cell(corpus, normaliser: str, policy: str, technique: str, surrogate: str) -> dict:
    kwargs = {} if surrogate == "tag" else {"inventory": SyntheticInventory(pool_size=1 << 16)}
    engine = Pseudonymiser(
        NORMALISERS.create(normaliser),
        POLICIES.create(policy),
        TECHNIQUES.create(technique),
        SURROGATES.create(surrogate, **kwargs),
    )
    result = engine.pseudonymise_corpus(corpus)
    row: dict[str, object] = {
        "normaliser": normaliser, "policy": policy, "technique": technique, "surrogate": surrogate,
    }
    for entity_type in ("PERSON", "LOC"):
        stab = evaluate_stability(result, entity_type, policy)
        atk = FrequencyAttack().run(result, entity_type, policy, technique)
        row[f"{entity_type}_chains"] = stab.chains
        row[f"{entity_type}_frag"] = round(stab.fragmentation_rate, 4)
        row[f"{entity_type}_coll"] = round(stab.collision_rate, 4)
        row[f"{entity_type}_a2_top1"] = round(atk.accuracy_top1, 4)
        row[f"{entity_type}_a2_rho"] = (
            None if atk.rank_correlation is None else round(atk.rank_correlation, 4)
        )
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tab", required=True, type=Path, help="TAB repository checkout")
    ap.add_argument("--splits", nargs="+", default=["train", "dev", "test"])
    ap.add_argument("--out", type=Path, help="write rows as JSON lines")
    args = ap.parse_args()

    corpus = tab.load(args.tab, splits=args.splits, types=["PERSON", "LOC"])
    mentions = sum(len(d.mentions) for d in corpus)
    print(f"TAB: {len(corpus)} documents, {mentions} PERSON/LOC mentions (annotator=first)\n")

    header = ("norm pol            tech      | PERSON: chains  frag  coll  A2@1   rho "
              "| LOC: chains  frag  coll  A2@1   rho")
    print(header)
    print("-" * len(header))

    rows = []
    for normaliser in ("N0", "N2", "N4"):
        for policy in ("deterministic", "document", "full"):
            for technique in TECHNIQUES.names():
                r = cell(corpus, normaliser, policy, technique, "tag")
                rows.append(r)
                print(
                    f"{normaliser:4s} {policy:14s} {technique:9s} |"
                    f" {r['PERSON_chains']:13d} {r['PERSON_frag']:.3f} {r['PERSON_coll']:.3f}"
                    f" {r['PERSON_a2_top1']:.3f} {str(r['PERSON_a2_rho']):>5s} |"
                    f" {r['LOC_chains']:10d} {r['LOC_frag']:.3f} {r['LOC_coll']:.3f}"
                    f" {r['LOC_a2_top1']:.3f} {str(r['LOC_a2_rho']):>5s}"
                )
        print()

    if args.out:
        args.out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
