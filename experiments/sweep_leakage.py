#!/usr/bin/env python3
"""Leakage recomputed at every recall level — H1 and H5 (§6).

§6 does not ask for leakage under one ensemble.  **H1** is *"comparing every detector and every
combination rule against the gold-span oracle, with leakage recomputed at each recall level"*, and
**H5** is *"comparing every LLMs-only subset against the same subset plus one classical detector"*.
Both are statements about the *ensemble axis*, and neither is answerable from a single union run.

This is affordable where a utility sweep is not.  Utility re-runs frozen models over every
conditioned text; leakage is set arithmetic, a cosine and a small numpy fit.  So condition B is
constructed **in memory** for each span source, attacked, and thrown away — 2,151 patch sets would
be 50 GB on disk and are not worth keeping when the rates are what the paper reports.

Each row carries the detection numbers **and** the leakage numbers for the same span source, which is
what makes "leakage at each recall level" a single table rather than a join across two files.

    . config/env.sh
    python experiments/sweep_leakage.py --corpus cardiode --max-size 3

Rows land in ``results/leakage_sweep/<corpus>.jsonl``, one per (span source, rule), resumable.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import statistics
import pathlib
import sys
import time
from pathlib import Path

from pseudonymkit.attacks import (
    FrequencyAttack,
    Prior,
    degrade,
    observe,
    LearnedLinkage,
    StructuralLinkage,
    build_gallery,
    build_queries,
    disjoint_document_split,
    truth_map,
)
from pseudonymkit.conditions import Unmodified
from pseudonymkit.construction import construct, detected_documents, to_pseudonymised_corpus
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.domain import Corpus
from pseudonymkit.metrics.detection import prepare, score_prepared
from pseudonymkit.paths import cardiode_a, condition_a_dir
from pseudonymkit.serialisation import iter_documents

CORPORA = {
    "cardiode": cardiode_a,
    "tab": lambda: condition_a_dir() / "tab_A.jsonl.gz",
    "ontonotes": lambda: condition_a_dir() / "ontonotes_A.jsonl.gz",
    "enron": lambda: condition_a_dir() / "enron_A.jsonl.gz",
}

CLASSICAL = ("presidio", "privacy_tagger", "gliner:", "hf:")
"""Prefixes of the non-LLM levels of axis D.  H5 asks what adding one of these to an LLMs-only
subset buys, so the two families have to be distinguishable by name."""

RULES: tuple[tuple[str, dict], ...] = (
    ("union", {}), ("intersection", {}), ("vote", {"k": 2}), ("vote", {"k": 3}),
)


def log(message: str, t0: float = time.time()) -> None:
    print(f"[{time.time() - t0:8.1f}s] {message}", flush=True)


def is_llm(name: str) -> bool:
    return name.startswith("llm:")


def relational_identity(corpus, entity_type, gallery_docs, query_docs) -> tuple[bool, str]:
    """Whether A3 and A5 have a denominator on this corpus, and why.

    Both attacks link a query mention to a *profile of the same person built from other documents*.
    That needs an identity the corpus asserts across documents.  Enron has one — the e-mail address —
    and CARDIO:DE has one because §12.1 constructs recurring patients and a recurring physician pool.

    TAB and OntoNotes do not.  Their co-reference is document-scoped by construction: every gold
    entity id is prefixed with the document it came from, so **no entity appears in two documents**
    (checked: 0 of 8,701 in TAB, 0 of 13,230 in OntoNotes).  After
    :func:`disjoint_document_split`, no query's true identity is in the gallery at all.

    Run anyway, the attacks return Rank-1 = 0 for every span source *and for condition A*, and a
    reader of that table would conclude that pseudonymisation defeats structural linkage on TAB.  It
    does not; the attack was never possible.  §2 says report faithfully, so this returns the reason
    and the caller writes ``null`` with the reason attached rather than a zero that means something
    else.  :mod:`experiments/run_stability` gives drift the same treatment for the same reason.
    """
    gallery_ids, query_ids = set(), set()
    for doc in corpus:
        if doc.doc_id in gallery_docs:
            target = gallery_ids
        elif doc.doc_id in query_docs:
            target = query_ids
        else:
            continue
        target.update(m.gold_entity_id for m in doc.mentions
                      if m.type == entity_type and m.gold_entity_id)
    shared = gallery_ids & query_ids
    if shared:
        return True, (f"{len(shared)} {entity_type} identities appear on both sides of the "
                      f"document-disjoint split")
    return False, (f"no {entity_type} identity appears in both the gallery and the query half of "
                   f"the document-disjoint split ({len(gallery_ids)} and {len(query_ids)} "
                   f"identities, 0 shared) — co-reference in this corpus is document-scoped, so a "
                   f"cross-document linkage attack has no true match to find")


def subsets(detectors: list[str], max_size: int):
    for size in range(1, max_size + 1):
        yield from itertools.combinations(detectors, size)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(CORPORA))
    ap.add_argument("--include", type=Path, default=None,
                    help="file of '+'-joined ensembles to score under every rule regardless of "
                         "--max-size; use it to add the large ensemble to a full sweep")
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--out", type=Path, default=Path("results/leakage_sweep"))
    ap.add_argument("--max-size", type=int, default=3)
    ap.add_argument("--entity-type", default="PERSON")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--key-file", type=Path,
                    default=Path.home() / ".config" / "pseudonymkit" / "hmac.key")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sources", type=Path, default=None,
                    help="file of span-source labels to run, one per line; everything else is "
                         "skipped. Enron uses this — the full enumeration is 1,743 sources at ~257 s "
                         "each, and experiments/enron_candidates.py picks the promising ones")
    ap.add_argument("--fail-fast", type=int, default=25,
                    help="abort if the first N span sources all fail; 0 disables")
    ap.add_argument("--min-coverage", type=float, default=0.99,
                    help="skip a span source whose members jointly cover less than this fraction "
                         "of the corpus, rather than attacking a condition built by a different "
                         "operator on part of it")
    ap.add_argument("--restart", action="store_true")
    args = ap.parse_args()

    sys.path.insert(0, "experiments")
    from build_BC import inventory_for, read_key

    documents = list(iter_documents(CORPORA[args.corpus]()))
    if args.limit:
        documents = documents[: args.limit]
    corpus = Corpus(args.corpus, tuple(documents))
    key = read_key(args.key_file)
    cache_for_inventory = DetectorCache(args.cache, args.corpus)
    detectors_all = sorted(path.stem.replace("__", "/")
                           for path in cache_for_inventory.root.glob("*.jsonl"))
    log(f"{args.corpus}: {len(documents)} documents, entity type {args.entity_type}")

    # **The inventory must cover what any span source might replace, not what the gold contains.**
    # The sweep builds condition B for every subset of the pool, so the union over all detectors is
    # the superset of everything that can turn up. The gold is not: on Enron it is header-derived and
    # carries no ORG at all, which is how 334 of the first 336 rows came back as
    # ``LookupError: no surrogates for type='ORG'``. Compiling from the union-detected documents also
    # gives the attested pools the richest evidence available, and costs one extra combine.
    union_detected, _ = detected_documents(documents, cache_for_inventory, detectors_all, "union")
    cover = {(m.type, d.language) for d in union_detected for m in d.mentions}
    log(f"  inventory must cover {len(cover)} (type, language) pairs seen under union")
    inventory, _ = inventory_for({d.language for d in documents},
                                 documents=union_detected, cover=cover)
    index = prepare(documents, corpus=args.corpus)
    gallery_docs, query_docs = disjoint_document_split(corpus, seed=args.seed)
    gallery = build_gallery(corpus, args.entity_type, documents=gallery_docs)
    log(f"  gallery {len(gallery)} profiles; document-disjoint split "
        f"{len(gallery_docs)}/{len(query_docs)}")

    relational, why = relational_identity(corpus, args.entity_type, set(gallery_docs),
                                          set(query_docs))
    log(f"  A3/A5 {'computable' if relational else 'NOT COMPUTABLE'}: {why}")

    # Condition A once: the ceiling every row is read against (§8.4).
    a3_ceiling_rank1 = None
    if relational:
        ceiling = Unmodified().pseudonymise_corpus(documents)
        a_queries = build_queries(ceiling, args.entity_type, documents=query_docs)
        a_truth = truth_map(ceiling, args.entity_type)
        a3_ceiling = StructuralLinkage().run(a_queries, gallery, a_truth, "deterministic", "hmac")
        a3_ceiling_rank1 = a3_ceiling.rank1
        log(f"  ceiling A3 on condition A: Rank-1 {a3_ceiling.rank1:.3f}")
    else:
        log("  skipping the condition-A ceiling: it would be 0 for the same structural reason, "
            "which is not a measurement of anything")

    cache = DetectorCache(args.cache, args.corpus)
    detectors = sorted(p.stem.replace("__", "/") for p in cache.root.glob("*.jsonl"))
    log(f"  detectors {len(detectors)} ({sum(1 for d in detectors if is_llm(d))} LLM)")

    # **The same coverage floor the detection sweep uses, for the same reason.** A subset is scored
    # over the documents its members jointly cover; where a member has no record the combinator
    # silently drops it, so `vote(k=2)` over the two present out of three becomes an intersection
    # and the row is labelled with an ensemble it was not measured with. On Enron that would be
    # every subset containing Qwen3.6, which is still detecting.
    covered = {name: set(cache.digests(name)) for name in detectors}
    for name, ids in sorted(covered.items()):
        if len(ids) < len(documents):
            log(f"    PARTIAL {name}: {len(ids)}/{len(documents)} documents "
                f"({len(ids) / max(len(documents), 1):.1%})")

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"{args.corpus}_{args.entity_type}.jsonl"
    done: set[str] = set()
    if destination.exists() and not args.restart:
        for line in destination.open(encoding="utf-8"):
            try:
                done.add(json.loads(line)["source"])
            except Exception:
                continue
        log(f"  resuming: {len(done)} span sources already done")

    extra: list[tuple[str, ...]] = []
    wanted: set[str] | None = None

    if args.sources:
        wanted = {line.strip() for line in args.sources.read_text(encoding="utf-8").splitlines()
                  if line.strip()}
        log(f"  restricted to {len(wanted)} span sources from {args.sources}")
    if args.include:
        extra = [tuple(line.strip().split("+")) for line in
                 args.include.read_text(encoding="utf-8").splitlines() if line.strip()]
        log(f"  plus {len(extra)} explicitly included ensembles "
            f"(sizes {sorted({len(e) for e in extra})}) from {args.include}")

    written = 0
    errored = 0
    skipped: list[tuple[str, int]] = []
    started = time.time()
    with destination.open("a" if done else "w", encoding="utf-8", buffering=1) as handle:
        for names, rule, kwargs, label in plan(detectors, args.max_size, wanted, extra):
            k = kwargs.get("k")
            if True:
                if label in done:
                    continue
                shared = set.intersection(*(covered[n] for n in names))
                fraction = len(shared) / max(len(documents), 1)
                if fraction < args.min_coverage:
                    skipped.append((label, len(shared)))
                    continue
                try:
                    row = _one(names, rule, kwargs, label, documents, cache, index, inventory,
                               key, gallery, query_docs, args, relational)
                except Exception as exc:          # recorded, never silently skipped (§1)
                    row = {"source": label, "error": f"{type(exc).__name__}: {exc}"}
                row.update(corpus=args.corpus, entity_type=args.entity_type, size=len(names),
                           rule=rule if len(names) > 1 else "single", k=k,
                           ensemble=list(names),
                           llms_only=all(is_llm(n) for n in names),
                           classical=[n for n in names if not is_llm(n)],
                           a3_ceiling_rank1=a3_ceiling_rank1,
                           relational_computable=relational,
                           relational_note=None if relational else why)
                handle.write(json.dumps(row) + "\n")
                os.fsync(handle.fileno())
                written += 1
                errored += "error" in row
                # **Stop if nothing is working.** Enron's first run wrote 336 rows over four hours
                # and every one of them was the same LookupError, because the surrogate inventory
                # was missing a pool the detectors needed. The driver's own progress lines looked
                # healthy throughout — they count rows, and an error is a row. A sweep whose first
                # `--fail-fast` results are *all* failures is misconfigured, not unlucky, and the
                # cheapest thing it can do is say so before spending the allocation.
                if args.fail_fast and written >= args.fail_fast and errored == written:
                    raise SystemExit(
                        f"aborting: all {written} span sources so far failed. Last error: "
                        f"{row.get('error')}\nThis is a configuration fault, not a run of bad "
                        f"luck — fix it and restart with --restart, since an error row carries a "
                        f"source and would otherwise count as done on resume."
                    )
                if written % 20 == 0:
                    rate = written / max(time.time() - started, 1e-9)
                    log(f"  {written} sources  {rate * 3600:.0f}/h")
    log(f"wrote {written} rows to {destination}")
    if skipped:
        log(f"  SKIPPED {len(skipped)} span sources below --min-coverage {args.min_coverage}:")
        for label, n in skipped[:10]:
            log(f"    {label}  {n}/{len(documents)} documents shared")
        if len(skipped) > 10:
            log(f"    ... and {len(skipped) - 10} more")
        log("  not dropped cells: finish detection for the members above and re-run; the resume "
            "adds exactly these rows (§1).")
    return 0


def parse_label(label: str):
    """``a+b+c|vote2`` -> ``(("a","b","c"), "vote", {"k": 2})``.

    The inverse of the label the sweep writes, so a source file can name an ensemble the size-bounded
    enumeration would never reach.
    """
    ensemble, _, rule = label.rpartition("|")
    if not ensemble:
        raise ValueError(f"not a span-source label: {label!r}")
    digits = ""
    while rule and rule[-1].isdigit():
        digits = rule[-1] + digits
        rule = rule[:-1]
    kwargs = {"k": int(digits)} if digits else {}
    return tuple(ensemble.split("+")), rule, kwargs


def plan(detectors: list[str], max_size: int, wanted, extra):
    """Every (ensemble, rule) this run should score, in a stable order.

    The size-bounded enumeration first, then anything named explicitly that it did not reach — a
    large ensemble asked for by name is run rather than silently filtered out of a set it was never
    in.
    """
    seen: set[str] = set()
    out = []

    def add(names, rule, kwargs):
        k = kwargs.get("k")
        if len(names) == 1 and rule != "union":
            return
        if k is not None and k > len(names):
            return
        label = f"{'+'.join(names)}|{rule}{k or ''}"
        if label in seen:
            return
        seen.add(label)
        if wanted is not None and label not in wanted:
            return
        out.append((tuple(names), rule, kwargs, label))

    for names in subsets(detectors, max_size):
        for rule, kwargs in RULES:
            add(names, rule, kwargs)

    # Explicitly named ensembles, whatever their size.
    for names in extra:
        for rule, kwargs in RULES:
            add(names, rule, kwargs)
    if wanted is not None:
        for label in sorted(wanted):
            if label in seen:
                continue
            try:
                names, rule, kwargs = parse_label(label)
            except ValueError:
                continue
            unknown = [n for n in names if n not in detectors]
            if unknown:
                print(f"  requested source names detectors that are not in the pool: {unknown}",
                      flush=True)
                continue
            seen.add(label)
            out.append((names, rule, kwargs, label))
    return out


def attack_truth_tables(result, entity_type: str):
    """Evaluator-side tables, exposed so the sweep can build them once per span source."""
    from pseudonymkit.attacks.frequency import _truth_tables

    return _truth_tables(result, entity_type)


def external_priors(corpus: str, entity_type: str):
    """The public name lists an adversary attacking this corpus could actually look up.

    Absent rather than substituted where none exists: a corpus whose language has no list on disk
    reports that the realistic adversary is not measurable, which is a result about our evidence
    and not a reason to quote the upper bound in its place (§1).
    """
    from pseudonymkit.attacks.priors import (
        build_prior, load_census_surnames, load_german_weights, load_uci_given_names,
    )
    from pseudonymkit.paths import shared_corpora

    out = []
    gazetteers = shared_corpora() / "gazetteers"
    try:
        if corpus in ("tab", "ontonotes", "enron"):
            surnames = load_census_surnames(gazetteers / "Names_2010Census.csv")
            out.append(build_prior(surnames, entity_type, label="US Census 2010 surnames",
                                   provenance="US Census 2010, 162,253 surnames covering 90 % of "
                                              "those recorded; public domain under 17 U.S.C. 105",
                                   vintage="2010"))
            given = load_uci_given_names(gazetteers / "name_gender_dataset.csv")
            out.append(build_prior(given, entity_type, label="UCI given names",
                                   provenance="UCI Gender by Name, CC BY 4.0, "
                                              "DOI 10.24432/C55G7X",
                                   vintage="1880-2019"))
        elif corpus == "cardiode":
            weights = pathlib.Path("data/cardiode_name_weights.json")
            out.append(build_prior(load_german_weights(weights, "family"), entity_type,
                                   label="German surnames",
                                   provenance="abydos rank order x US Census 2010 counts — a US "
                                              "Zipf shape on German ranks, not German counts",
                                   vintage="2010"))
            for part, cohort in (("male", "1930-1969"), ("female", "1930-1969")):
                out.append(build_prior(load_german_weights(weights, part), entity_type,
                                       label=f"German given names ({part})",
                                       provenance="Stadt Bielefeld Einwohnermelderegister, "
                                                  "CC BY 4.0",
                                       vintage=cohort))
    except FileNotFoundError as exc:
        # Report, do not substitute.
        print(f"  no external prior for {corpus}: {exc}", flush=True)
        return []
    return out


def _one(names, rule, kwargs, label, documents, cache, index, inventory, key,
         gallery, query_docs, args, relational: bool) -> dict:
    """Detection and leakage for one span source, condition B built and discarded in memory."""
    detected, report = detected_documents(
        documents, cache, list(names), rule=rule, rule_kwargs=kwargs
    )
    spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}
    detection = score_prepared(index, spans, detector=label).as_dict()

    patches = construct(detected, corpus=args.corpus, conditions=("B",),
                        inventory=inventory, key=key)
    # **The gold-bearing documents, not the detected ones.** `detected` carries the detector's spans
    # as its mentions, so it has no gold_entity_id to inherit and A3/A5 come back with no truth at
    # all — which is what the first run of this sweep produced. The patch offsets address condition-A
    # text either way, so the originals are the right thing to rebuild against.
    result = to_pseudonymised_corpus(documents, patches["B"], check=False)

    row = {
        "source": label,
        "token_recall": detection["token_recall"],
        "entity_recall": detection["entity_recall"],
        "precision": detection["precision"],
        "information_weighted_precision": detection["information_weighted_precision"],
        "replacements": sum(len(p.entries) for p in patches["B"].patches),
        "documents_missing_a_detector": report.get("documents_missing_a_detector"),
    }

    # **Two priors over one observation** (AM, 2026-09-22). The attacker's view of the release is
    # computed once; what changes between cells is only what the adversary is assumed to know.
    # The oracle is kept because a scheme safe under it is safe in practice, and it is labelled an
    # upper bound in its own fields so it can never be read as a risk estimate.
    # The adversary's view of this release: its own tagger's counts, and the evaluator-side tables
    # that say what stands behind each surface. Computed once, shared by every prior and every
    # abstention threshold below.
    seen = observe(result)
    tables = attack_truth_tables(result, args.entity_type)
    internal = Prior.corpus_internal(result, args.entity_type)
    # phi = 0: the attacker always answers. The headline, because every positive threshold refuses
    # essentially every query on a one-dimensional frequency signal (measured, 2026-09-22).
    oracle = FrequencyAttack(internal, eccentricity=0.0)
    a2 = oracle.run(result, args.entity_type, "deterministic", "hmac")
    bound = oracle.score(result, args.entity_type, observed=seen, tables=tables)
    row.update(a2_top1=a2.accuracy_top1, a2_top5=a2.accuracy_top5, a2_rho=a2.rank_correlation,
               a2_candidates=a2.candidates, a2_bands=dict(a2.by_frequency_band))
    row.update({f"a2_bound_{k}": v for k, v in bound.as_dict().items()})

    # The realistic adversary, and the Bindschaedler prior-quality sweep around it: one cell per
    # (list, size, vintage). Reported per cell rather than averaged — the point is how attack
    # strength varies with what the adversary knows, which an average would erase.
    cells = []
    available = external_priors(args.corpus, args.entity_type)
    for prior in available:
        for top in (100, 1_000, 10_000, None):
            if top is not None and top >= prior.size:
                continue
            cell = FrequencyAttack(degrade(prior, top=top), eccentricity=0.0).score(
                result, args.entity_type, observed=seen, tables=tables)
            cells.append(cell.as_dict())

    # The abstention curve, on the full-size priors only. Both numbers PAN asks for are already in
    # each cell (`accuracy_attempted` blind, `c_at_1` rewarding); what this adds is how both move as
    # the attacker is allowed to be more cautious.
    curve = []
    for label, prior in [("corpus-internal", internal)] + [(p.label, p) for p in available]:
        for phi in (0.0, 0.05, 0.25, 1.5):
            cell = FrequencyAttack(prior, eccentricity=phi).score(
                result, args.entity_type, observed=seen, tables=tables)
            curve.append({"prior": label, "phi": phi, "attempted": cell.attempted,
                          "abstained": cell.abstained,
                          "accuracy_attempted": cell.accuracy_attempted,
                          "c_at_1": cell.c_at_1, "lift_over_chance": cell.lift_over_chance})
    row["a2_abstention_curve"] = curve
    if cells:
        row["a2_prior_sweep"] = cells
        # The full-size external prior is the headline realistic number.
        best = max(cells, key=lambda c: c.get("prior_size") or 0)
        row.update({f"a2_real_{k}": v for k, v in best.items()})
    else:
        row["a2_prior_sweep"] = []
        row["a2_real_note"] = ("no external name-frequency list for this corpus — the realistic "
                               "adversary is not measurable here and the bound is not a substitute")

    queries = build_queries(result, args.entity_type, documents=query_docs)
    truth = truth_map(result, args.entity_type)
    # `relational` is a property of the corpus, not of this span source: where co-reference is
    # document-scoped the gallery and the queries share no identity, so A3 and A5 would report zero
    # for every row including the condition-A ceiling.  The fields are left absent rather than set
    # to a zero that would read as "the attack failed".
    if relational and queries and truth:
        structural = StructuralLinkage()
        # The whole-corpus A3, as reported before 2026-09-22 — kept so the change is auditable.
        a3 = structural.run(queries, gallery, truth, "deterministic", "hmac")
        row.update(a3_rank1=a3.rank1, a3_rank5=a3.rank5, a3_map=a3.mean_average_precision,
                   a3_queries=a3.queries, a3_gallery=a3.gallery)

        # One partition, handed to both attacks. A3 sees the same held-out queries A5 is tested on
        # and the same undiminished gallery; the fold withholds labels from the learner and nothing
        # else (AM, 2026-09-22).
        partition = structural.folds(queries, gallery, truth, seed=args.seed, folds=args.folds)
        a3_folds = [
            structural.run(queries, gallery, truth, "deterministic", "hmac", subset=keys)
            for keys in partition
        ]
        a5_folds = [
            LearnedLinkage(seed=args.seed, folds=args.folds, fold=f).run(
                queries, gallery, truth, "deterministic", "hmac")
            for f in range(args.folds)
        ]

        def summarise(results, prefix):
            """Mean, spread and the raw per-fold values, for each metric.

            ``None`` rather than ``0.0`` where a single fold cannot have a spread: a measured-looking
            zero is worse than an absent number.
            """
            out = {f"{prefix}_folds": len(results)}
            for name, get in (("rank1", lambda r: r.rank1),
                              ("rank5", lambda r: r.rank5),
                              ("map", lambda r: r.mean_average_precision)):
                values = [get(r) for r in results]
                out[f"{prefix}_{name}"] = statistics.fmean(values)
                out[f"{prefix}_{name}_sd"] = (
                    statistics.stdev(values) if len(values) > 1 else None)
                out[f"{prefix}_{name}_values"] = values
            out[f"{prefix}_queries_values"] = [r.queries for r in results]
            out[f"{prefix}_gallery_values"] = [r.gallery for r in results]
            return out

        row.update(summarise(a3_folds, "a3f"))
        row.update(summarise(a5_folds, "a5"))
        # The paired difference, fold by fold — what "learning buys" actually means once both
        # attacks face the same problem. Only defined because the folds are matched.
        gap = [b.rank1 - a.rank1 for a, b in zip(a3_folds, a5_folds)]
        row.update(
            a5_minus_a3_rank1=statistics.fmean(gap),
            a5_minus_a3_rank1_sd=statistics.stdev(gap) if len(gap) > 1 else None,
            a5_minus_a3_rank1_values=gap,
            a5_seed=args.seed,
            fold_paradigm="labels-held-out; full gallery at evaluation (AM 2026-09-22)",
        )
    return row


if __name__ == "__main__":
    sys.exit(main())
