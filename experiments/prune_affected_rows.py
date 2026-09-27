#!/usr/bin/env python3
'''Delete only the leakage rows the CODE sanity rule actually changed, and keep the rest.

AM, 2026-09-27: "only affected rows need recomputation ... design the scripts to continue rather
to replace. Then we delete the affected rows and continue the jobs."

The conservative test — "does this span source contain a detector the rule touches?" — condemns
1,697 of the 2,150 Enron sources, because six of the fifteen detectors emit at least one short CODE
span. That is an over-count: a span dropped from one member of an intersection may never have
reached the result, and a vote may be unmoved by losing one voter's stray span.

The exact test is cheap, because detection scoring is set arithmetic with no construction and no
attacks: re-score the detection plane under the rule and compare it, source by source, with the
plane scored without it. A source whose detection row is unchanged produced the identical span set,
so its leakage row is unchanged too and is kept. Everything else is deleted and recomputed.

    # 1. score the detection plane again, with the filter now in force
    python experiments/score_detection.py --corpus enron --out results/detection_filtered
    # 2. see what actually moved, without touching anything
    python experiments/prune_affected_rows.py --corpus enron
    # 3. delete those rows from the shard destinations and resume the array
    python experiments/prune_affected_rows.py --corpus enron --write

Fields that differ only by provenance are ignored: the point is whether the SPANS moved.
'''
import argparse
import json
from pathlib import Path

# Compared field by field. Anything absent from both rows is ignored, so a schema that gains a
# field does not condemn the whole plane.
SPAN_SENSITIVE = (
    'token_recall', 'entity_recall', 'precision', 'information_weighted_precision',
    'predicted_tokens', 'true_positive_tokens', 'gold_tokens', 'protected_entities',
    'documents_missing_a_detector', 'per_type',
)


def load(path: Path, key: str = 'detector') -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in path.open():
        row = json.loads(line)
        rows[row[key]] = row
    return rows


def changed(before: dict, after: dict) -> bool:
    return any(before.get(f) != after.get(f) for f in SPAN_SENSITIVE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--entity-type', default='PERSON')
    ap.add_argument('--before', type=Path, default=Path('results/detection'))
    ap.add_argument('--after', type=Path, default=Path('results/detection_filtered'))
    ap.add_argument('--shards', type=Path, default=Path('results/leakage_sweep/shards'))
    ap.add_argument('--write', action='store_true',
                    help='without this it only reports; nothing is deleted')
    args = ap.parse_args()

    before = load(args.before / f'{args.corpus}.jsonl')
    after = load(args.after / f'{args.corpus}.jsonl')
    missing = sorted(set(before) - set(after))
    if missing:
        raise SystemExit(
            f'the filtered detection plane is missing {len(missing)} sources that the unfiltered '
            f'one has, e.g. {missing[:3]}. Re-score it fully before pruning, or the diff will '
            f'silently keep rows nobody checked.')

    moved = {label for label in before if changed(before[label], after[label])}
    print(f'{len(before)} span sources scored both ways')
    print(f'  unchanged by the CODE rule : {len(before) - len(moved)}')
    print(f'  changed, must be recomputed: {len(moved)}')

    name = f'{args.corpus}_{args.entity_type}.jsonl'
    total = kept = dropped = 0
    plan: list[tuple[Path, list[str], int]] = []
    for destination in sorted(args.shards.glob(f'*/{name}')):
        survivors, removed = [], 0
        for line in destination.open():
            total += 1
            row = json.loads(line)
            if row['source'] in moved:
                removed += 1
            else:
                survivors.append(line if line.endswith('\n') else line + '\n')
        kept += len(survivors)
        dropped += removed
        plan.append((destination, survivors, removed))
        print(f'  {destination.parent.name}: {len(survivors)} kept, {removed} deleted')

    print(f'\nleakage rows on disk {total}: {kept} kept, {dropped} to delete')
    if not args.write:
        print('dry run: pass --write to delete them, then resubmit the array to continue')
        return 0

    for destination, survivors, _ in plan:
        destination.write_text(''.join(survivors))
    print('deleted. Resubmit the array; each task resumes from its own destination.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
