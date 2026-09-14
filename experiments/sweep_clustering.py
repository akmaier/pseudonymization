#!/usr/bin/env python3
"""Choose ``link`` and ``iou`` for the ensemble, by measurement rather than by the default.

``cluster_spans`` decides what counts as *one* entity when detectors disagree about a boundary, and
until 2026-09-12 its two settings were unreachable from the combination rules — so they were
invisible parameters of every ensemble number the study would have produced. This picks them.

* ``link="single"`` — transitive overlap. Chains: ``A(0,10)``, ``B(8,20)``, ``C(18,30)`` become one
  cluster although A and C are disjoint, which on dense text merges two adjacent people into one
  entity and pseudonymises them as one.
* ``link="iou"`` — a span joins only if its intersection-over-union with a member reaches a
  threshold. No chaining, at the price of splitting genuine boundary disagreement when one detector
  is much more generous than another.

Scored at **character level** against gold, which is the granularity that matters here: the question
is which characters get replaced, and a boundary disagreement is a partial credit rather than a
miss. Token-level exact match would score *Dr. Weber* against *Weber* as a total failure in both
directions and tell us nothing about the parameter.

Two diagnostics beside F1, because F1 alone cannot see the failure mode each setting has:

* **span inflation** — mean detected span length over mean gold span length. Chaining shows up here
  before it shows up in F1.
* **merge rate** — detected spans that cover two or more *distinct* gold spans. This is chaining's
  actual harm: two people replaced by one pseudonym.

Run after a detection sweep, on the corpora that have gold:

    python experiments/sweep_clustering.py --cache results/sweep_cache --corpora tab ontonotes cardiode
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pseudonymkit.construction import detected_documents
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.domain import Document

CONDITION_A = Path("data/conditionA")
CARDIODE_A = Path("/cluster/maier/dua-restricted/cardiode/A/cardiode_A.jsonl.gz")
SOURCES = {
    "tab": CONDITION_A / "tab_A.jsonl.gz",
    "ontonotes": CONDITION_A / "ontonotes_A.jsonl.gz",
    "enron": CONDITION_A / "enron_A.jsonl.gz",
    "cardiode": CARDIODE_A,
}


def char_set(spans) -> set[int]:
    out: set[int] = set()
    for span in spans:
        out.update(range(span.start, span.end))
    return out


def score(documents: list[Document], gold: dict[str, Document]) -> dict:
    """Character-level P/R/F1 against gold, plus the two chaining diagnostics."""
    tp = fp = fn = 0
    det_len = det_n = gold_len = gold_n = 0
    merges = covered = 0
    for document in documents:
        reference = gold.get(document.doc_id)
        if reference is None:
            continue
        g = char_set(m.span for m in reference.mentions)
        d = char_set(m.span for m in document.mentions)
        tp += len(g & d)
        fp += len(d - g)
        fn += len(g - d)
        for mention in document.mentions:
            det_len += mention.span.length
            det_n += 1
            hit = sum(
                1 for r in reference.mentions
                if r.span.start < mention.span.end and mention.span.start < r.span.end
            )
            covered += bool(hit)
            merges += hit > 1              # one detected span swallowing two gold entities
        for r in reference.mentions:
            gold_len += r.span.length
            gold_n += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "spans": det_n,
        "span_inflation": round((det_len / det_n) / (gold_len / gold_n), 3)
        if det_n and gold_n else None,
        "merge_rate": round(merges / covered, 4) if covered else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=Path("results/sweep_cache"))
    ap.add_argument("--corpora", nargs="+", default=["tab", "ontonotes", "cardiode"])
    ap.add_argument("--rules", nargs="+", default=["union", "vote", "intersection"])
    ap.add_argument("--ious", nargs="+", type=float,
                    default=[0.1, 0.3, 0.5, 0.7, 0.9])
    ap.add_argument("--out", type=Path, default=Path("results/clustering_sweep.json"))
    args = ap.parse_args()

    rows = []
    for corpus in args.corpora:
        source = SOURCES[corpus]
        if not source.exists():
            print(f"{corpus}: no condition A at {source} — skipped", flush=True)
            continue
        from pseudonymkit.serialisation import iter_documents

        documents = list(iter_documents(source))
        gold = {d.doc_id: d for d in documents if d.mentions}
        cache = DetectorCache(args.cache, corpus)
        detectors = sorted(cache.stats())
        if not detectors:
            print(f"{corpus}: nothing cached — skipped", flush=True)
            continue
        # Only the documents this sweep actually detected on.
        cached_ids = set()
        for detector in detectors:
            cached_ids |= set(cache.done(detector))
        subset = [d for d in documents if d.doc_id in cached_ids]
        print(f"\n=== {corpus}: {len(subset)} documents, {len(detectors)} detectors, "
              f"{sum(1 for d in subset if d.mentions)} with gold ===", flush=True)
        if not any(d.mentions for d in subset):
            print("  no gold on the sampled documents — cannot score", flush=True)
            continue

        print(f"  {'rule':<13}{'link':<8}{'iou':>5}{'P':>8}{'R':>8}{'F1':>8}"
              f"{'spans':>8}{'inflation':>11}{'merge':>8}")
        for rule in args.rules:
            settings = [("single", 0.5)] + [("iou", v) for v in args.ious]
            for link, iou in settings:
                detected, _ = detected_documents(
                    subset, cache, detectors, rule,
                    rule_kwargs={"link": link, "iou": iou},
                )
                result = score(detected, gold)
                rows.append({"corpus": corpus, "rule": rule, "link": link, "iou": iou, **result})
                print(f"  {rule:<13}{link:<8}{iou:>5.1f}"
                      f"{result['precision']:>8.3f}{result['recall']:>8.3f}{result['f1']:>8.3f}"
                      f"{result['spans']:>8}{str(result['span_inflation']):>11}"
                      f"{str(result['merge_rate']):>8}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
