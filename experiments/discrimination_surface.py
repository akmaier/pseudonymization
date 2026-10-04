#!/usr/bin/env python3
"""The discrimination surface (plan §8.3): can the attacker tell a surrogate from a survivor?

At each operating point condition B is built in memory exactly as ``sweep_leakage`` builds it —
the same pinned inventory, the same key, the same span source — and every name-like span the
attacker can see is labelled by position (:mod:`pseudonymkit.attacks.occurrences`). Among the
spans that are surrogates or survivors, a logistic regression cross-fitted over documents predicts
which is which, from the two feature groups plan §8.3 says Carrell 2019 conflates:

(a) **error correlation** — did an attacker-side detector tag this span? One binary feature per
    attacker variant of §7.4, looked up at the span's condition-A offsets. That is phase 1's
    stand-in for the attacker's re-tagging (§7.3): Bao et al. 2026 find surrogate substitution
    detection-neutral, so where a detector fires on A predicts where it fires on B.
(b) **generator artefacts** — gazetteer membership (the span is an entry of the generator's own
    pools), single-token-ness, ``.title()`` orthography, population frequency against frequency in
    the release (the draw is uniform, never frequency-matched), within- and cross-document
    repetition.

Each row reports out-of-fold AUROC for (b) alone, for (a) alone and (a)+(b) per variant, and the
class counts they rest on. A point with fewer than ``--min-class`` spans in either class gets no
AUROC and says why: on CARDIO:DE most good points leave one or two survivors, and an AUROC over
two positives is not a measurement.

**Not here:** §8.3's other separation, *"holding the span set fixed and swapping only the
generator"*. It needs a second surrogate generator, and which one is AM's to choose.

    . config/env.sh
    python experiments/discrimination_surface.py --corpus enron2 \\
        --sources results/leakage_sweep/shards/enron2_00.txt \\
        --variants results/phase1/enron2_variants.json \\
        --out results/discrimination/enron2_00.jsonl

CPU only, no model calls, resumable. Writes rates and counts only — no surface, no text (§15).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "experiments")

from pseudonymkit.attacks.occurrences import label_occurrences
from pseudonymkit.construction import construct, detected_documents, to_pseudonymised_corpus
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.serialisation import iter_documents
from sweep_leakage import CORPORA, external_priors, parse_label

T0 = time.time()
ARTEFACTS = ("in_gazetteer", "single_token", "title_case", "population_log_frequency",
             "release_log_frequency", "frequency_mismatch", "within_document", "across_documents")


def log(message: str) -> None:
    print(f"[{time.time() - T0:8.1f}s] {message}", flush=True)


def attacker_spans(documents, cache, label):
    """doc_id -> sorted condition-A spans of one attacker variant."""
    names, rule, kwargs = parse_label(label)
    detected, _ = detected_documents(documents, cache, list(names), rule=rule, rule_kwargs=kwargs)
    return {d.doc_id: sorted((m.span.start, m.span.end) for m in d.mentions) for d in detected}


def tagged(spans, start, end) -> int:
    for s, e in spans:
        if s >= end:
            return 0
        if e > start:
            return 1
    return 0


def generator_pool(inventory, languages) -> set[str]:
    """Every surface the generator can draw, casefolded, over all its pools for these languages."""
    pool: set[str] = set()
    for (entity_type, language), entries in inventory._entries.items():  # noqa: SLF001
        if language in languages:
            pool.update(entry.surface.casefold() for entry in entries)
    return pool


def population(corpus: str, entity_type: str = "PERSON") -> dict[str, float]:
    """Relative population frequency per name key, from the attacker's public name lists.

    The same lists the sweep's realistic A2 adversary uses (``external_priors``), keyed as the
    priors key them (``keys.entity_key`` under the N2 normaliser) and merged by taking the larger
    relative frequency where a name is on more than one list.
    """
    out: dict[str, float] = {}
    for prior in external_priors(corpus, entity_type):
        total = sum(prior.weights.values()) or 1.0
        for name_key, weight in prior.weights.items():
            out[name_key] = max(out.get(name_key, 0.0), weight / total)
    return out


def features(occurrences, pool, frequencies, variants, attackers, entity_type="PERSON"):
    """One row of features per occurrence: group (b), then one (a) column per variant."""
    from pseudonymkit.keys import NORMALISERS, entity_key

    normaliser = NORMALISERS.create("N2")
    in_release = Counter(o.surface for o in occurrences)
    total = sum(in_release.values()) or 1
    per_doc = Counter((o.doc_id, o.surface) for o in occurrences)
    docs_with = defaultdict(set)
    for o in occurrences:
        docs_with[o.surface].add(o.doc_id)
    floor = min(frequencies.values()) / 10 if frequencies else 1e-9
    rows_b, rows_a = [], []
    for o in occurrences:
        tokens = o.surface.split()
        pop = max((frequencies.get(entity_key(t, entity_type, normaliser), 0.0)
                   for t in tokens), default=0.0)
        release = in_release[o.surface] / total
        rows_b.append([
            1.0 if o.surface.casefold() in pool else 0.0,
            1.0 if len(tokens) == 1 else 0.0,
            1.0 if o.surface == o.surface.title() else 0.0,
            math.log(max(pop, floor)),
            math.log(release),
            math.log(release) - math.log(max(pop, floor)),
            math.log(per_doc[(o.doc_id, o.surface)]),
            math.log(len(docs_with[o.surface])),
        ])
        rows_a.append([tagged(attackers[v].get(o.doc_id, ()), o.old_start, o.old_end)
                       for v in variants])
    return rows_b, rows_a


def auroc(x, y, groups, folds: int, seed: int):
    """Out-of-fold AUROC of a balanced logistic regression, folds grouped by document."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    x, y = np.asarray(x, dtype=float), np.asarray(y)
    score = np.zeros(len(y))
    splitter = GroupKFold(n_splits=min(folds, len(set(groups))))
    for train, test in splitter.split(x, y, groups):
        if len(set(y[train])) < 2:
            score[test] = float(y[train][0])          # a fold with one class predicts it
            continue
        model = make_pipeline(StandardScaler(),
                              LogisticRegression(max_iter=1000, class_weight="balanced",
                                                 random_state=seed))
        model.fit(x[train], y[train])
        score[test] = model.predict_proba(x[test])[:, 1]
    return float(roc_auc_score(y, score))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(CORPORA))
    ap.add_argument("--sources", type=Path, required=True)
    ap.add_argument("--variants", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--key-file", type=Path,
                    default=Path.home() / ".config" / "pseudonymkit" / "hmac.key")
    ap.add_argument("--entity-type", default="PERSON")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-class", type=int, default=10)
    args = ap.parse_args()

    from build_BC import inventory_for, read_key

    documents = list(iter_documents(CORPORA[args.corpus]()))
    languages = {d.language for d in documents}
    cache = DetectorCache(args.cache, args.corpus)
    pool_names = sorted(p.stem.replace("__", "/") for p in cache.root.glob("*.jsonl"))
    log(f"{args.corpus}: {len(documents):,} documents, {len(pool_names)} detectors")
    # sweep_leakage.main, step for step: one inventory pinned over the union of every detector.
    union_detected, _ = detected_documents(documents, cache, pool_names, "union")
    cover = {(m.type, d.language) for d in union_detected for m in d.mentions}
    inventory, _ = inventory_for(languages, documents=union_detected, cover=cover)
    del union_detected
    key = read_key(args.key_file)
    pool = generator_pool(inventory, languages)
    frequencies = population(args.corpus, args.entity_type)
    log(f"  generator pools {len(pool):,} surfaces; public name lists {len(frequencies):,} tokens")

    variants = json.loads(args.variants.read_text())
    names = sorted(variants)
    attackers = {v: attacker_spans(documents, cache, variants[v]) for v in names}
    log(f"  attacker variants: {', '.join(names)}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.out.exists():
        done = {json.loads(line)["source"] for line in args.out.open() if line.strip()}
    wanted = [line for line in args.sources.read_text().split() if line and line not in done]
    log(f"  {len(wanted)} span sources to do, {len(done)} already done")

    with args.out.open("a", buffering=1) as handle:
        for n, label in enumerate(wanted, 1):
            started = time.time()
            ensemble, rule, kwargs = parse_label(label)
            row: dict = {"source": label, "corpus": args.corpus, "variants": variants,
                         "artefact_features": list(ARTEFACTS)}
            try:
                detected, _ = detected_documents(documents, cache, list(ensemble), rule=rule,
                                                 rule_kwargs=kwargs)
                patches = construct(detected, corpus=args.corpus, conditions=("B",),
                                    inventory=inventory, key=key)
                del detected
                release = to_pseudonymised_corpus(documents, patches["B"], check=False)
                occurrences = [o for o in label_occurrences(release, documents, args.entity_type)
                               if o.label in ("surrogate", "survivor")]
                y = [1 if o.label == "surrogate" else 0 for o in occurrences]
                row.update(surrogates=sum(y), survivors=len(y) - sum(y),
                           survivor_entities=len({o.entity for o in occurrences
                                                  if o.label == "survivor"}))
                if min(row["surrogates"], row["survivors"]) < args.min_class:
                    row["auroc_note"] = (f"fewer than {args.min_class} spans in one class "
                                         f"({row['surrogates']} surrogates, {row['survivors']} "
                                         f"survivors): no AUROC")
                else:
                    rows_b, rows_a = features(occurrences, pool, frequencies, names, attackers,
                                              args.entity_type)
                    groups = [o.doc_id for o in occurrences]
                    row["auroc_artefacts"] = auroc(rows_b, y, groups, args.folds, args.seed)
                    for i, v in enumerate(names):
                        col = [[a[i]] for a in rows_a]
                        row[f"auroc_error_{v}"] = auroc(col, y, groups, args.folds, args.seed)
                        both = [b + [a[i]] for b, a in zip(rows_b, rows_a)]
                        row[f"auroc_both_{v}"] = auroc(both, y, groups, args.folds, args.seed)
                        row[f"tagged_surrogates_{v}"] = sum(a[i] for a, t in zip(rows_a, y) if t)
                        row[f"tagged_survivors_{v}"] = sum(a[i] for a, t in zip(rows_a, y)
                                                           if not t)
            except Exception as error:                 # recorded, never silently skipped (§1)
                row["error"] = f"{type(error).__name__}: {error}"
            row["seconds"] = round(time.time() - started, 1)
            handle.write(json.dumps(row) + "\n")
            if n % 10 == 0 or n == len(wanted):
                log(f"  {n}/{len(wanted)}  last {row['seconds']}s  "
                    f"{'ERROR ' + row['error'][:80] if 'error' in row else ''}")
    log(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
