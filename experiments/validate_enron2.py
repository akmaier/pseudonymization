#!/usr/bin/env python3
"""Can ENRON 2.0 carry the attack curve? The unmodified-text linkage ceiling, as the sweep computes it.

Plan §4 gives Enron the attack curve because it was the one corpus with cross-document identity at
scale: a 3,697-identity reference population and a 71.98 % A3 ceiling on unmodified text. Both were
measured on the paper-1 corpus, where 66.8 % of query-half messages had a verbatim copy in the
reference half, so some unknown part of that ceiling was the attack finding the copy rather than
the person. This measures the same ceiling on the rebuilt corpus, with the same code path and the
same seed as ``sweep_leakage.py``, so the two numbers are directly comparable.

If the ceiling collapses, the attack curve has nothing to fall from, and that is a result to report
before anything else is run on this corpus — not a reason to change the corpus until it rises.

    . config/env.sh
    python experiments/validate_enron2.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "experiments")

from pseudonymkit.attacks import (
    StructuralLinkage,
    build_gallery,
    build_queries,
    disjoint_document_split,
    truth_map,
)
from pseudonymkit.conditions import Unmodified
from pseudonymkit.domain import Corpus
from pseudonymkit.paths import condition_a_dir
from pseudonymkit.serialisation import iter_documents
from sweep_leakage import relational_identity

T0 = time.time()


def log(message: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {message}", flush=True)


def thread_split(documents, seed: int = 0, fraction: float = 0.5):
    """Like ``disjoint_document_split``, but whole threads go to one side.

    A thread is a folded subject within a mailbox; a message without a subject is its own group.
    Groups are shuffled from their sorted order with the seed and the reference half is filled to
    ``fraction`` of the documents, so the halves stay balanced in documents, not in groups.
    """
    import random
    from collections import defaultdict

    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for d in documents:
        thread = d.metadata.get("thread")
        groups[(d.metadata.get("mailbox"), thread) if thread else ("#", d.doc_id)].append(d.doc_id)
    order = sorted(groups)
    random.Random(seed).shuffle(order)
    target = int(len(documents) * fraction)
    reference: set[str] = set()
    for key in order:
        if len(reference) >= target:
            break
        reference.update(groups[key])
    query = {d.doc_id for d in documents} - reference
    return frozenset(reference), frozenset(query)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus-file", type=Path, default=None,
                    help="default: <condition A dir>/enron2_A.jsonl.gz")
    ap.add_argument("--entity-type", default="PERSON")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--split", choices=["document", "thread"], default="document",
                    help="document: the sweep's own split, by document id. thread: whole threads "
                         "(a subject within a mailbox) kept on one side, because the subject line "
                         "stays in the text (AM, 2026-10-03) and 714 of 2,502 query documents have "
                         "a sibling of their own thread in the reference half under the document split")
    ap.add_argument("--out", type=Path, default=None,
                    help="default: results/enron2/linkage_ceiling_<split>.json")
    args = ap.parse_args()
    out = args.out or Path(f"results/enron2/linkage_ceiling_{args.split}.json")

    path = args.corpus_file or condition_a_dir() / "enron2_A.jsonl.gz"
    documents = list(iter_documents(path))
    corpus = Corpus("enron2", tuple(documents))
    log(f"{path.name}: {len(documents):,} documents")

    if args.split == "document":
        reference, query = disjoint_document_split(corpus, seed=args.seed)
    else:
        reference, query = thread_split(documents, seed=args.seed)
    gallery = build_gallery(corpus, args.entity_type, documents=reference)
    relational, why = relational_identity(corpus, args.entity_type, set(reference), set(query))
    log(f"reference population {len(gallery):,} identities; split {len(reference):,}/{len(query):,}")
    log(f"A3/A5 {'computable' if relational else 'NOT COMPUTABLE'}: {why}")

    result = {"corpus_file": str(path), "documents": len(documents), "seed": args.seed,
              "split": args.split,
              "reference_population": len(gallery), "relational": relational, "why": why}
    if relational:
        ceiling = Unmodified().pseudonymise_corpus(documents)
        queries = build_queries(ceiling, args.entity_type, documents=query)
        truth = truth_map(ceiling, args.entity_type)
        a3 = StructuralLinkage().run(queries, gallery, truth, "deterministic", "hmac")
        chance = 1.0 / max(len(gallery), 1)
        result.update(queries=len(queries), a3_rank1=a3.rank1, chance=chance,
                      lift=a3.rank1 / chance if chance else None)
        log(f"A3 on unmodified text: Rank-1 {a3.rank1:.4f} over {len(queries):,} queries, "
            f"chance {chance:.2e}, lift {a3.rank1 / chance:,.0f}x")
        log("  paper-1 corpus, for reference: Rank-1 0.7198 against 3,697 identities, measured "
            "with 66.8 % of query messages copied verbatim into the reference half")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    log(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
