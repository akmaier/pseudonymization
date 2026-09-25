'''Is Enron's detection performance a property of its message headers rather than its prose?

AM, 2026-09-25: *"It is unclear why the performance of Enron is so bad. I suspect this is the header
information that does not represent natural text that the models are trained on. Headers are
structured and can therefore be de-ID'd automatically. I think exposure needs to be carefully
analysed and re-computed for this likely mistake."*

The adapter builds each document as a reduced header block — From/To/Cc/Subject with
display names and addresses — followed by a blank line and the body, so the split is exact rather
than guessed: everything before the first blank line is header, everything after is prose. This
scores the recommended 13-detector union separately on the two regions, on both error rates and on
exposure, so a number that belongs to the header block can no longer be read as a statement about
free text.

Nothing identifying leaves this script: counts and rates only.
'''
import json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, 'src'); sys.path.insert(0, 'experiments')
from pseudonymkit.conditions import CONSTRUCTED, POOLED
from pseudonymkit.construction import detected_documents
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.metrics.detection import covered_tokens, tokenise
from pseudonymkit.serialisation import iter_documents
from score_detection import CORPORA

REPLACED = frozenset(POOLED) | frozenset(CONSTRUCTED)
IDENTITY = frozenset({'PERSON'})
REC = open('results/leakage_sweep/large_ensemble.txt').read().strip().split('+')


def boundary(text: str) -> int:
    '''First blank line: the adapter joins the header lines then appends \n\n + body.'''
    i = text.find('\n\n')
    return len(text) if i < 0 else i


documents = list(iter_documents(CORPORA['enron']()))
cache = DetectorCache(Path('results/detector_cache'), 'enron')
detected, _ = detected_documents(documents, cache, REC, rule='union', rule_kwargs={})
spans_by_doc = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}

R = {r: dict(tokens=0, gold=0, hit=0, person_gold=0, person_hit=0,
             predicted=0, true_positive=0, docs=0, docs_exposed=0, docs_person_exposed=0)
     for r in ('header', 'body')}
entity_region = defaultdict(set)      # gold entity -> regions where a mention SURVIVED
entities_seen = defaultdict(set)      # gold entity -> regions where it is mentioned at all

for document in documents:
    text = document.text
    cut = boundary(text)
    tokens = tokenise(text)
    caught = covered_tokens(tokens, spans_by_doc.get(document.doc_id, ()))
    region_of = ['header' if s < cut else 'body' for s, _ in tokens]
    for r in ('header', 'body'):
        R[r]['docs'] += 1
    for i, r in enumerate(region_of):
        R[r]['tokens'] += 1
        if i in caught:
            R[r]['predicted'] += 1

    gold_idx = {'header': set(), 'body': set()}
    person_idx = {'header': set(), 'body': set()}
    exposed_here = {'header': False, 'body': False}
    person_exposed_here = {'header': False, 'body': False}
    for mention in document.mentions:
        if mention.type not in REPLACED:
            continue
        idx = covered_tokens(tokens, (mention.span,))
        if not idx:
            continue
        r = 'header' if min(idx) < len(region_of) and region_of[min(idx)] == 'header' else 'body'
        gold_idx[r] |= idx
        key = mention.gold_entity_id or mention.mention_id
        if mention.type in IDENTITY:
            person_idx[r] |= idx
            entities_seen[key].add(r)
        if idx - caught:
            exposed_here[r] = True
            if mention.type in IDENTITY:
                person_exposed_here[r] = True
                entity_region[key].add(r)
    for r in ('header', 'body'):
        R[r]['gold'] += len(gold_idx[r])
        R[r]['hit'] += len(gold_idx[r] & caught)
        R[r]['person_gold'] += len(person_idx[r])
        R[r]['person_hit'] += len(person_idx[r] & caught)
        R[r]['true_positive'] += len(gold_idx[r] & caught)
        R[r]['docs_exposed'] += int(exposed_here[r])
        R[r]['docs_person_exposed'] += int(person_exposed_here[r])

out = {'corpus': 'enron', 'ensemble': 'recommended 13, union', 'regions': {}}
for r, v in R.items():
    negatives = v['tokens'] - v['gold']
    fp = v['predicted'] - v['true_positive']
    out['regions'][r] = {
        'tokens': v['tokens'], 'gold_tokens': v['gold'], 'person_gold_tokens': v['person_gold'],
        'sensitivity': (v['hit'] / v['gold']) if v['gold'] else None,
        'person_sensitivity': (v['person_hit'] / v['person_gold']) if v['person_gold'] else None,
        'specificity': (max(0, negatives - fp) / negatives) if negatives > 0 else None,
        'predicted_tokens': v['predicted'], 'false_positive_tokens': fp,
        'documents_with_a_finding': v['docs_exposed'],
        'documents_with_a_person_in_clear': v['docs_person_exposed'],
        'documents': v['docs'],
    }
only_h = sum(1 for k, rs in entity_region.items() if rs == {'header'})
only_b = sum(1 for k, rs in entity_region.items() if rs == {'body'})
both = sum(1 for k, rs in entity_region.items() if rs == {'header', 'body'})
out['person_entities'] = {
    'exposed_total': len(entity_region), 'exposed_header_only': only_h,
    'exposed_body_only': only_b, 'exposed_both': both,
    'mentioned_total': len(entities_seen),
    'mentioned_header_only': sum(1 for rs in entities_seen.values() if rs == {'header'}),
    'mentioned_body_only': sum(1 for rs in entities_seen.values() if rs == {'body'}),
}
json.dump(out, open('results/detection/enron_header_split.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
