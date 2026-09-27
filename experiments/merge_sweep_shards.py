#!/usr/bin/env python3
'''Join the Slurm array's per-shard leakage rows into the canonical sweep file.

Refuses to write if a span source appears twice with different content, and refuses to drop rows
that are already in the destination but in no shard -- on Enron those are the four recommended-13
rules, which were run by hand under the corrected gold and are not part of the 2,150.

    python experiments/merge_sweep_shards.py --corpus enron
'''
import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--entity-type', default='PERSON')
    ap.add_argument('--shards', type=Path, default=Path('results/leakage_sweep/shards'))
    ap.add_argument('--out', type=Path, default=Path('results/leakage_sweep'))
    ap.add_argument('--write', action='store_true', help='without this it only reports')
    args = ap.parse_args()

    name = f'{args.corpus}_{args.entity_type}.jsonl'
    rows: dict[str, dict] = {}
    errors = []

    destination = args.out / name
    kept = 0
    if destination.exists():
        for line in destination.open():
            row = json.loads(line)
            rows[row['source']] = row
            kept += 1
        print(f'existing {destination}: {kept} rows kept as the base')

    for shard in sorted(args.shards.glob(f'*/{name}')):
        n = seen = 0
        for line in shard.open():
            row = json.loads(line)
            n += 1
            if row.get('error'):
                errors.append((shard.parent.name, row['source'], row['error']))
                continue
            previous = rows.get(row['source'])
            if previous is not None and previous != row and previous.get('size') != 13:
                raise SystemExit(f'conflicting rows for {row["source"]} in {shard}')
            if row['source'] not in rows:
                seen += 1
            rows[row['source']] = row
        print(f'{shard.parent.name}: {n} rows, {seen} new')

    if errors:
        print(f'\n{len(errors)} error rows -- these span sources did NOT produce a measurement:')
        for shard, source, message in errors[:20]:
            print(f'  [{shard}] {source}: {str(message)[:110]}')
        if len(errors) > 20:
            print(f'  ... and {len(errors) - 20} more')

    print(f'\ntotal {len(rows)} span sources')
    if not args.write:
        print('dry run: pass --write to replace the canonical file')
        return 0

    backup = destination.with_suffix('.jsonl.premerge')
    if destination.exists():
        backup.write_text(destination.read_text())
        print(f'previous file kept at {backup}')
    with destination.open('w', encoding='utf-8') as handle:
        for source in sorted(rows):
            handle.write(json.dumps(rows[source]) + '\n')
    print(f'wrote {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
