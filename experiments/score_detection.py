#!/usr/bin/env python3
"""§8.1 scoring, swept over single detectors and ensembles of up to three (§7, axis D″).

Detection is the one stage whose sweep is free: the spans are already in the cache, so a combination
rule is set arithmetic and a score is a pass over pre-tokenised documents.  That is what makes
**3,375 span sources per corpus** affordable — 15 singletons, 105 pairs and 455 triples under six
rules — where re-running the frozen models downstream would not be.

    . config/env.sh
    python experiments/score_detection.py --corpus cardiode
    python experiments/score_detection.py --corpus cardiode --max-size 1      # singletons only

Rows land in ``results/detection/<corpus>.jsonl``, one per span source, each carrying its counts as
well as its rates so they can be pooled or bootstrapped later.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from pseudonymkit.detectors.base import DetectorOutput
from pseudonymkit.detectors.cache import DetectorCache, text_digest
from pseudonymkit.detectors.combinators import COMBINATORS
from pseudonymkit.metrics.detection import frequency_weight, prepare, score_prepared, tokenise
from pseudonymkit.paths import cardiode_a, condition_a_dir
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.taxonomy import Harmoniser, source_for

CORPORA = {
    "cardiode": cardiode_a,
    "tab": lambda: condition_a_dir() / "tab_A.jsonl.gz",
    "ontonotes": lambda: condition_a_dir() / "ontonotes_A.jsonl.gz",
    "enron": lambda: condition_a_dir() / "enron_A.jsonl.gz",
}

RULES: tuple[tuple[str, dict], ...] = (
    ("union", {}),
    ("intersection", {}),
    ("vote", {"k": 2}),
    ("vote", {"k": 3}),
)
"""The D′ levels this driver can apply to an arbitrary subset.

