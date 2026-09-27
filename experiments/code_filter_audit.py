#!/usr/bin/env python3
'''Which detectors the CODE sanity rule touches, and how hard.

Writes results/detection/code_filter_audit_<corpus>.json, which is both the input to
experiments/prune_affected_rows.py and the evidence behind the paper's paragraph on the rule
(experiment_plan_operating_point.md §8.6).

Read-only over the span cache. No span surface is printed or stored: the artefact carries counts
and detector names only, because the CARDIO:DE cache holds DUA-restricted clinical text.
'''
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, 'src')
from pseudonymkit.construction import CODE_MIN_LENGTH, code_filter  # noqa: E402
from pseudonymkit.domain import Span  # noqa: E402


def keeps(text: str) -> bool:
    return bool(code_filter((Span(0, max(len(text), 1), text, 'CODE'),)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--cache', type=Path, default=Path('results/detector_cache'))
    ap.add_argument('--out', type=Path, default=Path('results/detection'))
    args = ap.parse_args()

    root = args.cache / args.corpus
    dropped: dict[str, int] = {}
    kept: dict[str, int] = {}
    for path in sorted(root.glob('*.jsonl')):
        name = path.stem.replace('__', '/')
        dropped.setdefault(name, 0)
        kept.setdefault(name, 0)
        for line in path.open():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            for span in record.get('spans') or []:
                if span.get('type') != 'CODE':
                    continue
                if keeps(span.get('text') or ''):
                    kept[name] += 1
                else:
                    dropped[name] += 1

    affected = sorted(name for name, n in dropped.items() if n)
    audit = {
        'corpus': args.corpus,
        'code_min_length': CODE_MIN_LENGTH,
        'rule': 'a CODE span is kept only if it has an alphanumeric character and is at least '
                f'{CODE_MIN_LENGTH} characters long',
        'affected_detectors': affected,
        'dropped_per_detector': {k: v for k, v in sorted(dropped.items()) if v},
        'kept_per_detector': {k: v for k, v in sorted(kept.items()) if v},
        'dropped_total': sum(dropped.values()),
        'kept_total': sum(kept.values()),
        'pool_size': len(dropped),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f'code_filter_audit_{args.corpus}.json'
    destination.write_text(json.dumps(audit, indent=1) + '\n')

    print(f'{args.corpus}: {audit["dropped_total"]:,} CODE spans dropped, '
          f'{audit["kept_total"]:,} kept, across {audit["pool_size"]} detectors')
    for name in affected:
        print(f'  AFFECTED  drop {dropped[name]:8,}  keep {kept[name]:9,}  {name}')
    print(f'wrote {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
