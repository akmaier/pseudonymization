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

    args.out.mkdir(parents=True, exist_ok=True)
    shards = [[] for _ in range(args.shards)]
    for i, label in enumerate(labels):
        shards[i % args.shards].append(label)

    for i, shard in enumerate(shards):
        path = args.out / f'{args.corpus}_{i:02d}.txt'
        path.write_text('\n'.join(shard) + '\n')
        print(f'{path}  {len(shard)} sources')
    print(f'total {len(labels)} sources over {args.shards} shards '
          f'(gold excluded, run separately)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
