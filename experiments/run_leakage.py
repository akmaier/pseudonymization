#!/usr/bin/env python3
"""§8.4 leakage over the conditions as built, not as rebuilt in memory.

``run_reid.py`` sweeps policy x technique on Enron by constructing conditions on the fly.  This runs
the study's actual conditions — A, and the B and C on disk — so the leakage numbers belong to the
same artefacts the utility numbers do.

    . config/env.sh
    python experiments/run_leakage.py --corpus cardiode --rule union

What runs where, from §8.4:

* **A2** frequency alignment — **condition B only**.  On C every identifier of a type is one string,
  so there is no distribution to align.  Both reference settings are reported: the corpus's own name
  distribution, which is the upper bound, and an external one where a gazetteer is given.
* **A3** structural linkage and **A5** learned linkage — **A, B and C**.  A is the ceiling: what the
  adversary recovers with nothing replaced.  Without it a rate on B or C has no scale.
* **A4** LLM ranked-candidate re-identification — **A, B and C**, and run with and without
  auxiliary context, as §8.4 requires. It is **opt-in** (``--attacks a4``) because it is the only
  attack here that costs model time: one gateway call per query per arm. It is also the one attack
  CARDIO:DE can carry in full, because it needs a *candidate list* rather than cross-document
  identity — ``build_items`` draws distractors from the corpus itself, which is what §8.4 and §15
  require, and a letter-scoped patient still has 399 other letters to be confused with.

Two disjointness requirements, both enforced rather than assumed:

* **document-disjoint** gallery and query for A3 and A5 — violating it matches a corpus against
  itself and inflated Rank-1 by 0.29 in the first run;
* **entity-disjoint** train and test for A5, here as **five-fold cross-validation** (AM, 2026-09-15),
  so every entity is tested exactly once and the five results can be averaged.
"""

from __future__ import annotations

import argparse
import json
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
from pseudonymkit.construction import (
    check_current,
    read_patchset,
    to_pseudonymised_corpus,
)
from pseudonymkit.domain import Corpus
from pseudonymkit.paths import cardiode_a, cardiode_conditions, condition_a_dir, work_dir
from pseudonymkit.serialisation import iter_documents

SOURCES = {
    "cardiode": (cardiode_a, cardiode_conditions),
    "tab": (lambda: condition_a_dir() / "tab_A.jsonl.gz", lambda: work_dir() / "results/conditions"),
    "ontonotes": (lambda: condition_a_dir() / "ontonotes_A.jsonl.gz",
                  lambda: work_dir() / "results/conditions"),
    "enron": (lambda: condition_a_dir() / "enron_A.jsonl.gz",
              lambda: work_dir() / "results/conditions"),
}


def log(message: str, t0: float = time.time()) -> None:
    print(f"[{time.time() - t0:7.1f}s] {message}", flush=True)


