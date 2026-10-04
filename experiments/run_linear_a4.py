#!/usr/bin/env python3
'''A4's statistical twin at the pre-registered sample points (plan §8.5b, §8.5c).

Per (corpus, point, condition): rebuild the release from its patch set, assemble the same A4
candidate items the LLM will see, split entities disjointly, fit TF-IDF + logistic regression on
the training half of the RELEASED text, and score Rank-1 on the held-out half.

Never trained on condition A (AM, 2026-09-29): that is the defender's original text and no
attacker has it. Condition A is run once as the ceiling only.

The tag is derived exactly as build_BC derives it -- sha256 over the detector names joined with
\\x1f -- and CARDIO:DE patch sets are read from the DUA root, not the shared tree. Reconstructing
either by hand produced a false "nothing was built" on 2026-09-30.
'''
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')

from pseudonymkit.attacks.candidates import build_items, score
from pseudonymkit.attacks.linear_ranker import split_entities, train_linear_ranker
from pseudonymkit.construction import (check_current, read_patchset,
                                       to_pseudonymised_corpus)
from pseudonymkit.domain import Corpus
from pseudonymkit.serialisation import iter_documents
from run_leakage import SOURCES
from sweep_leakage import CORPORA


def tag_for(label: str) -> str:
    ensemble, _, rule = label.rpartition('|')
    k = ''
    while rule and rule[-1].isdigit():
        k, rule = rule[-1] + k, rule[:-1]
    names = sorted(ensemble.split('+'))
    fingerprint = hashlib.sha256('\x1f'.join(names).encode('utf-8')).hexdigest()[:6]
    return f'{rule}{k}-single0.5-{len(names)}det-{fingerprint}'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--n-candidates', type=int, default=10)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--limit', type=int, default=0, help='cap points, for a smoke run')
    ap.add_argument('--out', type=Path, default=Path('results/phase1'))
    args = ap.parse_args()

    documents = list(iter_documents(CORPORA[args.corpus]()))
    corpus = Corpus(args.corpus, tuple(documents))
    root = SOURCES[args.corpus][1]()
    sample = json.loads(
        Path(f'results/phase1/{args.corpus}_a4_sample.json').read_text())['sample']
    if args.limit:
        sample = sample[: args.limit]
    print(f'{args.corpus}: {len(documents):,} documents, {len(sample)} points, '
          f'patch sets under {root.name}/', flush=True)

    rows, missing = [], 0
    for n, point in enumerate(sample, 1):
        tag = tag_for(point['source'])
        for condition in ('B', 'C'):
            path = root / f'{args.corpus}_{condition}_{tag}.patch.jsonl'
            if not path.exists():
                print(f'  [{n}] {condition} {tag}: NO PATCH SET', flush=True)
                missing += 1
                continue
            patchset = read_patchset(path)
            # check_current RAISES when a patch set is stale and otherwise returns a report that
            # is always non-empty. Treating the report as the failure signal discarded every
            # healthy patch set -- six of six on the first smoke run.
            try:
                check_current(documents, patchset)
            except Exception as error:
                print(f'  [{n}] {condition} {tag}: STALE against condition A — {error}',
                      flush=True)
                missing += 1
                continue
            released = to_pseudonymised_corpus(documents, patchset, check=False)
            items = build_items(released, corpus, n_candidates=args.n_candidates,
                                seed=args.seed)
            train, test = split_entities(items, seed=args.seed)
            if len(train) < 20 or len(test) < 20:
                print(f'  [{n}] {condition} {tag}: {len(items)} items, too few to split',
                      flush=True)
                continue
            try:
                ranker = train_linear_ranker(train, seed=args.seed)
            except ValueError as error:
                print(f'  [{n}] {condition} {tag}: cannot train — {error}', flush=True)
                continue
            result = score(test, ranker, condition=condition)
            row = {'source': point['source'], 'role': point['role'], 'condition': condition,
                   'tag': tag, 'ranker': ranker.name, 'items': len(items),
                   'train': len(train), 'test': len(test),
                   'rank1': result.overall.rank1, 'rank5': result.overall.rank5,
                   'map': result.overall.mean_average_precision, 'n_candidates': result.n_candidates,
                   'chance': 1.0 / max(result.n_candidates, 1),
                   # Same outcome classes and per-query record as the LLM rows (§8.4, §9.5), so
                   # the twin pairs with them query by query. No name or text is written (§15).
                   'outcome_counts': result.outcome_counts(),
                   'per_query': result.per_query()}
            rows.append(row)
            print(f'  [{n}/{len(sample)}] {condition} {point["role"][:22]:22s} '
                  f'Rank-1 {result.overall.rank1:.4f} (chance {row["chance"]:.3f}) '
                  f'on {len(test)} held-out items', flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    dest = args.out / f'{args.corpus}_linear_a4.jsonl'
    with dest.open('w') as handle:
        for row in rows:
            handle.write(json.dumps(row) + '\n')
    print(f'\nwrote {dest}: {len(rows)} cells, {missing} without a usable patch set')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
