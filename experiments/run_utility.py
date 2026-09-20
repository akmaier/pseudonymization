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
from concurrent.futures import ThreadPoolExecutor
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
    ap.add_argument("--concurrency", type=int, default=1,
                    help="gateway calls in flight at once. Enron is 58,636 documents x 3 "
                         "conditions per rule; sequentially that is ~11 days a rule, which is not "
                         "a measurement limit but a driver one")
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

    def score_one(name, one, result, condition, instrument):
        """One document through one task. Returns ``(doc_id, vectors, error)`` — never raises.

        Run on a worker thread, so it must not touch ``handle``: every write stays on the main
        thread.  That is not fastidiousness — the detector cache lost four records to two processes
        appending 13 KB lines at once, and a single writer is the cheap way not to repeat it.
        """
        single = PseudonymisedCorpus(documents=(one,), mapping=result.mapping)
        try:
            return one.document.doc_id, _run(name, single, condition, instrument), None
        except Exception as exc:              # reported, never silently skipped (§1)
            return one.document.doc_id, None, f"{type(exc).__name__}: {exc}"

    with destination.open("a" if done else "w", encoding="utf-8", buffering=1) as handle:
        for name in wanted:
            log(f"=== {name} ===")
            instrument = _build(name, args)     # once per task, not once per document
            for condition, result in corpora.items():
                started = time.time()
                scored = failed = 0
                todo = [one for one in result.documents
                        if (condition, name, one.document.doc_id) not in done]

                def emit(doc_id, vectors, error):
                    """Write one document's result. Main thread only."""
                    nonlocal rows, failed, scored
                    if error is not None:
                        failed += 1
                        handle.write(json.dumps({
                            "corpus": args.corpus, "rule": args.rule, "condition": condition,
                            "task": name, "doc_id": doc_id, "error": error,
                        }) + "\n")
                        os.fsync(handle.fileno())
                        rows += 1
                        return
                    for task_key, vector in vectors.items():
                        for scored_id, score in zip(vector.doc_ids, vector.scores):
                            handle.write(json.dumps({
                                "corpus": args.corpus, "rule": args.rule, "condition": condition,
                                "task": task_key, "doc_id": scored_id, "score": score,
                                "model": args.model,
                            }) + "\n")
                            rows += 1
                    os.fsync(handle.fileno())
                    scored += 1

                # **Chunked, so the corpus is never held whole.** Enron is 58,636 documents per
                # condition; submitting them all at once would pin every PseudonymisedDocument and
                # every pending result for the life of the pass. At most `concurrency * 4` are in
                # flight, which is what the gateway detector already does for the same reason.
                if args.concurrency > 1:
                    with ThreadPoolExecutor(max_workers=args.concurrency,
                                            thread_name_prefix="utility") as pool:
                        for start in range(0, len(todo), args.concurrency * 4):
                            chunk = todo[start : start + args.concurrency * 4]
                            futures = [pool.submit(score_one, name, one, result,
                                                   condition, instrument)
                                       for one in chunk]
                            for future in futures:
                                emit(*future.result())
                            rate = scored / max(time.time() - started, 1e-9)
                            left = (len(todo) - scored) / rate if rate else float("inf")
                            log(f"  {condition}/{name}: {scored}/{len(todo)}  "
                                f"{rate * 3600:.0f}/h  eta {left / 3600:.1f}h  failed {failed}")
                    continue

                for one in todo:
                    emit(*score_one(name, one, result, condition, instrument))
                    if scored % 25 == 0:
                        rate = scored / max(time.time() - started, 1e-9)
                        left = (len(result.documents) - scored) / rate if rate else float("inf")
                        log(f"  {condition}/{name}: {scored}/{len(result.documents)}  "
                            f"{rate * 3600:.0f}/h  eta {left / 3600:.1f}h  failed {failed}")
                log(f"  {condition}/{name}: {scored} documents scored, {failed} failed, "
                    f"{time.time() - started:.0f}s")
    log(f"wrote {rows} rows to {destination}")
    return 0


def _build(name: str, args):
    """The frozen instrument for one task, built **once**.

    This used to live inside :func:`_run`, which is called per document, so ``ner_agreement``
    constructed a ``PresidioDetector`` and loaded its spaCy pipeline for every document in the
    corpus. Measured on TAB: 9.6 s per document, of which Presidio's own detection is 0.27 s — the
    other 9.3 s was rebuilding the model. Over Enron's 58,636 documents times three conditions that
    is eleven days a rule of pure setup, and it is why concurrency made things *slower* rather than
    faster: eight threads each building their own spaCy pipeline contend for CPU and for the GIL,
    and there was no I/O for them to overlap.

    The instrument must be identical across conditions for §8.3's comparison to mean anything, so
    building it once is not only faster, it is the thing the protocol actually asks for.
    """
    from pseudonymkit.tasks.models import LlmSingleLabelClassifier, LlmSpanExtractor

    if name == "medication_ie":
        return LlmSpanExtractor(model=args.model, config_path=args.config)
    if name == "section_classification":
        return LlmSingleLabelClassifier(model=args.model, config_path=args.config)
    if name == "ner_agreement":
        from pseudonymkit.detectors.rule import PresidioDetector

        detector = PresidioDetector()
        detector.load()
        return detector
    raise SystemExit(f"unknown task {name!r}")


def _run(name: str, result, condition: str, instrument) -> dict:
    """One task over one condition, using the instrument :func:`_build` already made."""
    if name == "medication_ie":
        return medication_ie(result, instrument, condition=condition)
    if name == "section_classification":
        return {"section_classification": section_classification(result, instrument,
                                                                 condition=condition)}
    if name == "ner_agreement":
        return {"ner_agreement": ner_agreement(result, instrument, condition=condition)}
    raise SystemExit(f"unknown task {name!r}")


if __name__ == "__main__":
    sys.exit(main())
