#!/usr/bin/env python3
"""How much of paper 1's Enron linkage was the attack finding copies of the query message?

Measured 2026-10-03: 84.9 % of the paper-1 Enron messages share their body with another message (Lotus
Notes files one mail under several folders), and the A3/A5 split is by document id, so 66.8 % of the
query-half messages have a verbatim copy in the reference half. ``disjoint_document_split``'s own
docstring states the rule this breaks: if the context around an entity is identical on both sides,
"the attack measures nothing but the fact that a corpus matches itself".

This reruns paper 1's three Enron linkage numbers on the paper-1 corpus, with the code path and seed
the leakage sweep used, under two splits that differ in exactly one thing:

* ``document`` — the sweep's split, by document id (paper 1's numbers);
* ``body``     — the same procedure, but every group of messages with an identical body is kept on
                 one side, so no query message has a verbatim copy among the reference documents.

and reports, for each:

* the A3 ceiling on unmodified text (paper 1: 0.7198),
* A3 and A5 on the recommended 13-detector union's release, as fold means (paper 1: 0.0093 and
  0.0394).

It changes nothing in paper 1 and writes one result file. Enron is public; no names are printed.

    . config/env.sh
    sbatch ... --wrap "python experiments/duplicate_leak.py"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "experiments")

from pseudonymkit.attacks import (
    LearnedLinkage,
    StructuralLinkage,
    build_gallery,
    build_queries,
    disjoint_document_split,
    truth_map,
)
from pseudonymkit.conditions import Unmodified
from pseudonymkit.construction import read_patchset, to_pseudonymised_corpus
from pseudonymkit.domain import Corpus
from pseudonymkit.paths import condition_a_dir, work_dir
from pseudonymkit.serialisation import iter_documents

T0 = time.time()
TAG = "union-single0.5-13det-1797ba"


def log(message: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {message}", flush=True)


def body_of(text: str) -> str:
    cut = text.find("\n\n")
    return text[cut + 2:] if cut >= 0 else text


def body_split(documents, seed: int = 0, fraction: float = 0.5):
    """``disjoint_document_split``, but messages with one body stay together on one side."""
    groups: dict[str, list[str]] = defaultdict(list)
    for d in documents:
        groups[hashlib.sha1(" ".join(body_of(d.text).split()).encode("utf-8")).hexdigest()].append(
            d.doc_id)
    order = sorted(groups)
    random.Random(seed).shuffle(order)
    target = int(len(documents) * fraction)
    reference: set[str] = set()
    for key in order:
        if len(reference) >= target:
            break
        reference.update(groups[key])
    return frozenset(reference), frozenset(d.doc_id for d in documents) - frozenset(reference)


def linkage(corpus, documents, released, reference, query, entity_type, seed, folds):
    gallery = build_gallery(corpus, entity_type, documents=reference)
    out = {"reference_documents": len(reference), "query_documents": len(query),
           "reference_population": len(gallery)}
    ceiling = Unmodified().pseudonymise_corpus(documents)
    q = build_queries(ceiling, entity_type, documents=query)
    a3 = StructuralLinkage().run(q, gallery, truth_map(ceiling, entity_type),
                                 "deterministic", "hmac")
    out.update(a3_ceiling_rank1=a3.rank1, ceiling_queries=len(q))
    queries = build_queries(released, entity_type, documents=query)
    truth = truth_map(released, entity_type)
    structural = StructuralLinkage()
    partition = structural.folds(queries, gallery, truth, seed=seed, folds=folds)
    a3_folds = [structural.run(queries, gallery, truth, "deterministic", "hmac", subset=keys).rank1
                for keys in partition]
    a5_folds = [LearnedLinkage(seed=seed, folds=folds, fold=f).run(
        queries, gallery, truth, "deterministic", "hmac").rank1 for f in range(folds)]
    out.update(release_queries=len(queries),
               a3_rank1_mean=statistics.mean(a3_folds), a3_rank1_sd=statistics.stdev(a3_folds),
               a5_rank1_mean=statistics.mean(a5_folds), a5_rank1_sd=statistics.stdev(a5_folds))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entity-type", default="PERSON")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--out", type=Path, default=Path("results/detection/duplicate_leak_enron.json"))
    args = ap.parse_args()

    documents = list(iter_documents(condition_a_dir() / "enron_A.jsonl.gz"))
    corpus = Corpus("enron", tuple(documents))
    patchset = read_patchset(work_dir() / "results/conditions" / f"enron_B_{TAG}.patch.jsonl")
    released = to_pseudonymised_corpus(documents, patchset, check=False)
    log(f"paper-1 Enron: {len(documents):,} documents; release {TAG}")

    result = {"corpus": "enron (paper 1)", "tag": TAG, "seed": args.seed, "folds": args.folds,
              "paper_1": {"a3_ceiling_rank1": 0.7198, "a3_rank1": 0.0093, "a5_rank1": 0.0394}}
    for name, split in (("document", lambda: disjoint_document_split(corpus, seed=args.seed)),
                        ("body", lambda: body_split(documents, seed=args.seed))):
        reference, query = split()
        bodies = {hashlib.sha1(" ".join(body_of(d.text).split()).encode()).hexdigest()
                  for d in documents if d.doc_id in reference}
        copies = sum(1 for d in documents if d.doc_id in query and
                     hashlib.sha1(" ".join(body_of(d.text).split()).encode()).hexdigest() in bodies)
        row = linkage(corpus, documents, released, reference, query, args.entity_type, args.seed,
                      args.folds)
        row["query_documents_with_a_verbatim_copy_in_the_reference_half"] = copies
        result[name] = row
        log(f"{name:8s} split: copies {copies:,}; A3 ceiling {row['a3_ceiling_rank1']:.4f}; "
            f"A3 {row['a3_rank1_mean']:.4f} ± {row['a3_rank1_sd']:.4f}; "
            f"A5 {row['a5_rank1_mean']:.4f} ± {row['a5_rank1_sd']:.4f}; "
            f"reference population {row['reference_population']:,}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    log(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
