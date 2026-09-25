'''Re-score Enron's four operating points against the corrected gold.

Table 2's Enron rows are three-detector triples chosen by the old sweep and scored against the old
gold, which counted role mailboxes and word fragments as people.  The *selection* is left alone --
re-running the 1,743-source sweep is not warranted -- but the sensitivity and specificity reported
for those same ensembles have to be recomputed, or the table states numbers the corpus no longer
supports.
'''
import json, sys
from pathlib import Path
sys.path.insert(0, 'src'); sys.path.insert(0, 'experiments')
from pseudonymkit.conditions import CONSTRUCTED, POOLED
from pseudonymkit.construction import detected_documents
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.metrics.detection import prepare, score_prepared, tokenise
from pseudonymkit.serialisation import iter_documents
from score_detection import CORPORA

REPLACED = frozenset(POOLED) | frozenset(CONSTRUCTED)
documents = list(iter_documents(CORPORA['enron']()))
index = prepare(documents, corpus='enron')
cache = DetectorCache(Path('results/detector_cache'), 'enron')
total = sum(len(list(tokenise(d.text))) for d in documents)
points = json.load(open('results/detection/enron_operating_points.json'))['points']

out = {}
for name, p in points.items():
    rule = p['rule']; members = list(p['ensemble'])
    kwargs = {'k': 2} if rule == 'vote' else {}
    detected, _ = detected_documents(documents, cache, members,
                                     rule=('union' if rule == 'single' else rule),
                                     rule_kwargs=kwargs)
    spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}
    s = score_prepared(index, spans, detector='x').as_dict()
    per = s.get('per_type') or {}
    gold = sum(v[0] for t, v in per.items() if t in REPLACED)
    hit = sum(v[2] for t, v in per.items() if t in REPLACED)
    negatives = total - (s.get('gold_tokens') or 0)
    fp = (s.get('predicted_tokens') or 0) - (s.get('true_positive_tokens') or 0)
    out[name] = {'rule': rule, 'sensitivity': hit / gold if gold else None,
                 'specificity': max(0, negatives - fp) / negatives if negatives > 0 else None,
                 'precision': s.get('precision'),
                 'information_weighted_precision': s.get('information_weighted_precision'),
                 'old_sensitivity': p['sensitivity'], 'old_specificity': p['specificity'],
                 'old_precision': p['precision'],
                 'old_information_weighted_precision': p['information_weighted_precision'],
                 'cost_parallel_s': p['cost_parallel_s'], 'cost_serial_s': p['cost_serial_s'],
                 'ensemble': members}
    o = out[name]
    print(f"{name:18s} sens {o['old_sensitivity']:.4f} -> {o['sensitivity']:.4f}   "
          f"spec {o['old_specificity']:.4f} -> {o['specificity']:.4f}   "
          f"prec {o['old_precision']:.4f} -> {o['precision']:.4f}   "
          f"iwP {o['old_information_weighted_precision']:.4f} -> {o['information_weighted_precision']:.4f}", flush=True)
json.dump(out, open('results/detection/enron_operating_points_regold.json','w'), indent=1)
print('done')
