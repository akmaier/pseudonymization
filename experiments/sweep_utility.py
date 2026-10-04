#!/usr/bin/env python3
"""Utility at every operating point, conditions B and C — plan §8.5 and §10.

`sweep_leakage.py` says in its own docstring that this is *"affordable where a utility sweep is
not"*, because a utility sweep *"re-runs frozen models over every conditioned text"*. That was
true of the gateway scorers and it is why utility was measured at four named points in the first
paper. It stopped being true on 2026-09-29, when AM replaced them with TF-IDF and logistic
regression: scoring a CARDIO:DE letter is now a sparse matrix-vector product rather than a network
round trip, so the plane is reachable.

    . config/env.sh
    python experiments/train_linear_tasks.py --corpus cardiode     # once, first
    python experiments/sweep_utility.py --corpus cardiode

What one row is: one span source, both released conditions, every task the corpus carries, with
the **per-document score vector** kept rather than only its mean. §8.3 makes the vector the
primary artefact, and a paired test at a primary cell (§9.5) has nothing to pair without it. A
binary task is stored as a bit per document, which is exact and keeps Enron's rows at kilobytes.

**Condition A is scored once per corpus, not once per point.** Nothing is replaced there, so the
text is the same whatever the detector did; it is the ceiling every B and C score is read against
and it is written as its own row. This is the same reasoning `run_a4_sample.py` applies to A4.

**The scored documents are the instrument's held-out half and nothing else.** The artefact records
which documents it was fitted on; scoring those would measure memorisation. The same held-out set
is used in A, B and C, so the pairing survives (see :mod:`pseudonymkit.tasks.linear`).

**The surrogate inventory is pinned across the plane** (plan §6): it is compiled once from the
union over every detector, exactly as `sweep_leakage.py` does, so an entity receives the same
surrogate whatever the operating point replaced. Without that, two points would differ by their
inventories as well as by their detection, and the plane would not be one experiment.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')

from pseudonymkit.conditions import Unmodified
from pseudonymkit.construction import construct, detected_documents, to_pseudonymised_corpus
from pseudonymkit.engine import PseudonymisedCorpus
from pseudonymkit.tasks.linear import CrossFit
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.domain import Corpus
from pseudonymkit.metrics.detection import prepare, score_prepared
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.tasks import (
    folder_classification,
    label_set,
    load_artefact,
    medication_ie,
    section_classification,
)
from sweep_leakage import CORPORA, is_llm, plan

T0 = time.time()

TASKS_FOR = {
    'cardiode': ('section_classification', 'medication_ie'),
    'enron': ('folder_classification',),
}
"""The instruments each corpus carries, matching `train_linear_tasks.TASKS_FOR`.

