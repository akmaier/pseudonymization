"""Does Phi-4-mini's English truncation survive the corrected budget?

Phi-4-mini's OntoNotes English records date from 2026-09-14, when it was family plain at ratio
1.0 -- a 6,000-character window answered with a ~2,900-token cap.  48.5 % of them truncated.  Since
then AM doubled the plain ratio (2026-09-21) and reclassified Phi as reasoning on its behaviour,
which shrinks its window to 2,952 characters and raises its cap to ~14,000.  Its Chinese records,
re-run under exactly that budget, still truncate 61.5 %.

So the question this answers is narrow: **is Phi's English truncation a budget artefact or the
model?**  Re-running all 3,637 English documents to find out costs about 30 hours of gateway time
that Qwen needs.  A hundred documents answers it in under one, and this is a diagnostic -- it writes
to its own file, never to the detector cache, and nothing it produces is a reported cell.
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0] / '..' / 'src'))

from pseudonymkit.detectors.llm import LlmDetector
from pseudonymkit.serialisation import iter_documents

CORPUS = Path('data/conditionA/ontonotes_A.jsonl.gz')
OUT = Path('results/diag_phi4mini_english.jsonl')
MODEL = 'Microsoft/Phi-4-mini-instruct'
N = 100
SEED = 20260922


def main() -> int:
    english = [d for d in iter_documents(CORPUS) if '/english/' in d.doc_id]
    print(f'{len(english)} English documents in condition A', flush=True)
    chosen = random.Random(SEED).sample(english, min(N, len(english)))
    detector = LlmDetector(MODEL, config_path=Path('config/llm_api.toml'), max_tokens=None)
    print(f'budget: {detector._budget.describe()}', flush=True)

    started = time.time()
    truncated = errors = 0
    with OUT.open('w') as fh:
        for i, document in enumerate(chosen, 1):
            try:
                output, meta = detector.detect_with_meta(document)
                meta = dict(meta or {})
                t = int(meta.get('truncated') or 0)
                truncated += bool(t)
                fh.write(json.dumps({
                    'doc_id': document.doc_id, 'chars': len(document.text),
                    'spans': len(output.spans), 'truncated': t,
                    'windows': meta.get('windows'),
                    'finish_reasons': meta.get('finish_reasons'),
                    'completion_tokens': meta.get('completion_tokens'),
                    'prompt_tokens': meta.get('prompt_tokens'),
                }, ensure_ascii=False) + '\n')
                fh.flush()
            except Exception as exc:                      # noqa: BLE001
                errors += 1
                fh.write(json.dumps({'doc_id': document.doc_id, 'error': str(exc)[:300]}) + '\n')
                fh.flush()
            if i % 10 == 0 or i == len(chosen):
                rate = i / max(time.time() - started, 1e-9) * 3600
                print(f'[{time.time()-started:7.1f}s] {i}/{len(chosen)}  '
                      f'truncated {truncated} ({100*truncated/i:.1f}%)  errors {errors}  '
                      f'{rate:.0f}/h', flush=True)

    print(f'RESULT Phi-4-mini English, corrected budget: '
          f'{truncated}/{len(chosen)} truncated ({100*truncated/len(chosen):.1f}%), '
          f'{errors} errors -- compare 48.5 % on the 2026-09-14 plain-1.0 records', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
