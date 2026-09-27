#!/usr/bin/env python3
'''Split a corpus's span sources into balanced shards for a Slurm array.

AM, 2026-09-27: "Much of it can run in parallel. I think about 200 in each job is fine."

The labels are taken from the DETECTION sweep (results/detection/<corpus>.jsonl, field `detector`)
rather than re-enumerated here. Two reasons: the detection row and the leakage row then share a join
key by construction, which is the whole point of the operating-point paper; and a re-enumeration
that drifted from the one that produced the detection sweep would be invisible until the join
silently lost rows.

`gold` is excluded. It is a first-class detector name inside `detected_documents`, but it is not a
cache file, so the sweep's coverage check has no entry for it; the perfect-detection point is run
separately once that is confirmed rather than risking an array task on it.

Balancing: cost per source runs with the number of replacements, so union-of-three is dear and
intersection is cheap, and the detection file is ordered by subset size. Round-robin assignment
(label i -> shard i % n) therefore spreads dear and cheap evenly, where contiguous blocks would put
all the dear ones in one job.

    python experiments/shard_sweep_sources.py --corpus enron --shards 11
'''
import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--shards', type=int, default=11)
    ap.add_argument('--detection', type=Path, default=Path('results/detection'))
    ap.add_argument('--out', type=Path, default=Path('results/leakage_sweep/shards'))
    ap.add_argument('--entity-type', default='PERSON')
    ap.add_argument('--carry-done', action='store_true',
                    help='seed each new shard destination with rows already computed for its '
                         'labels, gathered from every existing shard. Re-sharding otherwise '
                         'orphans finished work: the sweep resumes from its OWN destination, so a '
                         'label that moves to a different shard is silently recomputed.')
    args = ap.parse_args()

    source = args.detection / f'{args.corpus}.jsonl'
    labels = []
    for line in source.open():
        label = json.loads(line)['detector']
        if label == 'gold':
            continue
        labels.append(label)
    if len(labels) != len(set(labels)):
        raise SystemExit('duplicate labels in the detection sweep; refusing to shard')

    done: dict[str, str] = {}
    if args.carry_done:
        name = f'{args.corpus}_{args.entity_type}.jsonl'
        for old in sorted(args.out.glob(f'*/{name}')):
            for line in old.open():
                row = json.loads(line)
                if not row.get('error'):
                    done[row['source']] = line if line.endswith('\n') else line + '\n'
        print(f'carrying {len(done)} finished span sources across the re-shard')

    args.out.mkdir(parents=True, exist_ok=True)
    shards = [[] for _ in range(args.shards)]
    for i, label in enumerate(labels):
        shards[i % args.shards].append(label)

    carried = 0
    for i, shard in enumerate(shards):
        path = args.out / f'{args.corpus}_{i:02d}.txt'
        path.write_text('\n'.join(shard) + '\n')
        if args.carry_done:
            destination = args.out / f'{i:02d}' / f'{args.corpus}_{args.entity_type}.jsonl'
            destination.parent.mkdir(parents=True, exist_ok=True)
            rows = [done[label] for label in shard if label in done]
            destination.write_text(''.join(rows))
            carried += len(rows)
            print(f'{path}  {len(shard)} sources, {len(rows)} already done')
        else:
            print(f'{path}  {len(shard)} sources')
    if args.carry_done:
        print(f'seeded {carried} finished rows into the new destinations')
    print(f'total {len(labels)} sources over {args.shards} shards '
          f'(gold excluded, run separately)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
