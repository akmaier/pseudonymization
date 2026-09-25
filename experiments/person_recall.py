'''PERSON token recall of the recommended 13-detector union, per corpus and per OntoNotes language.

Table 2 reports sensitivity over every identifier type; the leakage tables report what the attacks
actually target, which is people (AM, 2026-09-24: identity is PERSON, not the other classes).  The
two are different denominators and were being read as one, so this computes the second explicitly.
'''
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, 'src'); sys.path.insert(0, 'experiments')
from pseudonymkit.construction import detected_documents
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.metrics.detection import prepare, score_prepared
from pseudonymkit.serialisation import iter_documents
from score_detection import CORPORA, restrict

IDENTITY = frozenset({'PERSON'})
ENSEMBLE = open('results/leakage_sweep/large_ensemble.txt').read().strip().split('+')

def sensitivity(scored):
    per_type = scored.get('per_type') or {}
    gold = sum(v[0] for t, v in per_type.items() if t in IDENTITY)
    hit = sum(v[2] for t, v in per_type.items() if t in IDENTITY)
    return (hit / gold) if gold else float('nan'), gold

def language(doc_id):
    for tag in ('english', 'chinese', 'arabic'):
        if f'/{tag}/' in doc_id:
            return tag
    return None

for corpus in ('cardiode', 'tab', 'ontonotes', 'enron'):
    documents = list(iter_documents(CORPORA[corpus]()))
    index = prepare(documents, corpus=corpus)
    cache = DetectorCache(Path('results/detector_cache'), corpus)
    detected, _ = detected_documents(documents, cache, ENSEMBLE, rule='union', rule_kwargs={})
    spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}
    value, gold = sensitivity(score_prepared(index, spans, detector='p').as_dict())
    print(f'{corpus:10s} PERSON token recall {value:.4f} over {gold:,} gold tokens', flush=True)
    if corpus == 'ontonotes':
        by_language = defaultdict(set)
        for document in documents:
            lang = language(document.doc_id)
            if lang:
                by_language[lang].add(document.doc_id)
        for lang in ('english', 'chinese', 'arabic'):
            keep = by_language[lang]
            v, g = sensitivity(score_prepared(restrict(index, keep), spans, detector='l').as_dict())
            print(f'   {lang:9s} {len(keep):6,} documents  recall {v:.4f} over {g:,} gold tokens', flush=True)
