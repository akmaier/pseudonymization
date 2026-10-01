#!/usr/bin/env python3
'''A4, the LLM attacker, at the pre-registered sample points — parallel over models.

AM, 2026-09-30: run the 90 cells, and run several models at once because the gateway's token
limit is per model. That is the pattern `detect_gateway.py` already follows for detection, on AM's
decision of 2026-09-08: *"Parallel over models, sequential over texts. One thread per model."*

Each model thread walks the whole cell list independently and writes its own rows, so the models
neither contend for the gateway's per-model budget nor for a file. Running N models therefore
costs about what one model costs, and yields a model axis for nothing — which is the honest way to
report an LLM attack, since a single model's number is a property of that model as much as of the
release.

**Not a Slurm array.** The gateway client holds no GPU, does no arithmetic and spends its life in
recv(); an earlier version ran as a nine-task array and occupied eight of the association's job
slots doing nothing, blocking the group's GPU work (detect_gateway.py:3-8). One job, N threads.

Cells: 22 operating points x {B, C} plus one condition-A ceiling per corpus = 45 per corpus.
Condition A is run once because nothing is replaced there, so its text is the same whatever the
detector did.
'''
import argparse
import json
import sys
import threading
import time
from pathlib import Path
from queue import Queue

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')

from pseudonymkit.attacks.candidates import LlmCandidateRanker, build_items, score
from pseudonymkit.conditions import Unmodified
from pseudonymkit.construction import check_current, read_patchset, to_pseudonymised_corpus
from pseudonymkit.domain import Corpus
from pseudonymkit.gateway import list_models
from pseudonymkit.serialisation import iter_documents
from run_leakage import SOURCES
from run_linear_a4 import tag_for
from sweep_leakage import CORPORA

T0 = time.time()
PRINT = threading.Lock()

A4_EXCLUDED = {
    # Not down, and not substituted: it refuses every A4 call with
    # litellm.ContextWindowExceededError. A4's prompt is a document plus ten candidates, and a
    # 3.8B model with a short window cannot hold it. Shrinking the prompt for this model alone
    # would make its number incomparable with the other seven; shrinking it for everyone would
    # weaken every model's attack and void the cells already computed. Removed from A4 only
    # (AM, 2026-10-01) -- it stays in the detection pool, where the prompt is one document.
    'Microsoft/Phi-4-mini-instruct',
}
"""Models excluded from A4 specifically, with the reason. Detection keeps its own pool."""


def log(message: str) -> None:
    with PRINT:
        print(f'[{time.time() - T0:8.1f}s] {message}', flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--models', nargs='+', default=None,
                    help='default: the chat models of detect_gateway.DEFAULT_MODELS that the '
                         'gateway is serving right now. NOT everything /models lists: that '
                         'includes an embedding model and an OCR model, which answer HTTP 400 '
                         'and 404, and DeepSeek, which experiment_plan.md excludes by decision.')
    ap.add_argument('--limit', type=int, default=200, help='A4 queries per cell')
    ap.add_argument('--n-candidates', type=int, default=10)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--concurrency', type=int, default=4,
                    help='queries in flight per model. Kept small: the budget is per model, so '
                         'throughput comes from running models side by side, not from hammering '
                         'one of them.')
    ap.add_argument('--points', type=int, default=0, help='cap points, for a smoke run')
    ap.add_argument('--out', type=Path, default=Path('results/phase1'))
    args = ap.parse_args()

    from detect_gateway import DEFAULT_MODELS

    live = list_models()
    models = args.models or [m for m in DEFAULT_MODELS
                             if m in live and m not in A4_EXCLUDED]
    unavailable = [m for m in models if m not in live]
    log(f'gateway serves {len(live)} models right now; running {len(models)}')
    if unavailable:
        log(f'  NOT SERVED, skipped and recorded: {unavailable}')
        models = [m for m in models if m in live]

    documents = list(iter_documents(CORPORA[args.corpus]()))
    corpus = Corpus(args.corpus, tuple(documents))
    root = SOURCES[args.corpus][1]()
    sample = json.loads(
        Path(f'results/phase1/{args.corpus}_a4_sample.json').read_text())['sample']
    if args.points:
        sample = sample[: args.points]

    cells = [('A', None, 'condition-A ceiling')]
    for point in sample:
        for condition in ('B', 'C'):
            cells.append((condition, point, point['role']))
    log(f'{args.corpus}: {len(documents):,} documents, {len(cells)} cells x {len(models)} models')

    # Items are built once per cell and shared by every model: identical inputs are what makes the
    # models comparable, and rebuilding them per model would also reshuffle the distractors.
    prepared: list[tuple[str, dict | None, str, list]] = []
    for condition, point, role in cells:
        if condition == 'A':
            released = Unmodified().pseudonymise_corpus(documents)
        else:
            path = root / f'{args.corpus}_{condition}_{tag_for(point["source"])}.patch.jsonl'
            if not path.exists():
                log(f'  no patch set for {role} {condition} — cell skipped'); continue
            try:
                check_current(documents, read_patchset(path))
            except Exception as error:
                log(f'  STALE {role} {condition}: {error}'); continue
            released = to_pseudonymised_corpus(documents, read_patchset(path), check=False)
        items = build_items(released, corpus, n_candidates=args.n_candidates, seed=args.seed)
        if not items:
            log(f'  no A4 items for {role} {condition} — nothing to attack'); continue
        prepared.append((condition, point, role, items[: args.limit]))
    log(f'  {len(prepared)} cells have items; {len(cells) - len(prepared)} do not')

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f'{args.corpus}_a4_llm.jsonl'
    done = set()
    if destination.exists():
        for line in destination.open():
            row = json.loads(line)
            done.add((row['model'], row['condition'], row.get('source') or 'A'))
        log(f'  resuming: {len(done)} cells already done')
    handle = destination.open('a', buffering=1)
    writing = threading.Lock()

    def work(model: str) -> None:
        ranker = LlmCandidateRanker(model=model)
        queue: Queue = Queue()
        for cell in prepared:
            queue.put(cell)
        while not queue.empty():
            condition, point, role, items = queue.get()
            key = (model, condition, (point or {}).get('source', 'A'))
            if key in done:
                continue
            started = time.time()
            try:
                result = score(items, ranker, condition=condition,
                               concurrency=args.concurrency)
            except Exception as error:
                log(f'  [{model}] {condition} {role}: FAILED — {str(error)[:120]}')
                continue
            row = {
                'corpus': args.corpus, 'model': model, 'condition': condition,
                'source': (point or {}).get('source'), 'role': role,
                'queries': len(items), 'rank1': result.overall.rank1,
                'rank5': result.overall.rank5,
                'map': result.overall.mean_average_precision,
                'n_candidates': result.n_candidates,
                'chance': 1.0 / max(result.n_candidates, 1),
                'seconds': round(time.time() - started, 1),
            }
            with writing:
                handle.write(json.dumps(row) + '\n')
            log(f'  [{model[:28]:28s}] {condition} {role[:22]:22s} '
                f'Rank-1 {result.overall.rank1:.3f} in {row["seconds"]:.0f}s')

    threads = [threading.Thread(target=work, args=(m,), daemon=False) for m in models]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    handle.close()
    log(f'wrote {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
