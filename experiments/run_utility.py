#!/usr/bin/env python3
"""§8.3 utility: frozen models over each condition, per-document scores kept.

The unit of analysis is the document, and the **vector** of per-document scores is the primary
artefact — not the mean (§8.3, §9).  Summaries are derived from it afterwards, so the paired tests
§8.3 mandates (Wilcoxon, McNemar) have something to pair.

**Condition A is always run beside the others.**  §8.3: *"Always report the original-text score
beside every condition. If the frozen model is near chance on the original, that task's numbers are
uninterpretable."*  So A is not optional here and cannot be switched off.

    . config/env.sh
    python experiments/run_utility.py --corpus cardiode
    python experiments/run_utility.py --corpus cardiode --rule vote --limit 20

Conditions B and C are read from the patch sets on disk and turned back into the shape the runners
consume by :func:`pseudonymkit.construction.to_pseudonymised_corpus`, which replays and checks the
engine's own offsets.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from pseudonymkit.conditions import Unmodified
from pseudonymkit.construction import (
    check_current,
    read_patchset,
    to_pseudonymised_corpus,
)
from pseudonymkit.engine import PseudonymisedCorpus
from pseudonymkit.paths import cardiode_a, cardiode_conditions, condition_a_dir, work_dir
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.tasks import medication_ie, ner_agreement, section_classification

SOURCES = {
    "cardiode": (cardiode_a, cardiode_conditions),
    "tab": (lambda: condition_a_dir() / "tab_A.jsonl.gz", lambda: work_dir() / "results/conditions"),
    "ontonotes": (lambda: condition_a_dir() / "ontonotes_A.jsonl.gz",
                  lambda: work_dir() / "results/conditions"),
    "enron": (lambda: condition_a_dir() / "enron_A.jsonl.gz",
              lambda: work_dir() / "results/conditions"),
}

TASKS_FOR = {
    "cardiode": ("medication_ie", "section_classification", "ner_agreement"),
    "tab": ("ner_agreement",),
    "ontonotes": ("ner_agreement",),
    "enron": ("ner_agreement",),
}
"""§8.3's table, per corpus. CARDIO:DE's two clinical tasks plus the corpus-blind NER agreement,
which reaches every corpus through that table's "all" row."""


def log(message: str, t0: float = time.time()) -> None:
    print(f"[{time.time() - t0:7.1f}s] {message}", flush=True)


def _already_done(destination: Path) -> set[tuple[str, str, str]]:
    """(condition, task, doc_id) triples already on disk, so a resumed run skips them."""
    done: set[tuple[str, str, str]] = set()
    if not destination.exists():
        return done
    for line in destination.open(encoding="utf-8"):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue                     # a torn final line from a killed job
        if row.get("doc_id"):
            done.add((row.get("condition"), row.get("task"), row["doc_id"]))
    return done


