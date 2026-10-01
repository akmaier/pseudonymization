#!/usr/bin/env python3
'''Merge the per-writer A4 files, dropping corrupt lines and reporting them.

Two Slurm jobs appended to one shared file on 2026-10-01 and interleaved mid-line. The writers now
each own a file; this joins them, keyed on (model, condition, source), and says what it had to
discard rather than quietly skipping it.
'''
import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--dir', type=Path, default=Path('results/phase1'))
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    rows, corrupt, duplicate = {}, 0, 0
    sources = sorted(args.dir.glob(f'{args.corpus}_a4_llm*.jsonl'))
    for path in sources:
        if path.name.endswith('.merged.jsonl'):
            continue
        n = bad = 0
        for line in path.open():
            try:
                row = json.loads(line)
            except ValueError:
                bad += 1
                continue
            key = (row['model'], row['condition'], row.get('source') or 'A')
            if key in rows:
                duplicate += 1
            rows[key] = row
            n += 1
        corrupt += bad
        print(f'  {path.name}: {n} rows, {bad} corrupt')
    print(f'\n{len(rows)} distinct cells, {corrupt} corrupt lines dropped, '
          f'{duplicate} duplicates collapsed')
    models = sorted({k[0] for k in rows})
    for model in models:
        print(f'    {model[:44]:44s} {sum(1 for k in rows if k[0] == model):3d} cells')
    if not args.write:
        print('dry run: pass --write')
        return 0
    dest = args.dir / f'{args.corpus}_a4_llm.merged.jsonl'
    with dest.open('w') as handle:
        for key in sorted(rows):
            handle.write(json.dumps(rows[key]) + '\n')
    print(f'wrote {dest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
