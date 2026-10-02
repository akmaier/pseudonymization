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

CLASS_WEIGHT = {
    'section_classification': 'balanced',
    'folder_classification': None,
}
"""Per-task class weighting for the two classifiers, measured rather than chosen.

Balanced is right for the fourteen section types: the head is only 12.3 % of sections, so an
unweighted fit has little head to learn and balancing costs nothing — it scores 0.9605. It is wrong
for the 176 Enron folders. Measured 2026-10-02: balanced gives held-out accuracy **0.2028 against a
majority-class baseline of 0.2621**, an instrument worse than answering "All documents" every time,
which §8.3 says cannot measure a loss. 32 of the 176 labels hold a single message and balancing
hands each of them the weight of a class holding 15,464.

The span tagger is not here. Its classes are BIO tags over tokens, where ``O`` is the overwhelming
majority by construction rather than by the corpus, so balancing is not a judgement call and is
fixed inside :func:`pseudonymkit.tasks.linear.train_span_tagger`.
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
    ap.add_argument('--class-weight', default=None, choices=['balanced', 'none'],
                    help='default: per task — balanced for the 14 section types, unweighted for '
                         "Enron's 176 folders, whose tail sinks a balanced fit below its own "
                         'majority-class baseline. See tasks.linear.')
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
        weight = (None if args.class_weight == 'none' else args.class_weight) \
            if args.class_weight else CLASS_WEIGHT.get(task, 'balanced')
        log(f'=== {task} ===' + (f' (class_weight={weight!r})'
                                 if task in CLASS_WEIGHT else ''))

        if task == 'section_classification':
            texts, labels, keys = section_units(documents, train_ids, score_ids)
            log(f'  {len(keys["train"]):,} training sections, {len(keys["score"]):,} to score')
            artefact = train_single_label_classifier(
                texts, labels, task_name=task, train_ids=keys['train'], score_ids=keys['score'],
                corpus=args.corpus, seed=args.seed, class_weight=weight,
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
                corpus=args.corpus, seed=args.seed, class_weight=weight,
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

        # §8.3's test is "near chance on the original text", and for a skewed label set the rate a
        # scorer gets for free is the majority class, not 1/k. A tagger has neither: it is judged
        # against the gateway extractor it replaces.
        chance = artefact.metadata.get('chance')
        floor = float(artefact.metadata.get('majority_baseline') or 0.0)
        reference = max(floor, float(chance or 0.0), 0.05)
        verdict = ('USABLE' if artefact.holdout_score > reference
                   else 'AT OR BELOW THE FREE BASELINE — cannot measure a loss (§8.3)')
        if chance is None:
            log(f'  held-out condition A: {artefact.holdout_score:.4f} span F1  '
                f'({offered} classes; exact-match F1 has no free baseline) — {verdict}')
        else:
            log(f'  held-out condition A: {artefact.holdout_score:.4f}  '
                f'(uniform chance {float(chance):.4f}, majority class {floor:.4f}, '
                f'{offered} classes) — {verdict}')
        log(f'  fitted in {time.time() - started:.0f}s')

        path = save_artefact(artefact, args.out / f'{args.corpus}_{task}.pkl')
        log(f'  wrote {path} and {path.with_suffix(".json").name}')
        summary.append({
            'task': task, 'scorer': artefact.scorer.name,
            'holdout_condition_a': artefact.holdout_score,
            'uniform_chance': chance, 'majority_baseline': floor,
            'class_weight': weight if task in CLASS_WEIGHT else 'balanced (fixed, BIO)',
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
