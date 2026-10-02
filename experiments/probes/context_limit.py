#!/usr/bin/env python3
"""Ask a gateway deployment to name its own context limit, rather than assuming one.

`budget.CONTEXT` records the limits measured on 2026-09-12 by the trick vLLM hands us: a request
with an absurd ``max_tokens`` is refused with the limit in the error text — *"max_tokens=10000000
cannot be greater than max_model_len=max_total_tokens=262144"*. Three deployments answered that
way; the rest accepted the absurd value without validating and fall back to ``DEFAULT_CONTEXT``,
which is 32,768 and deliberately conservative.

DeepSeek-V4-Flash-0731 is on the conservative fallback and that is now load-bearing: at
``RATIO['reasoning'] = 12`` the window is (32768-1024)/13 = 2,441 prompt tokens, and 379 of 400
CARDIO:DE documents came back truncated. If the real limit is larger, the fix is a bigger cap
rather than a smaller window -- more windows per document costs calls, and each one re-reads the
prompt.

    PYTHONPATH=src python experiments/probes/context_limit.py deepseek-ai/DeepSeek-V4-Flash-0731

Costs one refused request per model when the deployment validates, and one one-token completion
when it does not.
"""
from __future__ import annotations

import re
import sys

sys.path.insert(0, 'src')

from pseudonymkit.gateway import GatewayClient

ABSURD = 10_000_000
LIMIT = re.compile(r'max_model_len[=:]?\s*(?:max_total_tokens=)?(\d+)')


def probe(model: str) -> str:
    client = GatewayClient(model)
    try:
        reply = client.ask('Answer with one word.', 'Say ok.', max_tokens=ABSURD)
    except Exception as error:
        text = str(error)
        found = LIMIT.search(text)
        if found:
            return f'{model}: context {int(found.group(1)):,} (named by the deployment)'
        return f'{model}: refused without naming a limit — {text[:200]}'
    return (f'{model}: accepted max_tokens={ABSURD:,} without validating, so the limit cannot be '
            f'read this way; reply {(reply.text or "")[:40]!r}')


if __name__ == '__main__':
    models = sys.argv[1:]
    if not models:
        raise SystemExit(__doc__)
    for name in models:
        print(probe(name), flush=True)