def conditioned(corpus: str, documents, rule: str, conditions):
    """condition -> the corpus in the shape the runners consume."""
    out = {"A": Unmodified().pseudonymise_corpus(documents)}
    root = SOURCES[corpus][1]()
    for condition in conditions:
        if condition == "A":
            continue
        matches = sorted(root.glob(f"{corpus}_{condition}_{rule}*.patch.jsonl"))
        if not matches:
            log(f"  {condition}: no patch set matching {rule!r} in {root} — SKIPPED")
            continue
        patchset = read_patchset(matches[0])
        # **Before anything costs model time.** A patch is offsets into a text it does not carry, so
        # it is silently wrong the moment condition A is rebuilt — which happened on 2026-09-15
        # underneath a running job, and nine hours went into scoring a corpus that no longer existed.
        check = check_current(documents, patchset)
        patchset_ok = True
        out[condition] = to_pseudonymised_corpus(documents, patchset)
        log(f"  {condition}: {matches[0].name}, {len(out[condition].documents)} documents, "
            f"text digests verified ({check['patches']} patches)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(SOURCES))
    ap.add_argument("--rule", default="union", help="which combination rule's patch set to score")
    ap.add_argument("--conditions", nargs="+", default=["A", "B", "C"])
    ap.add_argument("--tasks", nargs="+", default=None)
    ap.add_argument("--model", default="gpt-oss-120b")
    ap.add_argument("--config", type=Path, default=Path("config/llm_api.toml"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=Path, default=Path("results/utility"))
    ap.add_argument("--restart", action="store_true",
                    help="discard an existing file instead of resuming from it")
    args = ap.parse_args()

    documents = list(iter_documents(SOURCES[args.corpus][0]()))
    if args.limit:
        documents = documents[: args.limit]
    log(f"{args.corpus}: {len(documents)} documents")

    corpora = conditioned(args.corpus, documents, args.rule, args.conditions)
    if "A" not in corpora:
        raise SystemExit("condition A is not optional — §8.3 requires it beside every condition")

    wanted = args.tasks or TASKS_FOR[args.corpus]
    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"{args.corpus}_{args.rule}.jsonl"
    rows = 0

    # **One document at a time, flushed as it lands.** The runners score each document
    # independently, so driving them per document costs only call overhead and buys durability at
    # text level: a killed job keeps every letter it finished instead of losing the whole
    # task x condition. The previous shape wrote nothing for nine hours and then lost all of it.
    done = _already_done(destination) if not args.restart else set()
    if done:
        log(f"resuming: {len(done)} (condition, task, document) results already on disk")

    with destination.open("a" if done else "w", encoding="utf-8", buffering=1) as handle:
        for name in wanted:
            log(f"=== {name} ===")
            for condition, result in corpora.items():
                started = time.time()
                scored = failed = 0
                for one in result.documents:
                    key = (condition, name, one.document.doc_id)
                    if key in done:
                        continue
                    single = PseudonymisedCorpus(documents=(one,), mapping=result.mapping)
                    try:
                        vectors = _run(name, single, condition, args)
                    except Exception as exc:          # reported, never silently skipped (§1)
                        failed += 1
                        handle.write(json.dumps({
                            "corpus": args.corpus, "rule": args.rule, "condition": condition,
                            "task": name, "doc_id": one.document.doc_id,
                            "error": f"{type(exc).__name__}: {exc}",
                        }) + "\n")
                        os.fsync(handle.fileno())
                        rows += 1
                        continue
                    for task_key, vector in vectors.items():
                        for doc_id, score in zip(vector.doc_ids, vector.scores):
                            handle.write(json.dumps({
                                "corpus": args.corpus, "rule": args.rule, "condition": condition,
                                "task": task_key, "doc_id": doc_id, "score": score,
                                "model": args.model,
                            }) + "\n")
                            rows += 1
                    os.fsync(handle.fileno())
                    scored += 1
                    if scored % 25 == 0:
                        rate = scored / max(time.time() - started, 1e-9)
                        left = (len(result.documents) - scored) / rate if rate else float("inf")
                        log(f"  {condition}/{name}: {scored}/{len(result.documents)}  "
                            f"{rate * 3600:.0f}/h  eta {left / 3600:.1f}h  failed {failed}")
                log(f"  {condition}/{name}: {scored} documents scored, {failed} failed, "
                    f"{time.time() - started:.0f}s")
    log(f"wrote {rows} rows to {destination}")
    return 0


def _run(name: str, result, condition: str, args) -> dict:
    """One task over one condition.  Returns task key -> ScoreVector."""
    from pseudonymkit.tasks.models import LlmSingleLabelClassifier, LlmSpanExtractor

    if name == "medication_ie":
        model = LlmSpanExtractor(model=args.model, config_path=args.config)
        return medication_ie(result, model, condition=condition)
    if name == "section_classification":
        model = LlmSingleLabelClassifier(model=args.model, config_path=args.config)
        return {"section_classification": section_classification(result, model,
                                                                 condition=condition)}
    if name == "ner_agreement":
        from pseudonymkit.detectors.rule import PresidioDetector

        detector = PresidioDetector()
        detector.load()
        return {"ner_agreement": ner_agreement(result, detector, condition=condition)}
    raise SystemExit(f"unknown task {name!r}")


if __name__ == "__main__":
    sys.exit(main())
