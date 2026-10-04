#!/usr/bin/env python3
"""Audit of the ENRON 2.0 gold standard against the fifteen detectors (paper 2, plan §4).

Two questions, both answered with the detector cache as a second opinion and never as the truth:

1. **Precision** — how many gold-standard PERSON mentions are not person names? Every mention gets
   the number of detectors that tagged it PERSON (``k_person``) and the surface features that the
   matching rules ignore: letter case, a following contraction ("'t"), whether it sits inside a URL,
   path or address, whether it opens a sentence, how often its token appears lower-cased elsewhere in
   the corpus (a common-word signal), and the rule (``gold_rule``) that produced it.
2. **Recall** — how many names does the gold standard miss? PERSON spans the detectors agree on that
   overlap no gold-standard mention, counted by how many detectors agree.

Aggregates go to ``--out`` (no surface, no text). ``--review`` writes stratified random samples
with their context for a human reader: that file holds real names from the corpus, is created
owner-only, and is never committed or released (plan §15).

    . config/env.sh
    python experiments/probes/enron2_gold_audit.py --review logs/enron2_gold_review.txt
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "src")

from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.paths import condition_a_dir
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.taxonomy import Harmoniser, source_for

WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
CONTRACTION = re.compile(r"['’](?:t|ll|re|ve|d|m)\b", re.IGNORECASE)
BINS = ((0, 0), (1, 2), (3, 5), (6, 9), (10, 99))


def k_bin(k: int) -> str:
    for low, high in BINS:
        if low <= k <= high:
            return f"{low}" if low == high else f"{low}-{high}" if high < 99 else f"{low}+"
    return "?"


def shape(surface: str) -> str:
    letters = [c for c in surface if c.isalpha()]
    if letters and all(c.islower() for c in letters):
        return "lower"
    if letters and all(c.isupper() for c in letters):
        return "UPPER"
    words = WORD.findall(surface)
    if words and all(w[0].isupper() for w in words):
        return "Title"
    return "mixed"


def rule_of(mention) -> str:
    return (mention.attributes or {}).get("gold_rule") or mention.mention_id.rstrip("0123456789")


def enclosing_token(text: str, start: int, end: int) -> str:
    left = start
    while left > 0 and not text[left - 1].isspace():
        left -= 1
    right = end
    while right < len(text) and not text[right].isspace():
        right += 1
    return text[left:right]


def sentence_initial(text: str, start: int) -> bool:
    before = text[max(0, start - 3):start].rstrip(" \t\"'(")
    return start == 0 or not before or before[-1] in ".!?\n:"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--out", type=Path, default=Path("results/enron2/gold_audit.json"))
    ap.add_argument("--review", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    docs = list(iter_documents(condition_a_dir() / "enron2_A.jsonl.gz"))
    texts = {d.doc_id: d.text for d in docs}
    cache = DetectorCache(args.cache, "enron2")
    detectors = sorted(p.stem.replace("__", "/") for p in cache.root.glob("*.jsonl"))
    person: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    anytype: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    for name in detectors:
        harmoniser = Harmoniser(source_for(name, "enron2"))
        for doc_id, output in cache.load(name, texts=texts).items():
            for span in harmoniser.spans(output.spans):
                anytype[doc_id].append((span.start, span.end, name))
                if span.type == "PERSON":
                    person[doc_id].append((span.start, span.end, name))

    # How often each word appears lower-cased against capitalised, over the whole corpus.
    lower, upper = Counter(), Counter()
    for d in docs:
        for w in WORD.findall(d.text):
            (lower if w.islower() else upper)[w.casefold()] += 1

    def lower_ratio(surface: str) -> float:
        words = [w.casefold() for w in WORD.findall(surface)]
        ratios = [lower[w] / (lower[w] + upper[w]) for w in words if lower[w] + upper[w]]
        return max(ratios) if ratios else 0.0

    def agreeing(spans, start, end) -> int:
        return len({name for s, e, name in spans if s < end and e > start})

    rows = []
    for d in docs:
        for m in d.mentions:
            if m.type != "PERSON":
                continue
            s, e = m.span.start, m.span.end
            token = enclosing_token(d.text, s, e)
            rows.append({
                "doc_id": d.doc_id, "start": s, "end": e, "rule": rule_of(m),
                "k_person": agreeing(person[d.doc_id], s, e),
                "k_any": agreeing(anytype[d.doc_id], s, e),
                "shape": shape(m.span.text), "tokens": len(WORD.findall(m.span.text)),
                "contraction": bool(CONTRACTION.match(d.text, e)),
                "in_url_path_address": any(c in token for c in "/\\@") or
                                       "http" in token.casefold() or "www" in token.casefold(),
                "sentence_initial": sentence_initial(d.text, s),
                "subject_line": d.text.find("\n") > s,
                "lower_ratio": round(lower_ratio(m.span.text), 3),
                "has_entity": m.gold_entity_id is not None,
                "external_entity": bool(m.gold_entity_id) and
                                   not str(m.gold_entity_id).endswith("@enron.com"),
            })

    # ---- recall: detector PERSON spans that touch no gold-standard mention at all
    gold_spans = {d.doc_id: [(m.span.start, m.span.end) for m in d.mentions] for d in docs}
    unlabelled = []
    for doc_id, spans in person.items():
        spans = sorted(spans)
        groups: list[list[tuple[int, int, str]]] = []
        for span in spans:                      # merge overlapping spans into one candidate
            if groups and span[0] < max(e for _, e, _ in groups[-1]):
                groups[-1].append(span)
            else:
                groups.append([span])
        for group in groups:
            start, end = min(s for s, _, _ in group), max(e for _, e, _ in group)
            if any(s < end and e > start for s, e in gold_spans.get(doc_id, ())):
                continue
            unlabelled.append({"doc_id": doc_id, "start": start, "end": end,
                               "k": len({n for _, _, n in group})})

    summary = {
        "documents": len(docs), "detectors": len(detectors),
        "gold_person_mentions": len(rows),
        "by_rule_and_k_person": {
            rule: dict(sorted(Counter(k_bin(r["k_person"]) for r in rows if r["rule"] == rule).items()))
            for rule in sorted({r["rule"] for r in rows})},
        "flags_among_k_person_0": {
            flag: sum(1 for r in rows if r["k_person"] == 0 and r[flag])
            for flag in ("contraction", "in_url_path_address", "sentence_initial",
                         "subject_line", "external_entity")},
        "shape_among_k_person_0": dict(Counter(r["shape"] for r in rows if r["k_person"] == 0)),
        "lower_ratio_over_half_among_k_person_0":
            sum(1 for r in rows if r["k_person"] == 0 and r["lower_ratio"] > 0.5),
        "lower_ratio_over_half_among_k_person_6_plus":
            sum(1 for r in rows if r["k_person"] >= 6 and r["lower_ratio"] > 0.5),
        "unlabelled_person_candidates_by_k": dict(sorted(Counter(k_bin(u["k"]) for u in unlabelled).items())),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))

    if args.review:
        rng = random.Random(args.seed)
        old = os.umask(0o077)
        try:
            with args.review.open("w", encoding="utf-8") as handle:
                def context(doc_id, s, e):
                    t = texts[doc_id]
                    left = re.sub(r"\s+", " ", t[max(0, s - 70):s])
                    right = re.sub(r"\s+", " ", t[e:e + 50])
                    return f"{left}⟦{t[s:e]}⟧{right}"
                for label, members, n in (
                    ("GOLD k_person=0", [r for r in rows if r["k_person"] == 0], 60),
                    ("GOLD k_person=1-2", [r for r in rows if 1 <= r["k_person"] <= 2], 30),
                    ("GOLD k_person=3-5", [r for r in rows if 3 <= r["k_person"] <= 5], 20),
                    ("GOLD k_person>=6", [r for r in rows if r["k_person"] >= 6], 20),
                ):
                    handle.write(f"\n===== {label}: {len(members)} mentions, {n} drawn\n")
                    for i, r in enumerate(rng.sample(members, min(n, len(members))), 1):
                        handle.write(f"{i:3d} [{r['rule'][:24]:24s} k={r['k_person']:2d} "
                                     f"{r['shape']:5s} low={r['lower_ratio']:.2f}] "
                                     f"{context(r['doc_id'], r['start'], r['end'])}\n")
                for label, members, n in (
                    ("UNLABELLED k>=10", [u for u in unlabelled if u["k"] >= 10], 30),
                    ("UNLABELLED k=6-9", [u for u in unlabelled if 6 <= u["k"] <= 9], 25),
                    ("UNLABELLED k=3-5", [u for u in unlabelled if 3 <= u["k"] <= 5], 25),
                ):
                    handle.write(f"\n===== {label}: {len(members)} candidates, {n} drawn\n")
                    for i, u in enumerate(rng.sample(members, min(n, len(members))), 1):
                        handle.write(f"{i:3d} [k={u['k']:2d}] "
                                     f"{context(u['doc_id'], u['start'], u['end'])}\n")
        finally:
            os.umask(old)
        print(f"review samples written to {args.review} (owner-only; contains corpus names)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
