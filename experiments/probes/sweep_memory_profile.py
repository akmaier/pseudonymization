#!/usr/bin/env python3
'''Where does the Enron sweep's resident set actually go?

AM, 2026-09-27: "I don't understand the 88 GB cap. Why does all of this have to be in memory;
it's sequential data. Sounds like a poor software choice."

Fair question, and it deserves a measurement rather than an opinion. This walks sweep_leakage's
own startup in the same order and prints RSS after each stage, so the cost is attributed to a
stage rather than to the program as a whole. Read-only; it scores nothing and writes nothing.

Run it on a compute node, never the login node.
'''
import os
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')

T0 = time.time()
_last = 0.0


def rss_gb() -> float:
    '''Resident set in GiB. ru_maxrss is KiB on Linux, bytes on macOS.'''
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 ** 2) if sys.platform != 'darwin' else peak / (1024 ** 3)


def live_gb() -> float:
    '''Current (not peak) resident set, from /proc.'''
    try:
        with open('/proc/self/statm') as handle:
            return int(handle.read().split()[1]) * os.sysconf('SC_PAGE_SIZE') / (1024 ** 3)
    except OSError:
        return float('nan')


def mark(stage: str) -> None:
    global _last
    now = live_gb()
    print(f'[{time.time() - T0:7.1f}s] {now:7.2f} GiB live  (+{now - _last:6.2f})  '
          f'peak {rss_gb():7.2f}  {stage}', flush=True)
    _last = now


def main() -> int:
    corpus_name = sys.argv[1] if len(sys.argv) > 1 else 'enron'
    mark('interpreter')

    from pseudonymkit.attacks import build_gallery, disjoint_document_split
    from pseudonymkit.construction import construct, detected_documents, to_pseudonymised_corpus
    from pseudonymkit.detectors.cache import DetectorCache
    from pseudonymkit.domain import Corpus
    from pseudonymkit.metrics.detection import prepare
    from pseudonymkit.serialisation import iter_documents
    from sweep_leakage import CORPORA
    from build_BC import inventory_for, read_key
    mark('imports')

    documents = list(iter_documents(CORPORA[corpus_name]()))
    corpus = Corpus(corpus_name, tuple(documents))
    mentions = sum(len(d.mentions) for d in documents)
    characters = sum(len(d.text) for d in documents)
    mark(f'documents: {len(documents):,} docs, {mentions:,} gold mentions, '
         f'{characters:,} characters')

    key = read_key(Path.home() / '.config' / 'pseudonymkit' / 'hmac.key')
    cache = DetectorCache(Path('results/detector_cache'), corpus_name)
    detectors = sorted(p.stem.replace('__', '/') for p in cache.root.glob('*.jsonl'))
    mark(f'cache handle ({len(detectors)} detectors)')

    union_all, _ = detected_documents(documents, cache, detectors, 'union')
    spans = sum(len(d.mentions) for d in union_all)
    mark(f'union over all {len(detectors)} detectors: a SECOND corpus-sized graph, {spans:,} spans')

    cover = {(m.type, d.language) for d in union_all for m in d.mentions}
    inventory, _ = inventory_for({d.language for d in documents}, documents=union_all, cover=cover)
    mark(f'inventory ({len(cover)} type/language pairs)')

    index = prepare(documents, corpus=corpus_name)
    mark('scoring index: the corpus tokenised once')

    gallery_docs, query_docs = disjoint_document_split(corpus, seed=0)
    gallery = build_gallery(corpus, 'PERSON', documents=gallery_docs)
    mark(f'gallery: {len(gallery):,} profiles')

    # One span source, the most expensive kind, to price the per-source peak.
    recommended = Path('results/leakage_sweep/large_ensemble.txt').read_text().strip().split('+')
    detected, _ = detected_documents(documents, cache, recommended, 'union')
    mark(f'detected: a THIRD corpus-sized graph ({len(recommended)}-detector union)')

    patches = construct(detected, corpus=corpus_name, conditions=('B',),
                        inventory=inventory, key=key)
    mark(f'patch set: {sum(len(p.entries) for p in patches["B"].patches):,} replacements')

    released = to_pseudonymised_corpus(documents, patches['B'], check=False)
    mark('released: a FOURTH corpus-sized graph, with rewritten text')

    print(f'\npeak resident {rss_gb():.2f} GiB', flush=True)
    print('the sweep then repeats the last three stages for every span source in the shard')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
