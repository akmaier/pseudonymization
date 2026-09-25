'''How much of what the ensemble detected the engine actually wrote.

The replacement engine resolves overlapping detections by writing one span of any overlapping
group and skipping the rest, and it records the count it skipped with each patch.  That number is
the difference between "the union of detected spans" and "the text that was released": where a
short span wins over a longer one, the remainder of the name is published even though a detector
found it.  Those are the *clipped* mentions that `exposure_from_release.py` counts and that no
measure computed on detected spans can see.

The project page asserted a skip rate in prose without a file behind it.  This reads it off the
released condition-B patch sets, which are the artefacts the release was built from, so the rate
is sourced rather than remembered.  Nothing is re-detected and nothing is re-written; the patch
sets are opened read-only.

    python experiments/release_skip_rate.py
'''
import json
import sys
from pathlib import Path

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')
from pseudonymkit.paths import cardiode_conditions, work_dir  # noqa: E402

TAG = 'union-single0.5-13det-1797ba'
"""The recommended 13-detector union — the release every leakage figure describes."""

SOURCES = {
    'cardiode': cardiode_conditions,
    'tab': lambda: work_dir() / 'results/conditions',
    'ontonotes': lambda: work_dir() / 'results/conditions',
    'enron': lambda: work_dir() / 'results/conditions',
}

out = {}
for corpus, root in SOURCES.items():
    path = root() / f'{corpus}_B_{TAG}.patch.jsonl'
    documents = written = skipped = 0
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            record = json.loads(line)
            if '__patchset__' in record:
                continue
            documents += 1
            written += len(record.get('entries', []))
            skipped += record.get('skipped', 0)
    detected = written + skipped
    out[corpus] = {
        'tag': TAG,
        'condition': 'B',
        'documents': documents,
        'replacements_written': written,
        'replacements_skipped': skipped,
        'detections_resolved': detected,
        'skip_rate': (skipped / detected) if detected else None,
    }
    print(f"{corpus:10s} docs {documents:>6,}  written {written:>9,}  skipped {skipped:>9,}  "
          f"skip rate {out[corpus]['skip_rate']:.4f}", flush=True)

destination = Path('results/detection/release_skip.json')
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
print(f'wrote {destination}')
