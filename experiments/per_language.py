'''The recommended operating point, scored on **both** error rates, per corpus and per language.

AM, 2026-09-25: *"You are mixing recall, sensitivity and specificity all the time. For a clean
result, both need to be reported."* Three different denominators were being reported under one
word, so all three are computed here and named apart:

* **sensitivity** — recall over the identifier types condition B actually replaces (PERSON, LOC,
  ORG, DEMOGRAPHIC, CODE). This is the definition the operating-point table uses. DATETIME,
  QUANTITY and MISC are passed through by design and are *not* in this denominator.
* **person sensitivity** — the same rate over PERSON alone, which is what the attacks act on.
* **specificity** — the share of non-identifier tokens the ensemble correctly left alone,
  (negatives - false positives) / negatives. Sensitivity without it is unreadable: an ensemble
  that replaces everything scores 1.0 on the first and destroys the text.

The configuration under study is the 13-detector ensemble under **union**, which is that ensemble's
maximum-sensitivity configuration: no other combining rule over the same members can find more.
Vote and intersection are computed beside it to show what the trade actually costs.
'''
import json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, 'src'); sys.path.insert(0, 'experiments')
from pseudonymkit.conditions import CONSTRUCTED, POOLED
from pseudonymkit.construction import detected_documents
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.metrics.detection import prepare, score_prepared, tokenise
from pseudonymkit.serialisation import iter_documents
from score_detection import CORPORA, restrict

REPLACED = frozenset(POOLED) | frozenset(CONSTRUCTED)
IDENTITY = frozenset({'PERSON'})
REC = open('results/leakage_sweep/large_ensemble.txt').read().strip().split('+')
LANGS = ('english', 'chinese', 'arabic')
RULES = (('union', {}), ('vote', {'k': 2}), ('vote', {'k': 3}), ('intersection', {}))


def rate(per_type, types):
    gold = sum(v[0] for t, v in per_type.items() if t in types)
    hit = sum(v[2] for t, v in per_type.items() if t in types)
    return ((hit / gold) if gold else None), gold


def measure(index, spans, total_tokens, keep=None):
    idx = restrict(index, keep) if keep else index
    s = score_prepared(idx, spans, detector='x').as_dict()
    per_type = s.get('per_type') or {}
    sens, sens_gold = rate(per_type, REPLACED)
    psens, p_gold = rate(per_type, IDENTITY)
    negatives = total_tokens - (s.get('gold_tokens') or 0)
    fp = (s.get('predicted_tokens') or 0) - (s.get('true_positive_tokens') or 0)
    spec = (max(0.0, negatives - fp) / negatives) if negatives > 0 else None
    return {'sensitivity': sens, 'sensitivity_gold_tokens': sens_gold,
            'person_sensitivity': psens, 'person_gold_tokens': p_gold,
            'specificity': spec, 'precision': s['precision'],
            'all_gold_tokens': s['gold_tokens'], 'total_tokens': total_tokens,
            'predicted_tokens': s['predicted_tokens'], 'documents': len(idx.documents)}


def language(doc_id):
    for tag in LANGS:
        if f'/{tag}/' in doc_id:
            return tag
    return None


out = {}
for corpus in ('cardiode', 'tab', 'ontonotes', 'enron'):
    documents = list(iter_documents(CORPORA[corpus]()))
    index = prepare(documents, corpus=corpus)
    cache = DetectorCache(Path('results/detector_cache'), corpus)
    tokens_by_doc = {d.doc_id: len(list(tokenise(d.text))) for d in documents}
    total = sum(tokens_by_doc.values())
    by_lang = defaultdict(set)
    for d in documents:
        lang = language(d.doc_id)
        if lang:
            by_lang[lang].add(d.doc_id)

    for rule, kwargs in RULES:
        name = rule + (f"-{kwargs['k']}" if kwargs else '')
        detected, _ = detected_documents(documents, cache, REC, rule=rule, rule_kwargs=kwargs)
        spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}
        block = {'rule': rule, 'k': kwargs.get('k'), 'members': len(REC),
                 'overall': measure(index, spans, total)}
        if corpus == 'ontonotes':
            block['by_language'] = {
                lang: measure(index, spans, sum(tokens_by_doc[i] for i in by_lang[lang]),
                              by_lang[lang])
                for lang in LANGS}
        out.setdefault(corpus, {})[name] = block
        print(f'{corpus}/{name}: done', flush=True)

json.dump(out, open('results/detection/recommended_both_rates.json', 'w'), indent=1)
print('wrote results/detection/recommended_both_rates.json')
