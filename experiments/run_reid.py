#!/usr/bin/env python3
"""A3 and A5 on Enron: can an entity be re-identified from the facts and relations around it?

**Read the split setting before quoting any number from this script.**  With ``--split none`` the
gallery is built from the originals of the very documents the queries come from, so the two sides
differ only in the replaced spans and the attack matches a corpus against itself.  That is train/test
leakage, it inflates Rank-1 enormously, and it is retained only as a labelled upper bound.  The
honest setting is ``--split documents``: the attacker's knowledge and the released corpus come from
disjoint documents, which is what a real adversary faces.

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
import random
import time
from pathlib import Path

from pseudonymkit import NORMALISERS, POLICIES, SURROGATES, TECHNIQUES, Pseudonymiser
from pseudonymkit.adapters import enron
from pseudonymkit.attacks import (
    LearnedLinkage, StructuralLinkage, build_gallery, build_queries, disjoint_document_split,
    truth_map,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--enron", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--stride", type=int, default=25)
    ap.add_argument("--split", choices=("documents", "none", "both"), default="both",
                    help="documents = honest disjoint split; none = leaky upper bound")
    ap.add_argument("--max-queries", type=int, default=20000,
                    help="cap on queries per cell; non-deterministic policies produce one pseudonym "
                         "per entity-document pair, which is ~100k on this sample")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    started = time.time()

    def log(message: str) -> None:
        print(f"[{time.time() - started:6.1f}s] {message}", flush=True)

    corpus = enron.load(args.enron, limit=args.limit, stride=args.stride, progress=log)
    gallery_docs, query_docs = disjoint_document_split(corpus, seed=args.seed)
    log(f"document split: {len(gallery_docs)} gallery / {len(query_docs)} query documents")
    modes = ["documents", "none"] if args.split == "both" else [args.split]
    galleries = {
        "documents": build_gallery(corpus, documents=gallery_docs),
        "none": build_gallery(corpus),
    }
    log(f"galleries: disjoint={len(galleries['documents'])} leaky={len(galleries['none'])}")
    print(f"Enron: {len(corpus)} messages\n", flush=True)

    header = ("split      policy         tech      | attack        | queries gallery | "
              "Rank-1 Rank-5    mAP")
    print(header); print("-" * len(header))
    rows = []
    for policy in ("deterministic", "document", "full"):
        for technique in TECHNIQUES.names():
            engine = Pseudonymiser(
                NORMALISERS.create("N2"), POLICIES.create(policy),
                TECHNIQUES.create(technique), SURROGATES.create("tag"),
            )
            result = engine.pseudonymise_corpus(corpus)
            truth = truth_map(result)
            for mode in modes:
                docs = query_docs if mode == "documents" else None
                queries = build_queries(result, documents=docs)
                if len(queries) > args.max_queries:      # cap, reported in the row
                    rng = random.Random(args.seed)
                    keep = set(rng.sample(sorted(queries), args.max_queries))
                    queries = {k: v for k, v in queries.items() if k in keep}
                log(f"{mode}/{policy}/{technique}: {len(queries)} queries")
                for attack in (StructuralLinkage(), LearnedLinkage(seed=args.seed)):
                    r = attack.run(queries, galleries[mode], truth, policy, technique)
                    row = r.as_dict() | {"split": mode, "corpus": "enron",
                                         "max_queries": args.max_queries}
                    rows.append(row)
                    print(f"{mode:10s} {policy:14s} {technique:9s} | {r.attack:13s} | "
                          f"{r.queries:7d} {r.gallery:7d} | {r.rank1:6.3f} {r.rank5:6.3f} "
                          f"{r.mean_average_precision:6.3f}", flush=True)
        print()

    if args.out:
        args.out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