def _run_a4(result, corpus, condition: str, args, stamp: dict, log) -> list[dict]:
    """A4 over one condition, both context arms.

    §8.4: *"Run with and without that auxiliary context, and stratified by public-figure status."*
    The stratification has code but **no corpus in the study carries the annotation**, so it is
    reported as absent rather than silently omitted.
    """
    from pseudonymkit.attacks import LlmCandidateRanker, build_items, score_candidates

    out: list[dict] = []
    for with_context in (False, True):
        items = build_items(
            result, corpus, entity_type=args.entity_type,
            n_candidates=args.a4_candidates, seed=args.seed, with_context=with_context,
        )
        if args.a4_limit:
            items = items[: args.a4_limit]
        if not items:
            log(f"  A4/{condition} context={with_context}: no queries — SKIPPED")
            continue
        ranker = LlmCandidateRanker(model=args.a4_model, config_path=str(args.config))
        report = score_candidates(items, ranker, condition=condition)
        # to_record(), not as_dict(): A4Report deliberately emits aggregate rates only, carrying no
        # candidate surface, no document text and no identity, because §15.1 forbids a real name
        # from the corpus appearing in any released artefact.
        row = report.to_record() | stamp | {"model": args.a4_model, "queries": len(items)}
        out.append(row)
        o = report.overall
        log(f"  A4/{condition} context={str(with_context):<5}: "
            f"Rank-1 {o.rank1:.3f} Rank-5 {o.rank5:.3f} "
            f"mAP {o.mean_average_precision:.3f} over {len(items)} queries")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(SOURCES))
    ap.add_argument("--rule", default="union")
    ap.add_argument("--entity-type", default="PERSON")
    ap.add_argument("--folds", type=int, default=5, help="A5 cross-validation folds")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--attacks", nargs="+", default=["a2", "a3", "a5"],
                    choices=["a2", "a3", "a4", "a5"],
                    help="a4 costs one gateway call per query per arm, so it is opt-in")
    ap.add_argument("--a4-candidates", type=int, default=10,
                    help="candidates per query, the true identity included")
    ap.add_argument("--a4-model", default="gpt-oss-120b")
    ap.add_argument("--a4-limit", type=int, default=0, help="cap queries per condition per arm")
    ap.add_argument("--config", type=Path, default=Path("config/llm_api.toml"))
    ap.add_argument("--out", type=Path, default=Path("results/leakage"))
    args = ap.parse_args()

    documents = list(iter_documents(SOURCES[args.corpus][0]()))
    if args.limit:
        documents = documents[: args.limit]
    corpus = Corpus(args.corpus, tuple(documents))
    log(f"{args.corpus}: {len(documents)} documents, entity type {args.entity_type}")

    gallery_docs, query_docs = disjoint_document_split(corpus, seed=args.seed)
    log(f"  document-disjoint split: {len(gallery_docs)} gallery / {len(query_docs)} query")
    gallery = build_gallery(corpus, args.entity_type, documents=gallery_docs)
    log(f"  gallery: {len(gallery)} entity profiles")

    conditions = {"A": Unmodified().pseudonymise_corpus(documents)}
    root = SOURCES[args.corpus][1]()
    for condition in ("B", "C"):
        found = sorted(root.glob(f"{args.corpus}_{condition}_{args.rule}*.patch.jsonl"))
        if not found:
            log(f"  {condition}: no patch set for rule {args.rule!r} — SKIPPED")
            continue
        patchset = read_patchset(found[0])
        # Verified before any attack runs: a patch set built against a rebuilt condition A scores a
        # corpus that no longer exists, and every rate it produces is wrong without looking wrong.
        check = check_current(documents, patchset)
        conditions[condition] = to_pseudonymised_corpus(documents, patchset)
        log(f"  {condition}: {found[0].name}, text digests verified ({check['patches']} patches)")

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"{args.corpus}_{args.rule}_{args.entity_type}.jsonl"
    rows: list[dict] = []

    for condition, result in conditions.items():
        stamp = {"corpus": args.corpus, "rule": args.rule, "condition": condition,
                 "entity_type": args.entity_type, "seed": args.seed}

        if "a4" in args.attacks:
            rows.extend(_run_a4(result, corpus, condition, args, stamp, log))

        if condition == "B" and "a2" in args.attacks:
            r = FrequencyAttack().run(result, args.entity_type, "deterministic", "hmac")
            rows.append(r.as_dict() | stamp | {"attack": "a2_frequency"})
            bands = " ".join(f"{k}:{v:.2f}" for k, v in sorted(r.by_frequency_band.items()))
            log(f"  A2/{condition}: top-1 {r.accuracy_top1:.3f} top-5 {r.accuracy_top5:.3f} "
                f"rho {r.rank_correlation:.3f} over {r.candidates} pseudonyms | bands {bands}")

        if not ({"a3", "a5"} & set(args.attacks)):
            continue
        queries = build_queries(result, args.entity_type, documents=query_docs)
        truth = truth_map(result, args.entity_type)
        if not queries or not truth:
            log(f"  {condition}: no queries or no truth for {args.entity_type} — A3/A5 SKIPPED")
            continue
        log(f"  {condition}: {len(queries)} queries, {len(truth)} truth pairs")

        if "a3" in args.attacks:
            r = StructuralLinkage().run(queries, gallery, truth, "deterministic", "hmac")
            rows.append(r.as_dict() | stamp | {"attack": "a3_structural", "fold": None})
            log(f"  A3/{condition}: Rank-1 {r.rank1:.3f} Rank-5 {r.rank5:.3f} "
                f"mAP {r.mean_average_precision:.3f}")

        # A5, five-fold. Every entity is tested exactly once across the folds, so the five results
        # are averaged rather than pooled — and the spread is reported, because a single split's
        # Rank-1 on a few hundred entities is not a stable number.
        fold_rows = []
        for fold in (range(args.folds) if "a5" in args.attacks else ()):
            attack = LearnedLinkage(seed=args.seed, folds=args.folds, fold=fold)
            r = attack.run(queries, gallery, truth, "deterministic", "hmac")
            row = r.as_dict() | stamp | {"attack": "a5_learned", "fold": fold,
                                         "folds": args.folds}
            rows.append(row)
            fold_rows.append(r)
        if fold_rows:
            for metric in ("rank1", "rank5", "mean_average_precision"):
                values = [getattr(r, metric) for r in fold_rows]
                rows.append(stamp | {
                    "attack": "a5_learned", "fold": "mean", "folds": args.folds,
                    "metric": metric, "mean": statistics.fmean(values),
                    "sd": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "values": values,
                })
            means = {m: statistics.fmean([getattr(r, m) for r in fold_rows])
                     for m in ("rank1", "rank5", "mean_average_precision")}
            sd1 = statistics.stdev([r.rank1 for r in fold_rows]) if len(fold_rows) > 1 else 0.0
            log(f"  A5/{condition}: Rank-1 {means['rank1']:.3f} (sd {sd1:.3f}) "
                f"Rank-5 {means['rank5']:.3f} mAP {means['mean_average_precision']:.3f} "
                f"over {args.folds} folds")

    # **Merge, do not overwrite.** The attacks are selectable, so a run with --attacks a4 used to
    # rewrite the file with only its own rows and destroyed the A2/A3/A5 results already there.
    # Rows whose attack this run produced are replaced; every other row is kept.
    produced = {r["attack"] for r in rows}
    kept: list[dict] = []
    if destination.exists():
        for line in destination.open(encoding="utf-8"):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("attack") not in produced:
                kept.append(row)
    destination.write_text(
        "\n".join(json.dumps(r) for r in kept + rows) + "\n", encoding="utf-8"
    )
    log(f"wrote {len(rows)} rows ({len(kept)} earlier rows kept) to {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
