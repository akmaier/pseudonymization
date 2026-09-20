#!/usr/bin/env python3
"""Leakage recomputed at every recall level — H1 and H5 (§6).

§6 does not ask for leakage under one ensemble.  **H1** is *"comparing every detector and every
combination rule against the gold-span oracle, with leakage recomputed at each recall level"*, and
**H5** is *"comparing every LLMs-only subset against the same subset plus one classical detector"*.
Both are statements about the *ensemble axis*, and neither is answerable from a single union run.

This is affordable where a utility sweep is not.  Utility re-runs frozen models over every
conditioned text; leakage is set arithmetic, a cosine and a small numpy fit.  So condition B is
constructed **in memory** for each span source, attacked, and thrown away — 2,151 patch sets would
be 50 GB on disk and are not worth keeping when the rates are what the paper reports.

Each row carries the detection numbers **and** the leakage numbers for the same span source, which is
what makes "leakage at each recall level" a single table rather than a join across two files.

    . config/env.sh
    python experiments/sweep_leakage.py --corpus cardiode --max-size 3

Rows land in ``results/leakage_sweep/<corpus>.jsonl``, one per (span source, rule), resumable.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import statistics
import sys
import time
from pathlib import Path

from pseudonymkit.attacks import (
    FrequencyAttack,
    LearnedLinkage,
    StructuralLinkage,
    build_gallery,
    build_queries,
    disjoint_document_split,
    truth_map,
)
from pseudonymkit.conditions import Unmodified
from pseudonymkit.construction import construct, detected_documents, to_pseudonymised_corpus
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.domain import Corpus
from pseudonymkit.metrics.detection import prepare, score_prepared
from pseudonymkit.paths import cardiode_a, condition_a_dir
from pseudonymkit.serialisation import iter_documents

CORPORA = {
    "cardiode": cardiode_a,
    "tab": lambda: condition_a_dir() / "tab_A.jsonl.gz",
    "ontonotes": lambda: condition_a_dir() / "ontonotes_A.jsonl.gz",
    "enron": lambda: condition_a_dir() / "enron_A.jsonl.gz",
}

CLASSICAL = ("presidio", "privacy_tagger", "gliner:", "hf:")
"""Prefixes of the non-LLM levels of axis D.  H5 asks what adding one of these to an LLMs-only
subset buys, so the two families have to be distinguishable by name."""

RULES: tuple[tuple[str, dict], ...] = (
    ("union", {}), ("intersection", {}), ("vote", {"k": 2}), ("vote", {"k": 3}),
)


def log(message: str, t0: float = time.time()) -> None:
    print(f"[{time.time() - t0:8.1f}s] {message}", flush=True)


def is_llm(name: str) -> bool:
    return name.startswith("llm:")


def relational_identity(corpus, entity_type, gallery_docs, query_docs) -> tuple[bool, str]:
    """Whether A3 and A5 have a denominator on this corpus, and why.

    Both attacks link a query mention to a *profile of the same person built from other documents*.
    That needs an identity the corpus asserts across documents.  Enron has one — the e-mail address —
    and CARDIO:DE has one because §12.1 constructs recurring patients and a recurring physician pool.

    TAB and OntoNotes do not.  Their co-reference is document-scoped by construction: every gold
    entity id is prefixed with the document it came from, so **no entity appears in two documents**
    (checked: 0 of 8,701 in TAB, 0 of 13,230 in OntoNotes).  After
    :func:`disjoint_document_split`, no query's true identity is in the gallery at all.

    Run anyway, the attacks return Rank-1 = 0 for every span source *and for condition A*, and a
    reader of that table would conclude that pseudonymisation defeats structural linkage on TAB.  It
    does not; the attack was never possible.  §2 says report faithfully, so this returns the reason
    and the caller writes ``null`` with the reason attached rather than a zero that means something
    else.  :mod:`experiments/run_stability` gives drift the same treatment for the same reason.
    """
    gallery_ids, query_ids = set(), set()
    for doc in corpus:
        if doc.doc_id in gallery_docs:
            target = gallery_ids
        elif doc.doc_id in query_docs:
            target = query_ids
        else:
            continue
        target.update(m.gold_entity_id for m in doc.mentions
                      if m.type == entity_type and m.gold_entity_id)
    shared = gallery_ids & query_ids
    if shared:
        return True, (f"{len(shared)} {entity_type} identities appear on both sides of the "
                      f"document-disjoint split")
    return False, (f"no {entity_type} identity appears in both the gallery and the query half of "
                   f"the document-disjoint split ({len(gallery_ids)} and {len(query_ids)} "
                   f"identities, 0 shared) — co-reference in this corpus is document-scoped, so a "
                   f"cross-document linkage attack has no true match to find")


def subsets(detectors: list[str], max_size: int):
    for size in range(1, max_size + 1):
        yield from itertools.combinations(detectors, size)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(CORPORA))
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--out", type=Path, default=Path("results/leakage_sweep"))
    ap.add_argument("--max-size", type=int, default=3)
    ap.add_argument("--entity-type", default="PERSON")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--key-file", type=Path,
                    default=Path.home() / ".config" / "pseudonymkit" / "hmac.key")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min-coverage", type=float, default=0.99,
                    help="skip a span source whose members jointly cover less than this fraction "
                         "of the corpus, rather than attacking a condition built by a different "
                         "operator on part of it")
    ap.add_argument("--restart", action="store_true")
    args = ap.parse_args()

    sys.path.insert(0, "experiments")
    from build_BC import inventory_for, read_key

    documents = list(iter_documents(CORPORA[args.corpus]()))
    if args.limit:
        documents = documents[: args.limit]
    corpus = Corpus(args.corpus, tuple(documents))
    key = read_key(args.key_file)
    log(f"{args.corpus}: {len(documents)} documents, entity type {args.entity_type}")

    inventory, _ = inventory_for({d.language for d in documents}, documents=documents)
    index = prepare(documents, corpus=args.corpus)
    gallery_docs, query_docs = disjoint_document_split(corpus, seed=args.seed)
    gallery = build_gallery(corpus, args.entity_type, documents=gallery_docs)
    log(f"  gallery {len(gallery)} profiles; document-disjoint split "
        f"{len(gallery_docs)}/{len(query_docs)}")

    relational, why = relational_identity(corpus, args.entity_type, set(gallery_docs),
                                          set(query_docs))
    log(f"  A3/A5 {'computable' if relational else 'NOT COMPUTABLE'}: {why}")

    # Condition A once: the ceiling every row is read against (§8.4).
    a3_ceiling_rank1 = None
    if relational:
        ceiling = Unmodified().pseudonymise_corpus(documents)
        a_queries = build_queries(ceiling, args.entity_type, documents=query_docs)
        a_truth = truth_map(ceiling, args.entity_type)
        a3_ceiling = StructuralLinkage().run(a_queries, gallery, a_truth, "deterministic", "hmac")
        a3_ceiling_rank1 = a3_ceiling.rank1
        log(f"  ceiling A3 on condition A: Rank-1 {a3_ceiling.rank1:.3f}")
    else:
        log("  skipping the condition-A ceiling: it would be 0 for the same structural reason, "
            "which is not a measurement of anything")

    cache = DetectorCache(args.cache, args.corpus)
    detectors = sorted(p.stem.replace("__", "/") for p in cache.root.glob("*.jsonl"))
    log(f"  detectors {len(detectors)} ({sum(1 for d in detectors if is_llm(d))} LLM)")

    # **The same coverage floor the detection sweep uses, for the same reason.** A subset is scored
    # over the documents its members jointly cover; where a member has no record the combinator
    # silently drops it, so `vote(k=2)` over the two present out of three becomes an intersection
    # and the row is labelled with an ensemble it was not measured with. On Enron that would be
    # every subset containing Qwen3.6, which is still detecting.
    covered = {name: set(cache.digests(name)) for name in detectors}
    for name, ids in sorted(covered.items()):
        if len(ids) < len(documents):
            log(f"    PARTIAL {name}: {len(ids)}/{len(documents)} documents "
                f"({len(ids) / max(len(documents), 1):.1%})")

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"{args.corpus}_{args.entity_type}.jsonl"
    done: set[str] = set()
    if destination.exists() and not args.restart:
        for line in destination.open(encoding="utf-8"):
            try:
                done.add(json.loads(line)["source"])
            except Exception:
                continue
        log(f"  resuming: {len(done)} span sources already done")

    written = 0
    skipped: list[tuple[str, int]] = []
    started = time.time()
    with destination.open("a" if done else "w", encoding="utf-8", buffering=1) as handle:
        for names in subsets(detectors, args.max_size):
            for rule, kwargs in RULES:
                k = kwargs.get("k")
                if len(names) == 1 and rule != "union":
                    continue
                if k is not None and k > len(names):
                    continue
                label = f"{'+'.join(names)}|{rule}{k or ''}"
                if label in done:
                    continue
                shared = set.intersection(*(covered[n] for n in names))
                fraction = len(shared) / max(len(documents), 1)
                if fraction < args.min_coverage:
                    skipped.append((label, len(shared)))
                    continue
                try:
                    row = _one(names, rule, kwargs, label, documents, cache, index, inventory,
                               key, gallery, query_docs, args, relational)
                except Exception as exc:          # recorded, never silently skipped (§1)
                    row = {"source": label, "error": f"{type(exc).__name__}: {exc}"}
                row.update(corpus=args.corpus, entity_type=args.entity_type, size=len(names),
                           rule=rule if len(names) > 1 else "single", k=k,
                           ensemble=list(names),
                           llms_only=all(is_llm(n) for n in names),
                           classical=[n for n in names if not is_llm(n)],
                           a3_ceiling_rank1=a3_ceiling_rank1,
                           relational_computable=relational,
                           relational_note=None if relational else why)
                handle.write(json.dumps(row) + "\n")
                os.fsync(handle.fileno())
                written += 1
                if written % 20 == 0:
                    rate = written / max(time.time() - started, 1e-9)
                    log(f"  {written} sources  {rate * 3600:.0f}/h")
    log(f"wrote {written} rows to {destination}")
    if skipped:
        log(f"  SKIPPED {len(skipped)} span sources below --min-coverage {args.min_coverage}:")
        for label, n in skipped[:10]:
            log(f"    {label}  {n}/{len(documents)} documents shared")
        if len(skipped) > 10:
            log(f"    ... and {len(skipped) - 10} more")
        log("  not dropped cells: finish detection for the members above and re-run; the resume "
            "adds exactly these rows (§1).")
    return 0


def _one(names, rule, kwargs, label, documents, cache, index, inventory, key,
         gallery, query_docs, args, relational: bool) -> dict:
    """Detection and leakage for one span source, condition B built and discarded in memory."""
    detected, report = detected_documents(
        documents, cache, list(names), rule=rule, rule_kwargs=kwargs
    )
    spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}
    detection = score_prepared(index, spans, detector=label).as_dict()

    patches = construct(detected, corpus=args.corpus, conditions=("B",),
                        inventory=inventory, key=key)
    # **The gold-bearing documents, not the detected ones.** `detected` carries the detector's spans
    # as its mentions, so it has no gold_entity_id to inherit and A3/A5 come back with no truth at
    # all — which is what the first run of this sweep produced. The patch offsets address condition-A
    # text either way, so the originals are the right thing to rebuild against.
    result = to_pseudonymised_corpus(documents, patches["B"], check=False)

    row = {
        "source": label,
        "token_recall": detection["token_recall"],
        "entity_recall": detection["entity_recall"],
        "precision": detection["precision"],
        "information_weighted_precision": detection["information_weighted_precision"],
        "replacements": sum(len(p.entries) for p in patches["B"].patches),
        "documents_missing_a_detector": report.get("documents_missing_a_detector"),
    }

    a2 = FrequencyAttack().run(result, args.entity_type, "deterministic", "hmac")
    row.update(a2_top1=a2.accuracy_top1, a2_top5=a2.accuracy_top5, a2_rho=a2.rank_correlation,
               a2_candidates=a2.candidates, a2_bands=dict(a2.by_frequency_band))

    queries = build_queries(result, args.entity_type, documents=query_docs)
    truth = truth_map(result, args.entity_type)
    # `relational` is a property of the corpus, not of this span source: where co-reference is
    # document-scoped the gallery and the queries share no identity, so A3 and A5 would report zero
    # for every row including the condition-A ceiling.  The fields are left absent rather than set
    # to a zero that would read as "the attack failed".
    if relational and queries and truth:
        a3 = StructuralLinkage().run(queries, gallery, truth, "deterministic", "hmac")
        row.update(a3_rank1=a3.rank1, a3_rank5=a3.rank5, a3_map=a3.mean_average_precision,
                   a3_queries=a3.queries)
        folds = [
            LearnedLinkage(seed=args.seed, folds=args.folds, fold=f).run(
                queries, gallery, truth, "deterministic", "hmac")
            for f in range(args.folds)
        ]
        row.update(
            a5_rank1=statistics.fmean([f.rank1 for f in folds]),
            a5_rank1_sd=statistics.stdev([f.rank1 for f in folds]) if len(folds) > 1 else 0.0,
            a5_rank5=statistics.fmean([f.rank5 for f in folds]),
            a5_map=statistics.fmean([f.mean_average_precision for f in folds]),
            a5_folds=args.folds,
        )
    return row


if __name__ == "__main__":
    sys.exit(main())