``weighted_vote`` needs per-detector weights — §7 says "e.g. by that detector's precision on a dev
split", which this sweep is what produces — and ``cascade`` needs an order.  Both are therefore run
separately once the singleton scores exist, rather than guessed at here.  ``vote(k)`` is emitted only
where ``k`` is meaningful for the subset size, and ``vote(2)`` over a pair is reported rather than
suppressed even though it equals ``intersection``: a degenerate cell is a fact about the design."""


def log(message: str, t0: float = time.time()) -> None:
    print(f"[{time.time() - t0:7.1f}s] {message}", flush=True)


def load_pool(cache: DetectorCache, corpus: str, texts: dict[str, str]) -> dict[str, dict]:
    """Every detector's harmonised, non-stale spans, keyed detector -> doc_id -> spans.

    Harmonised here for the same reason construction harmonises on read: the gateway pool writes the
    model's own label, and an unrouted label would be scored as if it were a harmonised type.
    """
    pool: dict[str, dict] = {}
    for path in sorted(cache.root.glob("*.jsonl")):
        name = path.stem.replace("__", "/")
        harmoniser = Harmoniser(source_for(name, corpus))
        records = cache.load(name, texts=texts)
        pool[name] = {
            doc_id: harmoniser.spans(output.spans) for doc_id, output in records.items()
        }
    return pool


def subsets(detectors: list[str], max_size: int):
    for size in range(1, max_size + 1):
        for combination in itertools.combinations(detectors, size):
            yield combination


def combine(pool: dict, names: tuple[str, ...], rule: str, kwargs: dict, doc_ids) -> dict:
    """One span set per document for this subset under this rule."""
    if len(names) == 1 and rule == "union":
        return pool[names[0]]                       # the singleton case needs no combinator
    combinator = COMBINATORS.create(rule, **kwargs)
    out = {}
    for doc_id in doc_ids:
        outputs = [
            DetectorOutput(doc_id=doc_id, detector=name, spans=tuple(pool[name][doc_id]))
            for name in names
            if doc_id in pool[name]
        ]
        if outputs:
            out[doc_id] = combinator.combine(outputs)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(CORPORA))
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--out", type=Path, default=Path("results/detection"))
    ap.add_argument("--max-size", type=int, default=3,
                    help="largest ensemble; 3 is the plan's D″ (AM, 2026-09-15)")
    ap.add_argument("--limit", type=int, default=0, help="cap documents, for a smoke run")
    ap.add_argument("--weight", choices=["uniform", "frequency"], default="frequency",
                    help="token weighting for information-weighted precision; recorded in every row")
    ap.add_argument("--restart", action="store_true",
                    help="discard an existing file instead of resuming from it")
    args = ap.parse_args()

    path = CORPORA[args.corpus]()
    documents = list(iter_documents(path))
    if args.limit:
        documents = documents[: args.limit]
    texts = {d.doc_id: d.text for d in documents}
    log(f"{args.corpus}: {len(documents)} documents from {path}")

    if args.weight == "frequency":
        counts: Counter[str] = Counter()
        total = 0
        for d in documents:
            for start, end in tokenise(d.text):
                counts[d.text[start:end].casefold()] += 1
                total += 1
        weight, weight_model = frequency_weight(counts, total), f"unigram:{args.corpus}"
        log(f"  weighting: corpus unigram self-information over {total} tokens, "
            f"{len(counts)} types")
    else:
        from pseudonymkit.metrics.detection import uniform_weight
        weight, weight_model = uniform_weight, "uniform"

    index = prepare(documents, corpus=args.corpus, weight=weight, weight_model=weight_model)
    log(f"  prepared: {sum(len(d.tokens) for d in index.documents)} tokens, "
        f"co-reference {'present' if index.any_coref else 'absent'}")

    cache = DetectorCache(args.cache, args.corpus)
    pool = load_pool(cache, args.corpus, texts)
    detectors = sorted(pool)
    log(f"  detectors: {len(detectors)}")

    # gold is a level of axis D (§7) and is the perfect-detection ceiling
    pool["gold"] = {d.doc_id: tuple(m.span for m in d.mentions) for d in documents}

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"{args.corpus}.jsonl"

    # **Resume, because this run has already been killed once.** The head node terminates long-lived
    # processes — it did so to Presidio three times and to the first full sweep at ~1,600 of 2,151
    # sources, silently and with no traceback. Appending and skipping what is already scored means a
    # kill costs the source in flight rather than the run, and the same guard makes the job safe to
    # resubmit under Slurm.
    done: set[str] = set()
    if destination.exists() and not args.restart:
        for line in destination.open(encoding="utf-8"):
            try:
                done.add(json.loads(line)["detector"])
            except Exception:       # a torn final line from a killed run; skip it, keep the rest
                continue
        log(f"  resuming: {len(done)} span sources already scored")

    written = len(done)
    started = time.time()
    with destination.open("a" if done else "w", encoding="utf-8", buffering=1) as handle:
        if "gold" not in done:
            row = score_prepared(index, pool["gold"], detector="gold").as_dict()
            row.update(ensemble=["gold"], rule="—", size=0)
            handle.write(json.dumps(row) + "\n")
            written += 1

        for names in subsets(detectors, args.max_size):
            for rule, kwargs in RULES:
                k = kwargs.get("k")
                if len(names) == 1 and (rule != "union"):
                    continue                      # one detector has nothing to combine
                if k is not None and k > len(names):
                    continue                      # vote(3) over a pair is not defined
                label = f"{'+'.join(names)}|{rule}{k if k else ''}"
                if label in done:
                    continue
                spans = combine(pool, names, rule, kwargs, texts)
                score = score_prepared(index, spans, detector=label)
                out = score.as_dict()
                out.update(ensemble=list(names), rule=rule if len(names) > 1 else "single",
                           k=k, size=len(names))
                handle.write(json.dumps(out) + "\n")
                os.fsync(handle.fileno())
                written += 1
            if written % 200 < 4:
                rate = written / max(time.time() - started, 1e-9)
                log(f"  {written} span sources scored  {rate:.1f}/s")

    log(f"wrote {written} rows to {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