`ner_agreement` is deliberately absent. It re-detects with Presidio per document — 351,816 calls
per Enron point (plan §10 item 7) — and §8.5 restricts it to comparisons *between operating points
within one condition* anyway. It is not a plane-wide instrument and pretending otherwise would put
eleven days of spaCy startup into every shard.
"""

BINARY = frozenset({'folder_classification'})
"""Tasks whose per-document score is 0 or 1, stored as a bitstring rather than a float list."""


def log(message: str) -> None:
    print(f'[{time.time() - T0:8.1f}s] {message}', flush=True)


def commit() -> str:
    try:
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True)
        dirty = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        return head.stdout.strip()[:12] + ('+dirty' if dirty.stdout.strip() else '')
    except Exception:
        return 'unknown'


def pack(task: str, doc_ids, scores) -> dict[str, object]:
    """One task's per-document vector, compactly.

    Binary tasks become a hex bitstring over the row's own ``doc_ids`` order — 29,318 Enron
    documents are 3.7 kB that way against 150 kB as a float list, and nothing is lost because the
    score is 0 or 1. Continuous scores are rounded to four places, which is below the resolution
    of any difference the statistics will test and keeps a row readable.
    """
    doc_ids = list(doc_ids)
    scores = list(scores)
    out: dict[str, object] = {'n': len(scores), 'mean': (sum(scores) / len(scores)) if scores else None}
    if task in BINARY:
        bits = 0
        for index, score in enumerate(scores):
            if score >= 0.5:
                bits |= 1 << index
        out['bits'] = format(bits, 'x')
    else:
        out['scores'] = [round(float(s), 4) for s in scores]
    return out


def _run_task(task: str, result, condition: str, scorer, labels) -> dict:
    """One task over one conditioned corpus with one estimator: ``{vector name: ScoreVector}``."""
    if task == 'section_classification':
        return {task: section_classification(result, scorer, condition=condition)}
    if task == 'medication_ie':
        return medication_ie(result, scorer, condition=condition)
    if task == 'folder_classification':
        return {task: folder_classification(result, scorer, condition=condition, labels=labels)}
    raise SystemExit(f'unknown task {task!r}')


def score_all(result, condition: str, instruments: dict, labels) -> dict[str, dict]:
    """Every task the corpus carries, over one conditioned corpus.

    A cross-fitted instrument (AM, 2026-10-03) is scored fold by fold: each fold's documents are
    handed to the estimator that was fitted without them, and the per-document scores are joined
    into one vector. That costs one pass, because every estimator scores only its own fold, and it
    is the reason a document is never scored by a model that saw it.
    """
    out: dict[str, dict] = {}
    for task, artefact in instruments.items():
        scorer = artefact.scorer
        if isinstance(scorer, CrossFit):
            parts: dict[str, tuple[list, list]] = {}
            for fold, members in enumerate(scorer.folds):
                wanted = set(members)
                subset = PseudonymisedCorpus(
                    documents=tuple(d for d in result.documents
                                    if d.document.doc_id in wanted),
                    mapping=result.mapping)
                if not subset.documents:
                    continue
                for key, vector in _run_task(task, subset, condition,
                                             scorer.scorer_for(fold), labels).items():
                    ids, scores = parts.setdefault(key, ([], []))
                    ids.extend(vector.doc_ids)
                    scores.extend(vector.scores)
            for key, (ids, scores) in parts.items():
                order = sorted(range(len(ids)), key=ids.__getitem__)
                out[key] = pack(key, [ids[i] for i in order], [scores[i] for i in order])
        else:
            for key, vector in _run_task(task, result, condition, scorer, labels).items():
                out[key] = pack(key, vector.doc_ids, vector.scores)
    return out


def released(documents, patchset):
    """Every scored document in its released form, in corpus order.

    ``to_pseudonymised_corpus`` omits a document with no patch, and ``detected_documents`` emits no
    document at all when none of the ensemble's detectors has a usable record for it — a single
    detector whose reply for that letter was dropped as truncated, say. For an attack that is
    harmless, since such a document carries no replaced mention to query. For utility it was a
    selection bias: the first run of this sweep scored 234 of its 4,300 rows on fewer letters than
    condition A, down to 41 of 193, and compared those means with the full ceiling. Detection
    scoring already counts such a document as "found nothing", so utility releases it unchanged.
    """
    patched = to_pseudonymised_corpus(documents, patchset, check=False)
    have = {d.document.doc_id: d for d in patched.documents}
    missing = [d for d in documents if d.doc_id not in have]
    if missing:
        for d in Unmodified().pseudonymise_corpus(missing).documents:
            have[d.document.doc_id] = d
    return (PseudonymisedCorpus(documents=tuple(have[d.doc_id] for d in documents),
                                mapping=patched.mapping), len(missing))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', required=True, choices=sorted(TASKS_FOR))
    ap.add_argument('--cache', type=Path, default=Path('results/detector_cache'))
    ap.add_argument('--artefacts', type=Path, default=Path('results/instruments'))
    ap.add_argument('--key-file', type=Path,
                    default=Path.home() / '.config' / 'pseudonymkit' / 'hmac.key',
                    help='the same default sweep_leakage.py and build_BC.py use: one key for '
                         'the whole study, or two points carry different surrogates for one '
                         'entity and the plane stops being one experiment')
    ap.add_argument('--max-size', type=int, default=3)
    ap.add_argument('--sources', type=Path, default=None,
                    help='a file of span-source labels, one per line — the shard this task runs')
    ap.add_argument('--conditions', nargs='+', default=['B', 'C'])
    ap.add_argument('--out', type=Path, default=Path('results/utility_sweep'))
    ap.add_argument('--shard', default=None, help="this writer's own output file suffix")
    ap.add_argument('--shard-index', type=int, default=0)
    ap.add_argument('--shard-of', type=int, default=1,
                    help='round-robin over the plan order rather than contiguous blocks: the '
                         'cost of a span source rises with its size, so contiguous blocks would '
                         'give the last task every triple and the first every singleton')
    ap.add_argument('--limit-points', type=int, default=0, help='cap span sources, for a smoke run')
    ap.add_argument('--min-coverage', type=float, default=0.99,
                    help='drop a detector whose cache covers less than this fraction of the '
                         'corpus, before the enumeration rather than after it')
    ap.add_argument('--restart', action='store_true')
    args = ap.parse_args()

    from build_BC import inventory_for, read_key

    instruments = {}
    for task in TASKS_FOR[args.corpus]:
        path = args.artefacts / f'{args.corpus}_{task}.pkl'
        if not path.exists():
            raise SystemExit(f'no frozen instrument at {path} — run train_linear_tasks.py first')
        artefact = load_artefact(path)
        instruments[task] = artefact
        log(f'{task}: {artefact.scorer.name}, held-out condition A '
            f'{artefact.holdout_score:.4f}, scores {len(artefact.score_doc_ids)} documents')

    # **Union, not intersection.** Each runner already skips a document its task has no gold for
    # -- a letter with no medication span, a message with no folder -- and counts the skip. Taking
    # the intersection would instead drop those documents from the tasks that *can* score them,
    # so section classification would be measured on a different set from the one its artefact
    # reports a held-out score for.
    held_out = set().union(*(set(a.score_doc_ids) for a in instruments.values()))
    log(f'  scoring {len(held_out)} held-out documents, the union over the instruments')

    all_documents = list(iter_documents(CORPORA[args.corpus]()))
    documents = [d for d in all_documents if d.doc_id in held_out]
    if len(documents) != len(held_out):
        raise SystemExit(f'the artefacts name {len(held_out)} held-out documents but the corpus '
                         f'carries {len(documents)} of them — the artefact and the corpus disagree')
    corpus = Corpus(args.corpus, tuple(documents))
    log(f'{args.corpus}: {len(all_documents)} documents, {len(documents)} scored')

    key = read_key(args.key_file)
    cache = DetectorCache(args.cache, args.corpus)
    pool = sorted(p.stem.replace('__', '/') for p in cache.root.glob('*.jsonl'))

    # **A partial detector is dropped from the pool, not from the rows.** The leakage sweep applies
    # its coverage floor per span source, which is right when the pool is fixed; here the pool is
    # also what `plan` enumerates over, so a sixteenth detector with a half-written cache would
    # change the plane from 2,154 labels into a different and larger set that no leakage row joins
    # to. It would also enter the pinned inventory. DeepSeek is exactly this case on CARDIO:DE
    # today: 337 of 400 documents, most of them truncated.
    coverage = {name: len(set(cache.digests(name))) / max(len(all_documents), 1) for name in pool}
    detectors = [name for name in pool if coverage[name] >= args.min_coverage]
    for name in pool:
        if name not in detectors:
            log(f'  EXCLUDED from the pool: {name} covers {coverage[name]:.1%} of the corpus, '
                f'below --min-coverage {args.min_coverage}. Reported, not substituted (§1): '
                f'finish its detection and re-run to include it.')
    log(f'  detectors {len(detectors)} of {len(pool)} '
        f'({sum(1 for d in detectors if is_llm(d))} LLM)')

    # The pinned inventory, compiled over the union of every detector on the **whole** corpus, not
    # on the scored half: a surrogate pool drawn from half the documents would be a different pool,
    # and the plan pins one inventory for the plane (§6).
    union_detected, _ = detected_documents(all_documents, cache, detectors, 'union')
    cover = {(m.type, d.language) for d in union_detected for m in d.mentions}
    inventory, _ = inventory_for({d.language for d in all_documents},
                                 documents=union_detected, cover=cover)
    log(f'  inventory pinned over {len(cover)} (type, language) pairs')
    del union_detected

    index = prepare(documents, corpus=args.corpus)
    labels = tuple(label_set(Unmodified().pseudonymise_corpus(documents))) \
        if 'folder_classification' in instruments else ()
    if labels:
        log(f'  folder label set fixed at {len(labels)} labels, from condition A')

    args.out.mkdir(parents=True, exist_ok=True)
    shard = args.shard or (f'{args.shard_index:02d}of{args.shard_of:02d}'
                           if args.shard_of > 1 else 'all')
    destination = args.out / f'{args.corpus}.{shard}.jsonl'
    done: set[str] = set()
    if destination.exists() and not args.restart:
        for line in destination.open(encoding='utf-8'):
            try:
                done.add(json.loads(line)['source'])
            except Exception:
                continue
        log(f'  resuming: {len(done)} span sources already on disk')

    stamp = {'corpus': args.corpus, 'commit': commit(),
             'scorers': {t: a.scorer.name for t, a in instruments.items()},
             'scored_documents': len(documents)}

    handle = destination.open('a' if done else 'w', encoding='utf-8', buffering=1)

    # Condition A once. Nothing is replaced, so the text does not depend on the operating point.
    if 'A' not in done:
        started = time.time()
        ceiling = Unmodified().pseudonymise_corpus(documents)
        row = {**stamp, 'source': 'A', 'condition': 'A', 'role': 'ceiling',
               'tasks': score_all(ceiling, 'A', instruments, labels),
               'seconds': round(time.time() - started, 1)}
        handle.write(json.dumps(row) + '\n')
        os.fsync(handle.fileno())
        done.add('A')
        for task, packed in row['tasks'].items():
            log(f'  condition A  {task:28s} mean {packed["mean"]:.4f} over {packed["n"]} documents')

    # `plan` is the leakage sweep's own enumeration, reused verbatim so the two sweeps address the
    # identical 2,154 span sources under the identical labels and their rows join.
    if args.sources:
        wanted = {line.strip() for line in args.sources.read_text().splitlines() if line.strip()}
        # `plan` parses any wanted label the size-bounded enumeration did not reach — the
        # recommended thirteen is one — so a shard can name an ensemble of any size.
        sources = plan(detectors, args.max_size, wanted, [])
        missing = wanted - {label for *_, label in sources}
        if missing:
            log(f'  {len(missing)} shard labels are not span sources of this pool — REPORTED, '
                f'not skipped silently: {sorted(missing)[:3]}')
    else:
        sources = plan(detectors, args.max_size, None, [])
    if args.shard_of > 1:
        sources = [s for index, s in enumerate(sources)
                   if index % args.shard_of == args.shard_index]
        log(f'  shard {args.shard_index + 1}/{args.shard_of}: {len(sources)} span sources')
    if args.limit_points:
        sources = sources[: args.limit_points]
    todo = [s for s in sources if s[3] not in done]
    log(f'  {len(sources)} span sources in this shard, {len(todo)} to do')

    failures = 0
    for position, (names, rule, kwargs, label) in enumerate(todo, 1):
        started = time.time()
        try:
            detected, _ = detected_documents(documents, cache, list(names),
                                             rule=rule, rule_kwargs=kwargs)
            spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}
            detection = score_prepared(index, spans, detector=label).as_dict()
            del spans
            patches = construct(detected, corpus=args.corpus,
                                conditions=tuple(args.conditions), inventory=inventory, key=key)
            del detected
            for condition in args.conditions:
                result, unchanged = released(documents, patches[condition])
                row = {
                    **stamp, 'source': label, 'condition': condition, 'rule': rule,
                    'size': len(names),
                    'token_recall': detection['token_recall'],
                    'precision': detection['precision'],
                    'replacements': sum(len(p.entries) for p in patches[condition].patches),
                    'released_unchanged': unchanged,
                    'tasks': score_all(result, condition, instruments, labels),
                    'seconds': round(time.time() - started, 1),
                }
                handle.write(json.dumps(row) + '\n')
                del result
            os.fsync(handle.fileno())
        except Exception as error:                 # recorded, never silently skipped (§1)
            failures += 1
            handle.write(json.dumps({**stamp, 'source': label,
                                     'error': f'{type(error).__name__}: {error}'}) + '\n')
            os.fsync(handle.fileno())
            log(f'  [{position}/{len(todo)}] {label[:60]}: FAILED — {type(error).__name__}: '
                f'{str(error)[:140]}')
            continue
        if position % 5 == 0 or position == len(todo):
            rate = position / max(time.time() - T0, 1e-9)
            log(f'  [{position}/{len(todo)}] {rate * 60:.2f} sources/min, '
                f'eta {(len(todo) - position) / rate / 3600:.1f}h, {failures} failed')

    handle.close()
    log(f'wrote {destination} ({failures} failed)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
