#!/usr/bin/env python3
"""Fit and freeze the linear utility instruments (plan §8.5), once, on condition A.

AM, 2026-09-29: utility moves from zero-shot gateway scorers to TF-IDF plus logistic regression.
This script is the whole of the "trained once" half — everything downstream loads the pickled
artefact and never fits again.

    . config/env.sh
    python experiments/train_linear_tasks.py --corpus cardiode
    python experiments/train_linear_tasks.py --corpus enron

Three instruments, each on the corpus that carries its gold:

    cardiode  section_classification   14 derived section types, one label per section
    cardiode  medication_ie             9 medication classes, a BIO tagger scored by span F1
    enron     folder_classification     the mailbox folder, one label per message

**Nothing is fitted on a document it will later score.** The split is document-disjoint and seeded
(``split_documents``), the training half is used for fitting and the scoring half is recorded in
the artefact so every condition is scored on exactly the same documents. Fitting and scoring the
same text would measure memorisation and would read as a utility loss under B and C that the
pseudonymisation did not cause. :mod:`pseudonymkit.tasks.linear` states the reasoning in full.

**The held-out condition-A score is the point of the run, not a by-product.** §8.3: *"If the frozen
model is near chance on the original, that task's numbers are uninterpretable."* Paper 1 had to drop
``medication_ie:in_narrative`` for exactly that reason, after the run rather than before it. Every
artefact here prints its held-out score beside the chance rate, and a task that does not clear
chance is reported as unusable rather than scored at 2,154 operating points.

Nothing is written outside ``--out``; no gateway, no GPU, no network.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')

from pseudonymkit.adapters.cardiode import (
    MEDICATION_CLASSES,
    SECTION_TYPES,
    derive_sections,
)
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.tasks.linear import (
    save_artefact,
    split_documents,
    train_single_label_classifier,
    train_span_tagger,
)
from run_utility import SOURCES

T0 = time.time()

TASKS_FOR = {
    'cardiode': ('section_classification', 'medication_ie'),
    'enron': ('folder_classification',),
}
"""Which instrument each corpus can carry. Driven by the gold the adapter produces, not by choice:
CARDIO:DE has section headings and medication spans, Enron has ``X-Folder``. TAB and OntoNotes carry
neither and are out of this paper (plan §4) — they keep ``ner_agreement``, which needs no training.
"""


def log(message: str) -> None:
    print(f'[{time.time() - T0:7.1f}s] {message}', flush=True)


def commit() -> str:
    """The commit every result row has to carry (§13). Unknown is recorded, never guessed."""
    try:
        out = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True)
        dirty = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        return out.stdout.strip()[:12] + ('+dirty' if dirty.stdout.strip() else '')
    except Exception:
        return 'unknown'


def section_units(documents, train_ids, score_ids):
    """Section texts and their gold types, keyed ``<doc_id>#<index>``.

    The unit is the section because that is what the runner classifies: ``section_classification``
    extends each heading to the next and asks for one label per derived section, then scores the
    letter by the fraction it got right. Fitting on whole letters would fit a different task from
    the one being measured.
    """
    texts: dict[str, str] = {}
    labels: dict[str, str] = {}
    keys: dict[str, list[str]] = {'train': [], 'score': []}
    train, score = set(train_ids), set(score_ids)
    for document in documents:
        headings = document.task.get('sections', ())
        sections = derive_sections(headings, len(document.text))
        if not sections:
            continue
        half = 'train' if document.doc_id in train else 'score' if document.doc_id in score else ''
        if not half:
            continue
        for index, section in enumerate(sections):
            key = f'{document.doc_id}#{index}'
            texts[key] = document.text[section.start:section.end]
            labels[key] = section.section_type
            keys[half].append(key)
    return texts, labels, keys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', required=True, choices=sorted(TASKS_FOR))
    ap.add_argument('--tasks', nargs='+', default=None,
                    help='default: every instrument the corpus can carry')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--train-fraction', type=float, default=0.5)
    ap.add_argument('--limit', type=int, default=0, help='documents, for a smoke run')
    ap.add_argument('--out', type=Path, default=Path('results/instruments'))
    args = ap.parse_args()

    documents = list(iter_documents(SOURCES[args.corpus][0]()))
    if args.limit:
        documents = documents[: args.limit]
    log(f'{args.corpus}: {len(documents):,} condition-A documents')

    train_ids, score_ids = split_documents(
        [d.doc_id for d in documents], seed=args.seed, train_fraction=args.train_fraction)
    log(f'  split seed={args.seed}: {len(train_ids):,} train / {len(score_ids):,} score, '
        f'document-disjoint')

    by_id = {d.doc_id: d for d in documents}
    args.out.mkdir(parents=True, exist_ok=True)
    summary = []

    for task in (args.tasks or TASKS_FOR[args.corpus]):
        started = time.time()
        log(f'=== {task} ===')

        if task == 'section_classification':
            texts, labels, keys = section_units(documents, train_ids, score_ids)
            log(f'  {len(keys["train"]):,} training sections, {len(keys["score"]):,} to score')
            artefact = train_single_label_classifier(
                texts, labels, task_name=task, train_ids=keys['train'], score_ids=keys['score'],
                corpus=args.corpus, seed=args.seed,
                record_ids=(train_ids, score_ids),
            )
            offered = len(SECTION_TYPES)

        elif task == 'folder_classification':
            texts = {d.doc_id: d.text for d in documents}
            labels = {d.doc_id: str(d.task.get('label') or '') for d in documents}
            present = sorted({v for v in labels.values() if v})
            log(f'  {len(present):,} distinct folders over {len(texts):,} messages')
            artefact = train_single_label_classifier(
                texts, labels, task_name=task, train_ids=train_ids, score_ids=score_ids,
                corpus=args.corpus, seed=args.seed,
            )
            offered = len(present)

        elif task == 'medication_ie':
            texts = {d.doc_id: d.text for d in documents}
            spans = {
                d.doc_id: [(m.start, m.end, m.class_type)
                           for m in d.task.get('medications', ())
                           if m.class_type in set(MEDICATION_CLASSES)]
                for d in documents
            }
            carrying = sum(1 for v in spans.values() if v)
            log(f'  {carrying:,} of {len(texts):,} letters carry a medication span')
            artefact = train_span_tagger(
                texts, spans, train_ids=train_ids, score_ids=score_ids, corpus=args.corpus,
                classes=list(MEDICATION_CLASSES), seed=args.seed,
            )
            offered = len(MEDICATION_CLASSES)

        else:
            raise SystemExit(f'unknown task {task!r}')

        chance = float(artefact.metadata.get('chance') or 0.0)
        verdict = ('USABLE' if artefact.holdout_score > max(chance * 2, 0.05)
                   else 'NEAR CHANCE — do not score the plane with this (§8.3)')
        log(f'  held-out condition A: {artefact.holdout_score:.4f}  '
            f'(chance {chance:.4f}, {offered} classes) — {verdict}')
        log(f'  fitted in {time.time() - started:.0f}s')

        path = save_artefact(artefact, args.out / f'{args.corpus}_{task}.pkl')
        log(f'  wrote {path} and {path.with_suffix(".json").name}')
        summary.append({
            'task': task, 'scorer': artefact.scorer.name,
            'holdout_condition_a': artefact.holdout_score, 'chance': chance,
            'usable': verdict == 'USABLE',
            'trained_on': len(artefact.train_doc_ids), 'scored_on': len(artefact.score_doc_ids),
        })

    index = args.out / f'{args.corpus}_instruments.json'
    index.write_text(json.dumps({
        'corpus': args.corpus, 'seed': args.seed, 'train_fraction': args.train_fraction,
        'documents': len(documents), 'commit': commit(), 'instruments': summary,
    }, indent=1), encoding='utf-8')
    log(f'wrote {index}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
