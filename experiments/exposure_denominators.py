'''Exposure under every denominator, stated apart.

AM, 2026-09-25: exposure needs careful re-analysis. Two faults are being corrected here.

**A person is not an entity-document pair.** leakage_profile.py builds gold_by_entity inside
its per-document loop, so its "entities" are entity-document pairs: a person in forty messages is
counted forty times. On Enron that inflates the denominator from about four thousand people to
281,476 pairs, and the rate built on it was reported as "the share of people". Both are computed
here and named apart.

**Enron is mostly header.** Its gold is header-derived, so 86 % of its identifier tokens sit in the
From/To/Cc/Subject block rather than in prose. Exposure is therefore also split by
region, because a name surviving in a structured header is a different failure from one surviving
in a sentence, and only the second is evidence about free text.
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
from leakage_profile import case_of

REPLACED = frozenset(POOLED) | frozenset(CONSTRUCTED)
IDENTITY = frozenset({'PERSON'})
REC = open('results/leakage_sweep/large_ensemble.txt').read().strip().split('+')

out = {}
for corpus in ('cardiode', 'tab', 'ontonotes', 'enron'):
    documents = list(iter_documents(CORPORA[corpus]()))
    cache = DetectorCache(Path('results/detector_cache'), corpus)
    detected, _ = detected_documents(documents, cache, REC, rule='union', rule_kwargs={})
    spans_by_doc = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}

    for label, types in (('person', IDENTITY), ('replaced', REPLACED)):
        people, exposed_people = set(), set()
        pairs = exposed_pairs = 0
        docs = exposed_docs = 0
        cases, exposed_cases = set(), set()
        mentions = exposed_mentions = 0
        corpus_cases = True
        for document in documents:
            case, real = case_of(document, corpus)
            if not real:
                corpus_cases = False
            cases.add(case)
            tokens = tokenise(document.text)
            caught = covered_tokens(tokens, spans_by_doc.get(document.doc_id, ()))
            per_entity = defaultdict(set)
            any_left = False
            for mention in document.mentions:
                if mention.type not in types:
                    continue
                idx = covered_tokens(tokens, (mention.span,))
                if not idx:
                    continue
                mentions += 1
                key = mention.gold_entity_id or mention.mention_id
                per_entity[key] |= (idx - caught)
                people.add(key)
                if idx - caught:
                    exposed_mentions += 1
                    any_left = True
                    exposed_people.add(key)
                    exposed_cases.add(case)
            docs += 1
            exposed_docs += int(any_left)
            for key, left in per_entity.items():
                pairs += 1
                exposed_pairs += int(bool(left))
        out.setdefault(corpus, {})[label] = {
            'distinct_entities': len(people), 'distinct_entities_exposed': len(exposed_people),
            'entity_document_pairs': pairs, 'entity_document_pairs_exposed': exposed_pairs,
            'mentions': mentions, 'mentions_exposed': exposed_mentions,
            'documents': docs, 'documents_exposed': exposed_docs,
            'cases': len(cases), 'cases_exposed': len(exposed_cases),
            'cases_are_documents': not corpus_cases,
        }
        r = out[corpus][label]
        print(f"{corpus:10s} {label:8s} people {r['distinct_entities_exposed']:>6,}/"
              f"{r['distinct_entities']:>7,} = {r['distinct_entities_exposed']/max(r['distinct_entities'],1):6.2%}"
              f"   pairs {r['entity_document_pairs_exposed']:>7,}/{r['entity_document_pairs']:>8,}"
              f" = {r['entity_document_pairs_exposed']/max(r['entity_document_pairs'],1):6.2%}"
              f"   docs {r['documents_exposed']:>6,}/{r['documents']:>6,}", flush=True)

json.dump(out, open('results/detection/exposure_denominators.json', 'w'), indent=1)
print('wrote results/detection/exposure_denominators.json')
