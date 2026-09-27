#!/usr/bin/env python3
'''Delete every leakage row whose span source contains a detector the CODE rule touches.

AM, 2026-09-27: "I want the affected 1697 cases rerun. No compromise."

The test is MEMBERSHIP, deliberately, and not a cheaper one. An earlier version of this script
diffed the filtered detection plane against the unfiltered one and kept any source whose detection
row was unchanged, on the argument that an identical span set gives an identical leakage row. AM
ruled against it: a source built from a detector whose output the rule altered is recomputed,
whether or not this particular rule and this particular corpus happened to cancel the change out.
Keeping such a row means a plane whose provenance differs cell by cell.

So a row survives only if EVERY member of its ensemble is clean. With six of the fifteen Enron
detectors affected, that is 129 of the 575 subsets and 453 of the 2,150 sources; the other 1,697
are deleted and recomputed.

The diff is still computed and reported when the filtered detection plane is available, because
"how many of the 1,697 would in fact have been unchanged" is a number the paper should state -- it
is the cost of the conservative choice, and stating it is not the same as taking it.

    python experiments/code_filter_audit.py --corpus enron
    python experiments/prune_affected_rows.py --corpus enron            # report only
    python experiments/prune_affected_rows.py --corpus enron --write    # then resubmit the array
'''
import argparse
import json
from pathlib import Path

SPAN_SENSITIVE = (
    'token_recall', 'entity_recall', 'precision', 'information_weighted_precision',
    'predicted_tokens', 'true_positive_tokens', 'gold_tokens', 'protected_entities',
    'documents_missing_a_detector', 'per_type',
)


def members(label: str) -> list[str]:
    """``a+b+c|vote2`` -> the detector names. The rule is everything left of the final bar."""
    ensemble, _, _ = label.rpartition('|')
    return (ensemble or label).split('+')


def load(path: Path, key: str) -> dict[str, dict]:
    return {json.loads(line)[key]: json.loads(line) for line in path.open()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--entity-type', default='PERSON')
    ap.add_argument('--audit', type=Path, default=None)
    ap.add_argument('--before', type=Path, default=Path('results/detection'))
    ap.add_argument('--after', type=Path, default=Path('results/detection_filtered'))
    ap.add_argument('--shards', type=Path, default=Path('results/leakage_sweep/shards'))
    ap.add_argument('--canonical', type=Path, default=Path('results/leakage_sweep'),
                    help='the un-sharded <corpus>_<TYPE>.jsonl is pruned too; on Enron it holds the '
                         'four hand-run 13-detector rules and nothing else scans it')
    ap.add_argument('--write', action='store_true', help='without this it only reports')
    args = ap.parse_args()

    audit_path = args.audit or args.before / f'code_filter_audit_{args.corpus}.json'
    audit = json.loads(audit_path.read_text())
    affected = set(audit['affected_detectors'])
    print(f'rule: {audit["rule"]}')
    print(f'{len(affected)} of {audit["pool_size"]} detectors affected; '
          f'{audit["dropped_total"]:,} CODE spans dropped\n')

    # Candidate labels come from the detection plane AND from the rows on disk. The four
    # 13-detector recommended rules were run by hand and are absent from the size-3 enumeration, so
    # a condemned set built from the plane alone silently spares them -- they contain affected
    # detectors and must be recomputed like everything else.
    name = f'{args.corpus}_{args.entity_type}.jsonl'
    labels: set[str] = set()
    plane = args.before / f'{args.corpus}.jsonl'
    if plane.exists():
        labels |= {json.loads(line)['detector'] for line in plane.open()}
    targets = [p for p in (args.canonical / name,) if p.exists()]
    targets += sorted(args.shards.glob(f'*/{name}'))
    on_disk: set[str] = set()
    for destination in targets:
        on_disk |= {json.loads(line)['source'] for line in destination.open()}
    outside = sorted(on_disk - labels)
    labels |= on_disk

    condemned = {label for label in labels if any(m in affected for m in members(label))}
    print(f'span sources: {len(labels)} total ({len(outside)} present as results but not in the '
          f'detection enumeration), {len(condemned)} contain an affected detector, '
          f'{len(labels) - len(condemned)} clean')
    for label in outside:
        verdict = 'CONDEMNED' if label in condemned else 'clean'
        print(f'    {verdict:9s} {label.split("|")[-1]:14s} '
              f'{len(label.split("|")[0].split("+"))} detectors')

    after = args.after / f'{args.corpus}.jsonl'
    if plane.exists() and after.exists():
        before_rows, after_rows = load(plane, 'detector'), load(after, 'detector')
        shared = set(before_rows) & set(after_rows)
        moved = {k for k in shared
                 if any(before_rows[k].get(f) != after_rows[k].get(f) for f in SPAN_SENSITIVE)}
        unchanged = len(condemned & shared) - len(condemned & moved)
        print(f'  of those {len(condemned)}, the detection diff says {unchanged} would in fact be '
              f'unchanged -- reported, not acted on (AM, 2026-09-27)')

    total = kept = removed = 0
    plan = []
    for destination in targets:
        survivors, gone = [], 0
        for line in destination.open():
            total += 1
            if json.loads(line)['source'] in condemned:
                gone += 1
            else:
                survivors.append(line if line.endswith('\n') else line + '\n')
        kept += len(survivors)
        removed += gone
        plan.append((destination, survivors))
        where = (destination.parent.name if destination.parent != args.canonical
                 else 'canonical')
        print(f'  {where}: {len(survivors)} kept, {gone} deleted')

    print(f'\nleakage rows on disk {total}: {kept} kept, {removed} to delete')
    if not args.write:
        print('dry run: pass --write to delete, then resubmit the array to continue')
        return 0
    for destination, survivors in plan:
        destination.write_text(''.join(survivors))
    print('deleted. Resubmit the array; each task resumes from its own destination.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
