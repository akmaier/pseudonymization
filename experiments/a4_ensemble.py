#!/usr/bin/env python3
"""A4 against a named condition build, so the attack and the leakage tables share one ensemble.

``run_leakage.py`` resolves its patch set with ``sorted(glob(...))[0]``, which picked the
15-detector union while Tables 2 and 3 report the recommended 13-detector one (AM, 2026-09-25:
*"A4 needs to run on the recommended 13"*).  The tag is therefore explicit here and is recorded in
every row, so a result can never again be read against an ensemble it was not produced on.

Condition A is unmodified text and does not depend on the detector set, so it is not re-run; the
existing ceiling applies unchanged.

    .venv/bin/python experiments/a4_ensemble.py --corpus tab --tag union-single0.5-13det-abc123
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from pseudonymkit.attacks import LlmCandidateRanker, build_items, score_candidates
from pseudonymkit.construction import check_current, read_patchset, to_pseudonymised_corpus
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(SOURCES))
    ap.add_argument("--tag", required=True, help="the condition build, e.g. union-single0.5-13det-ab12cd")
    ap.add_argument("--entity-type", default="PERSON")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--a4-candidates", type=int, default=10)
    ap.add_argument("--a4-limit", type=int, default=200)
    ap.add_argument("--a4-model", default="gpt-oss-120b")
    ap.add_argument("--conditions", nargs="+", default=["B", "C"])
    ap.add_argument("--context", nargs="+", default=["false"], choices=["false", "true"],
                    help="which auxiliary-context arms to run")
    ap.add_argument("--config", type=Path, default=Path("config/llm_api.toml"))
    ap.add_argument("--out", type=Path, default=Path("results/leakage"))
    args = ap.parse_args()

    documents = list(iter_documents(SOURCES[args.corpus][0]()))
    corpus = Corpus(args.corpus, tuple(documents))
    root = SOURCES[args.corpus][1]()
    log(f"{args.corpus}: {len(documents)} documents, tag {args.tag}")

    args.out.mkdir(parents=True, exist_ok=True)
    # The context arm belongs in the name. Without it, two jobs on one corpus — one per arm, which
    # is how these are parallelised — write the same path and the slower one silently overwrites the
    # faster one's rows. That happened on 2026-09-25 and cost the TAB no-context cells their file.
    arms = "".join(sorted(a[0] for a in args.context))
    destination = args.out / f"{args.corpus}_{args.tag}_{args.entity_type}_a4_ctx{arms}.jsonl"
    rows: list[dict] = []

    for condition in args.conditions:
        path = root / f"{args.corpus}_{condition}_{args.tag}.patch.jsonl"
        if not path.exists():
            log(f"  {condition}: no patch set at {path.name} — SKIPPED")
            continue
        patchset = read_patchset(path)
        check = check_current(documents, patchset)
        result = to_pseudonymised_corpus(documents, patchset)
        log(f"  {condition}: {path.name}, digests verified ({check['patches']} patches)")

        for arm in args.context:
            with_context = arm == "true"
            items = build_items(result, corpus, entity_type=args.entity_type,
                                n_candidates=args.a4_candidates, seed=args.seed,
                                with_context=with_context)
            if args.a4_limit:
                items = items[: args.a4_limit]
            if not items:
                log(f"  A4/{condition} context={with_context}: no queries — SKIPPED")
                continue
            ranker = LlmCandidateRanker(model=args.a4_model, config_path=str(args.config))
            report = score_candidates(items, ranker, condition=condition)
            o = report.overall
            row = report.to_record() | {
                "corpus": args.corpus, "rule": args.tag.split("-")[0], "condition": condition,
                "entity_type": args.entity_type, "seed": args.seed, "model": args.a4_model,
                "queries": len(items), "ensemble_tag": args.tag,
            }
            rows.append(row)
            # Written after every cell: a run that dies in its fourth hour still leaves the cells
            # it finished, and these cost a gateway call per query.
            destination.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            log(f"  A4/{condition} context={str(with_context):<5}: Rank-1 {o.rank1:.3f} "
                f"Rank-5 {o.rank5:.3f} mAP {o.mean_average_precision:.3f} over {len(items)} queries")

    log(f"wrote {len(rows)} rows to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
