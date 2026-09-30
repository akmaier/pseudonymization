#!/usr/bin/env python3
'''Pre-register the operating points at which A4 is run (plan §8.5c).

Written and committed BEFORE any LLM output is seen. Otherwise the multiplicity discipline of
§9.7 comes back in through the sampling: choose the cells after seeing the answers and the
"stratified sample" is a selection of whatever looked interesting.

Stratified on the **worst measured attack rate** over A2, A3 and A5 -- a quantity the leakage
sweep already has at all 2,154 points, so nothing is run to obtain it (AM, 2026-09-30). Deciles,
equal allocation, fixed seed, plus the anchor cells that must be reported regardless.

`gold` is an anchor of the detection axis only and takes no A4 cell: nothing is replaced there, so
there is no B or C release for A4 to attack.
'''
import argparse
import json
import random
from pathlib import Path

CONST = {'cardiode': (120701, 885059), 'enron': (3648256, 15507925)}
A2_KEYS = ('a2_real_accuracy_alignment', 'a2_bound_accuracy_alignment')


def load(corpus: str) -> list[dict]:
    gold, total = CONST[corpus]
    negatives = total - gold
    det = {}
    for line in open(f'results/detection_filtered/{corpus}.jsonl'):
        r = json.loads(line)
        person = (r.get('per_type') or {}).get('PERSON')
        if not person or not person[0] or not r.get('precision'):
            continue
        tp = r['token_recall'] * gold
        det[r['detector']] = (person[2] / person[0],
                              1.0 - (tp / r['precision'] - tp) / negatives)
    space = {}
    for path in sorted(Path('results/phase1').glob(f'{corpus}_[0-9]*.jsonl')):
        for line in path.open():
            r = json.loads(line)
            space[r['source']] = r
    rows = []
    for line in open(f'results/leakage_sweep/{corpus}_PERSON.jsonl'):
        r = json.loads(line)
        if r['source'] == 'gold':
            continue
        sens_spec = det.get(r['source'])
        sp = space.get(r['source'])
        rates = [r[k] for k in ('a3_rank1', 'a5_rank1') if r.get(k) is not None]
        rates += [r[k] for k in A2_KEYS if r.get(k) is not None]
        if not rates or sens_spec is None or sp is None:
            continue
        rows.append({
            'source': r['source'], 'size': r['size'], 'rule': r['rule'],
            'sens': sens_spec[0], 'spec': sens_spec[1],
            'worst_attack': max(rates), 'queries': r.get('a3_queries') or 0,
            'candidate_space': sp['candidate_space'],
            'survivor_entities': sp['survivor_entities'],
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--n', type=int, default=22)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', type=Path, default=Path('results/phase1'))
    args = ap.parse_args()

    rows = load(args.corpus)
    by_label = {r['source']: r for r in rows}
    print(f'{args.corpus}: {len(rows)} points with sensitivity, specificity and an attack rate')

    anchors: dict[str, str] = {}
    safety = Path(f'results/phase1/{args.corpus}_safety.json')
    if safety.exists():
        chosen = json.loads(safety.read_text()).get('selected')
        if chosen:
            anchors[chosen['source']] = 'phase-1 selection'
    for r in rows:
        if r['size'] == 13:
            anchors.setdefault(r['source'], f'recommended 13-detector {r["rule"]}')
    anchors.setdefault(max(rows, key=lambda r: r['sens'])['source'], 'max PERSON sensitivity')
    anchors.setdefault(max(rows, key=lambda r: r['spec'])['source'], 'max specificity')
    print(f'  anchors: {len(anchors)}')

    remaining = [r for r in rows if r['source'] not in anchors]
    remaining.sort(key=lambda r: r['worst_attack'])
    slots = args.n - len(anchors)
    if slots < 0:
        raise SystemExit(f'{len(anchors)} anchors already exceed n={args.n}')
    rng = random.Random(args.seed)
    picked: list[tuple[str, str]] = []
    size = max(len(remaining) // 10, 1)
    deciles = [remaining[i * size:(i + 1) * size] for i in range(10)]
    deciles[-1].extend(remaining[10 * size:])
    for i in range(slots):
        bucket = deciles[i % 10]
        bucket = [r for r in bucket if r['source'] not in dict(picked)]
        if not bucket:
            continue
        picked.append((rng.choice(bucket)['source'], f'decile {i % 10 + 1}'))

    sample = [{'source': label, 'role': role, **by_label[label]}
              for label, role in list(anchors.items()) + picked]
    sample.sort(key=lambda r: r['worst_attack'])
    for r in sample:
        print(f'  {r["role"]:28s} attack {r["worst_attack"] * 100:7.3f}%  '
              f'sens {r["sens"]:.4f} spec {r["spec"]:.4f}  {r["size"]}det {r["rule"]}')

    args.out.mkdir(parents=True, exist_ok=True)
    dest = args.out / f'{args.corpus}_a4_sample.json'
    dest.write_text(json.dumps({
        'corpus': args.corpus, 'n': len(sample), 'seed': args.seed,
        'stratified_on': 'worst measured attack rate over A2, A3 and A5',
        'drawn': 'before any A4 output was seen (plan §8.5c)',
        'conditions': ['B', 'C'], 'condition_a': 'once per corpus, not per point',
        'sample': sample,
    }, indent=1) + '\n')
    print(f'wrote {dest}  ({len(sample)} points -> {len(sample) * 2 + 1} A4 cells)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
