#!/usr/bin/env python3
'''Score the recommended whole-pool ensemble into the detection plane.

The detection sweep enumerates subsets of at most three detectors, so the four 13-detector rules
the study actually recommends are absent from it -- and with them the PERSON sensitivity of the
best operating point on either corpus. Phase 1 dropped them as "no detection row" and the safest
point was chosen without the recommended ensemble in the comparison (AM spotted it, 2026-09-29).

Appends rows in the detection plane's own shape so the join key is unchanged.
'''
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')

from pseudonymkit.construction import detected_documents
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.metrics.detection import prepare, score_prepared
from pseudonymkit.serialisation import iter_documents
from sweep_leakage import CORPORA

RULES = (('union', {}), ('vote', {'k': 2}), ('vote', {'k': 3}), ('intersection', {}))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--members', type=Path,
                    default=Path('results/leakage_sweep/large_ensemble.txt'))
    ap.add_argument('--out', type=Path, default=Path('results/detection_filtered'))
    args = ap.parse_args()

    names = tuple(sorted(args.members.read_text().strip().split('+')))
    documents = list(iter_documents(CORPORA[args.corpus]()))
    index = prepare(documents, corpus=args.corpus)
    cache = DetectorCache(Path('results/detector_cache'), args.corpus)
    print(f'{args.corpus}: {len(documents):,} documents, {len(names)} detectors')

    destination = args.out / f'{args.corpus}.jsonl'
    have = {json.loads(l)['detector'] for l in destination.open()} if destination.exists() else set()

    with destination.open('a', buffering=1) as handle:
        for rule, kwargs in RULES:
            label = f"{'+'.join(names)}|{rule}{kwargs.get('k', '')}"
            if label in have:
                print(f'  already scored: {rule}{kwargs.get("k", "")}')
                continue
            detected, report = detected_documents(documents, cache, list(names),
                                                  rule=rule, rule_kwargs=kwargs)
            spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}
            row = score_prepared(index, spans, detector=label).as_dict()
            row.update(corpus=args.corpus, detector=label, size=len(names), rule=rule,
                       ensemble=list(names), documents=len(documents),
                       documents_missing_a_detector=report.get('documents_missing_a_detector'))
            handle.write(json.dumps(row) + '\n')
            person = (row.get('per_type') or {}).get('PERSON')
            sens = person[2] / person[0] if person and person[0] else float('nan')
            print(f'  {rule}{kwargs.get("k", "")}: PERSON sensitivity {sens:.4f}, '
                  f'precision {row["precision"]:.4f}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
