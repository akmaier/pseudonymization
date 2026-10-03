#!/usr/bin/env python3
"""Find a feature set that makes a utility instrument able to measure a loss at all (§8.3).

AM, 2026-10-03: *"Enron utility: try a stronger baseline."*

Why this exists. §8.3 refuses a scorer that is near chance on the original text, because it cannot
then show a loss under B or C. Enron's folder task failed that test twice: with
``class_weight='balanced'`` the out-of-sample accuracy was **0.2028** and unweighted **0.2530**,
against a majority-class baseline of **0.2621** — both below the rate of answering "All documents"
every time. The first fit was word unigrams with default regularisation, which is a thin feature
set for e-mail: a folder is signalled by addresses, signature blocks, quoted headers and spellings
that a word tokeniser shatters.

    . config/env.sh
    python experiments/tune_instrument.py --corpus enron --task folder_classification

**The selection is made on condition A alone.** Every configuration is scored out of sample on
unmodified text and nothing here ever reads condition B or C. That is what keeps it instrument
selection rather than fitting to the result: the comparison the paper makes is between conditions
at a fixed instrument, and choosing the instrument by its ceiling does not touch that comparison.

**One fold, not five.** This is a search, so it uses a single held-out fold — fit on the other
*k−1*, score that one. The winner is then cross-fitted properly by ``train_linear_tasks.py``, which
is where the artefact comes from. Searching with full cross-fitting would cost *k* times as much to
answer the same question.

Nothing is written outside ``--out``; no gateway, no GPU, no network.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')

from pseudonymkit.serialisation import iter_documents
from pseudonymkit.tasks.linear import Features, split_folds, train_single_label_classifier
from run_utility import SOURCES
from train_linear_tasks import section_units

T0 = time.time()

# **Ordered cheapest first**, so a run that is killed on the wall clock still has the comparison
# against the configuration it is trying to beat. Each entry is (label, Features, C).
GRID: tuple[tuple[str, Features, float], ...] = (
    ('word 1-gram, C=1  [the one that failed]', Features(), 1.0),
    ('word 1-gram, C=10', Features(), 10.0),
    ('word 1-2gram, C=1', Features(word_ngrams=(1, 2)), 1.0),
    ('word 1-2gram, C=10', Features(word_ngrams=(1, 2)), 10.0),
    ('word 1-gram + char_wb 3-5, C=1', Features(char_ngrams=(3, 5)), 1.0),
    ('word 1-2gram + char_wb 3-5, C=10', Features(word_ngrams=(1, 2), char_ngrams=(3, 5)), 10.0),
    ('word 1-2gram + char_wb 3-5, C=10, 500k features',
     Features(word_ngrams=(1, 2), char_ngrams=(3, 5), max_features=500_000), 10.0),
)


def log(message: str) -> None:
    print(f'[{time.time() - T0:8.1f}s] {message}', flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', required=True, choices=sorted(SOURCES))
    ap.add_argument('--task', required=True,
                    choices=['folder_classification', 'section_classification'])
    ap.add_argument('--folds', type=int, default=5)
    ap.add_argument('--fold', type=int, default=0, help='which fold is held out for the search')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--class-weight', default='none', choices=['balanced', 'none'])
    ap.add_argument('--limit', type=int, default=0, help='documents, for a smoke run')
    ap.add_argument('--out', type=Path, default=Path('results/instruments'))
    args = ap.parse_args()

    weight = None if args.class_weight == 'none' else args.class_weight
    documents = list(iter_documents(SOURCES[args.corpus][0]()))
    if args.limit:
        documents = documents[: args.limit]
    folds = split_folds([d.doc_id for d in documents], k=args.folds, seed=args.seed)
    held = folds[args.fold]
    rest = [d for index, fold in enumerate(folds) if index != args.fold for d in fold]
    log(f'{args.corpus}/{args.task}: {len(documents):,} documents, '
        f'fold {args.fold} of {args.folds} held out ({len(held):,} documents), '
        f'class_weight={weight!r}')

    if args.task == 'folder_classification':
        texts = {d.doc_id: d.text for d in documents}
        labels = {d.doc_id: str(d.task.get('label') or '') for d in documents}
        train_ids, score_ids, record = rest, list(held), None
    else:
        texts, labels, keys = section_units(documents, rest, list(held))
        train_ids, score_ids = keys['train'], keys['score']
        record = (tuple(rest), tuple(held))
    log(f'  {len(train_ids):,} training units, {len(score_ids):,} to score, '
        f'{len({v for v in labels.values() if v}):,} labels')

    results = []
    best = None
    for label, features, regularisation in GRID:
        started = time.time()
        try:
            artefact = train_single_label_classifier(
                texts, labels, task_name=args.task, train_ids=train_ids, score_ids=score_ids,
                corpus=args.corpus, seed=args.seed, features=features,
                regularisation=regularisation, class_weight=weight, record_ids=record,
            )
        except Exception as error:          # recorded, never silently skipped (§1)
            log(f'  {label:52s} FAILED — {type(error).__name__}: {str(error)[:120]}')
            results.append({'config': label, 'error': f'{type(error).__name__}: {error}'})
            continue
        floor = float(artefact.metadata.get('majority_baseline') or 0.0)
        verdict = 'clears the baseline' if artefact.holdout_score > floor else 'below the baseline'
        log(f'  {label:52s} {artefact.holdout_score:.4f}  (majority {floor:.4f}) '
            f'{verdict}  [{time.time() - started:.0f}s]')
        row = {
            'config': label, 'features': features.describe(), 'regularisation': regularisation,
            'class_weight': weight, 'holdout': artefact.holdout_score,
            'majority_baseline': floor, 'clears_baseline': artefact.holdout_score > floor,
            'labels': artefact.metadata.get('labels'), 'seconds': round(time.time() - started, 1),
        }
        results.append(row)
        if best is None or row['holdout'] > best['holdout']:
            best = row
        # Written after every configuration, so a job killed on the wall clock keeps what it has.
        args.out.mkdir(parents=True, exist_ok=True)
        destination = args.out / f'{args.corpus}_{args.task}_tuning.json'
        destination.write_text(json.dumps({
            'corpus': args.corpus, 'task': args.task, 'fold': args.fold, 'folds': args.folds,
            'seed': args.seed, 'selected_on': 'condition A, out of sample, never B or C',
            'results': results, 'best': best,
        }, indent=1), encoding='utf-8')

    if best is None:
        log('no configuration completed — nothing to select')
        return 1
    log(f'best: {best["config"]} at {best["holdout"]:.4f} against a baseline of '
        f'{best["majority_baseline"]:.4f}')
    if not best['clears_baseline']:
        log('  NONE of the configurations clears its own majority-class baseline. Under §8.3 this '
            'instrument cannot measure a loss, and that is the result to report rather than a '
            'number to improve by changing the task.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
