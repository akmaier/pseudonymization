#!/usr/bin/env python3
'''Build B and C at the pre-registered A4 sample points, against ONE pinned inventory.

The inventory is compiled once, from the union over every detector, and reused at every point.
Without that the pools are compiled from whatever THIS rule detected, so a more selective rule
compiles a smaller pool and the same entity receives a different surrogate at a different
operating point -- `build_BC.py` names the confound in its own comments and leaves it to AM. For a
study whose independent variable IS the operating point it has to be closed, or the 22 releases
are not comparable with each other (plan section 6).

Emits the shell commands rather than importing build_BC, so each point is a separate resumable
process and a failure costs one point.
'''
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--sample', type=Path, default=None)
    ap.add_argument('--inventory', type=Path, default=None)
    ap.add_argument('--out', type=Path, default=Path('results/conditions'))
    ap.add_argument('--print', action='store_true', help='show the commands, run nothing')
    args = ap.parse_args()

    sample = json.loads((args.sample or Path(
        f'results/phase1/{args.corpus}_a4_sample.json')).read_text())
    inventory = args.inventory or Path(f'results/conditions/{args.corpus}_inventory.pkl')

    points = sample['sample']
    print(f'{args.corpus}: {len(points)} points -> B and C each, one pinned inventory')

    for n, point in enumerate(points, 1):
        ensemble, _, rule = point['source'].rpartition('|')
        k = ''
        while rule and rule[-1].isdigit():
            k = rule[-1] + k
            rule = rule[:-1]
        cmd = [sys.executable, 'experiments/build_BC.py',
               '--corpus', args.corpus,
               '--detectors', *ensemble.split('+'),
               '--rule', rule,
               '--conditions', 'B', 'C',
               '--out', str(args.out)]
        if k:
            cmd += ['--k', k]
        # The first point compiles the inventory and saves it; every later point pins to it.
        cmd += (['--save-inventory', str(inventory)] if n == 1
                else ['--inventory-from', str(inventory)])
        if args.print:
            print(' '.join(cmd))
            continue
        print(f'[{n}/{len(points)}] {point["role"]}: {len(ensemble.split("+"))}det {rule}{k}',
              flush=True)
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f'  FAILED ({result.returncode}) — continuing; this point has no release')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
