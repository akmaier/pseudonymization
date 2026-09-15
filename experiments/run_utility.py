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
import sys
import time
from pathlib import Path

from pseudonymkit.conditions import Unmodified
from pseudonymkit.construction import read_patchset, to_pseudonymised_corpus
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
        out[condition] = to_pseudonymised_corpus(documents, patchset)
        log(f"  {condition}: {matches[0].name}, {len(out[condition].documents)} documents")
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

    with destination.open("w", encoding="utf-8") as handle:
        for name in wanted:
            log(f"=== {name} ===")
            for condition, result in corpora.items():
                started = time.time()
                try:
                    vectors = _run(name, result, condition, args)
                except Exception as exc:              # reported, never silently skipped (§1)
                    log(f"  {condition}/{name}: FAILED — {type(exc).__name__}: {exc}")
                    handle.write(json.dumps({
                        "corpus": args.corpus, "rule": args.rule, "condition": condition,
                        "task": name, "error": f"{type(exc).__name__}: {exc}",
                    }) + "\n")
                    rows += 1
                    continue
                for key, vector in vectors.items():
                    row = {
                        "corpus": args.corpus, "rule": args.rule, "condition": condition,
                        "task": key, "model": args.model,
                        "n": len(vector.scores), "mean": vector.mean, "sd": vector.sd,
                        "scores": list(vector.scores), "doc_ids": list(vector.doc_ids),
                        "elapsed": time.time() - started,
                    }
                    handle.write(json.dumps(row) + "\n")
                    rows += 1
                    log(f"  {condition}/{key}: n={len(vector.scores)} mean={vector.mean:.4f}")
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
