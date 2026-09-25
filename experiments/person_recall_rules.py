'''PERSON token recall of the recommended ensemble under each combining rule, on Enron.

The leakage prose compares the union release with the two-vote one.  The sweep's token_recall is
over every annotated type, so quoting it beside a person-recall column compares two denominators;
this computes the person figure the column actually uses.
'''
import sys
from pathlib import Path
sys.path.insert(0, 'src'); sys.path.insert(0, 'experiments')
from pseudonymkit.construction import detected_documents
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.metrics.detection import prepare, score_prepared
from pseudonymkit.serialisation import iter_documents
from score_detection import CORPORA

IDENTITY = frozenset({'PERSON'})
ENSEMBLE = open('results/leakage_sweep/large_ensemble.txt').read().strip().split('+')

documents = list(iter_documents(CORPORA['enron']()))
index = prepare(documents, corpus='enron')
cache = DetectorCache(Path('results/detector_cache'), 'enron')
for rule, kwargs in (('union', {}), ('vote', {'k': 2}), ('vote', {'k': 3}), ('intersection', {})):
    detected, _ = detected_documents(documents, cache, ENSEMBLE, rule=rule, rule_kwargs=kwargs)
    spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}
    per_type = score_prepared(index, spans, detector='p').as_dict().get('per_type') or {}
    gold = sum(v[0] for t, v in per_type.items() if t in IDENTITY)
    hit = sum(v[2] for t, v in per_type.items() if t in IDENTITY)
    label = rule + (f"-{kwargs['k']}" if kwargs else '')
    print(f'{label:14s} PERSON token recall {hit/gold:.4f} over {gold:,} gold tokens', flush=True)
