#!/usr/bin/env python3
'''Choose the four attacker variants of plan §7.4 from a finished detection plane.

  (a) union-13          the recommended ensemble -- misses the least
  (b) union-3           the max-PERSON-sensitivity triple
  (c) balanced          max Youden J = PERSON sensitivity + specificity - 1 (AM, 2026-09-28)
  (d) max-specificity-3 the most specific triple that still catches half the PERSON tokens

(d) carries paper 1's 0.5 recall floor for paper 1's reason: specificity is 1 - FP/negatives, so an
ensemble that predicts almost nothing scores near 1.0 while catching nothing, and as an attacker it
would flag every name-like span in the corpus. Unfloored it is not a detector, it is a constant.
'''
import argparse
import json
from pathlib import Path

CONST = {'cardiode': (120701, 885059), 'enron': (3648256, 15507925)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--plane', type=Path, default=Path('results/detection_filtered'))
    ap.add_argument('--recommended', type=Path,
                    default=Path('results/leakage_sweep/large_ensemble.txt'))
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--floor', type=float, default=0.5)
    args = ap.parse_args()

    gold, total = CONST[args.corpus]
    negatives = total - gold
    rows = []
    for line in (args.plane / f'{args.corpus}.jsonl').open():
        r = json.loads(line)
        person = (r.get('per_type') or {}).get('PERSON')
        if not person or not person[0] or not r.get('precision'):
            continue
        tp_all = r['token_recall'] * gold
        if r['detector'] == 'gold' or r['detector'].startswith('gold|'):
            # Perfect detection trivially maximises Youden's J at 1.0, and the first run of this
            # script duly chose it as the "balanced" ATTACKER. An attacker does not hold the
            # corpus annotations; gold is the defender's left-hand axis end, not an adversary.
            continue
        rows.append({
            'label': r['detector'], 'size': r.get('size'), 'rule': r.get('rule'),
            'sens': person[2] / person[0],
            'spec': 1.0 - (tp_all / r['precision'] - tp_all) / negatives,
        })
    for r in rows:
        r['J'] = r['sens'] + r['spec'] - 1.0
    print(f'{args.corpus}: {len(rows)} scored points')

    recommended = '+'.join(sorted(args.recommended.read_text().strip().split('+'))) + '|union'
    triples_union = [r for r in rows if r['size'] == 3 and r['rule'] == 'union']
    triples = [r for r in rows if r['size'] == 3 and r['sens'] >= args.floor]

    picks = {
        'union13': recommended,
        'union3': max(triples_union, key=lambda r: r['sens'])['label'] if triples_union else None,
        'balanced': max(rows, key=lambda r: r['J'])['label'],
        'maxspec3': max(triples, key=lambda r: r['spec'])['label'] if triples else None,
    }
    by_label = {r['label']: r for r in rows}
    for name, label in picks.items():
        if label is None:
            print(f'  {name:10s} NO CANDIDATE'); continue
        r = by_label.get(label)
        detail = (f"sens {r['sens']:.4f} spec {r['spec']:.4f} J {r['J']:.4f}"
                  if r else 'not in the scored plane (13-detector rules are not enumerated)')
        print(f'  {name:10s} {detail}')
        print(f'             {label[:100]}')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({k: v for k, v in picks.items() if v}, indent=1) + '\n')
    print(f'wrote {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
