#!/usr/bin/env python3
"""§8.2 stability: collision, fragmentation and drift, over condition B.

Three rates, all functions of the mapping and the key normaliser, and **B only** — under C every
identifier of a type is the same string, so there is no mapping whose integrity could be measured.
§4.1 records that no published work reports any of the three, so every number here is new.

The denominators differ, so the three are not comparable with one another and are never averaged.

Drift needs identity *across* documents, which on CARDIO:DE exists only because §12.1 constructs it —
recurring patients and a recurring physician pool. TAB's and OntoNotes' chains are document-scoped,
so drift is not computable there and the row says so rather than reporting a zero.

    . config/env.sh
    python experiments/run_stability.py --corpus cardiode --rule vote
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from pseudonymkit.construction import check_current, read_patchset, to_pseudonymised_corpus
from pseudonymkit.metrics.stability import evaluate_stability
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

CROSS_DOCUMENT = {"cardiode", "enron"}
"""Corpora whose identity spans documents, so drift has a denominator (§8.2)."""


def log(message: str, t0: float = time.time()) -> None:
    print(f"[{time.time() - t0:7.1f}s] {message}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(SOURCES))
    ap.add_argument("--rule", default="union")
    ap.add_argument("--types", nargs="+", default=["PERSON", "LOC", "ORG"])
    ap.add_argument("--out", type=Path, default=Path("results/stability"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    documents = list(iter_documents(SOURCES[args.corpus][0]()))
    if args.limit:
        documents = documents[: args.limit]
    root = SOURCES[args.corpus][1]()
    found = sorted(root.glob(f"{args.corpus}_B_{args.rule}*.patch.jsonl"))
    if not found:
        raise SystemExit(f"no condition-B patch set for {args.corpus} rule {args.rule!r} in {root}")
    patchset = read_patchset(found[0])
    check = check_current(documents, patchset)
    log(f"{args.corpus}: {len(documents)} documents, {found[0].name}, "
        f"{check['patches']} patches verified")

    result = to_pseudonymised_corpus(documents, patchset)
    cross = args.corpus in CROSS_DOCUMENT
    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"{args.corpus}_{args.rule}.jsonl"
    rows = []
    for entity_type in args.types:
        for label, cross_document in (("within_document", False),
                                      *((("across_documents", True),) if cross else ())):
            report = evaluate_stability(result, entity_type, "deterministic",
                                        cross_document=cross_document)
            # as_dict(), not a hand-copied field list: the report already carries drift and the
            # first version of this driver checked for a field named "drifted_chains" that does not
            # exist, so drift was computed and then dropped on the floor.
            row = report.as_dict() | {
                "corpus": args.corpus, "rule": args.rule, "condition": "B", "scope": label,
            }
            rows.append(row)
            drift = (f"drift {report.drift_rate:.4f}" if cross_document
                     else "drift n/a (document-scoped identity)")
            log(f"  {entity_type:<8} {label:<16} chains {report.chains:>5}  "
                f"collision {report.collision_rate:.4f}  "
                f"fragmentation {report.fragmentation_rate:.4f}  {drift}")
    if not cross:
        log("  drift not computable here: identity is document-scoped (§8.2)")
    destination.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    log(f"wrote {len(rows)} rows to {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
