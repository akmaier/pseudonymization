'''Exposure measured against the released text itself, under every denominator.

Two earlier routes disagreed — leakage_profile.py combines cached spans through load_pool +
combine, this session's check re-derived them through detected_documents — and on TAB they
differ by five exposed people out of seventy. Neither is authoritative. What was *released* is the
condition-B patch set, whose old_start/old_end are the spans actually overwritten, after the
engine's own overlap-skipping rule. Those are what an attacker sees, so those are what exposure is
scored against here.

Denominators are kept apart because they were being conflated. leakage_profile.py builds its
entity map inside the per-document loop, so its "entities" are entity-document pairs: a person in
forty Enron messages counts forty times, which is how an 18 % figure came to be reported as the
share of *people*. Enron is additionally split at the header boundary, because 86 % of its gold
identifier tokens sit in the From/To/Cc/Subject block and a name surviving there is a different
failure from one surviving in a sentence.
'''
import json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, 'src'); sys.path.insert(0, 'experiments')
from pseudonymkit.conditions import CONSTRUCTED, POOLED
from pseudonymkit.construction import check_current, read_patchset
from pseudonymkit.metrics.detection import covered_tokens, tokenise
from pseudonymkit.paths import cardiode_a, cardiode_conditions, condition_a_dir, work_dir
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.domain import Span
from leakage_profile import case_of

REPLACED = frozenset(POOLED) | frozenset(CONSTRUCTED)
IDENTITY = frozenset({'PERSON'})
TAG = 'union-single0.5-13det-1797ba'
SOURCES = {
    'cardiode': (cardiode_a, cardiode_conditions),
    'tab': (lambda: condition_a_dir() / 'tab_A.jsonl.gz', lambda: work_dir() / 'results/conditions'),
    'ontonotes': (lambda: condition_a_dir() / 'ontonotes_A.jsonl.gz', lambda: work_dir() / 'results/conditions'),
    'enron': (lambda: condition_a_dir() / 'enron_A.jsonl.gz', lambda: work_dir() / 'results/conditions'),
}

out = {}
for corpus, (a_path, cond_root) in SOURCES.items():
    documents = list(iter_documents(a_path()))
    patch_path = cond_root() / f'{corpus}_B_{TAG}.patch.jsonl'
    patchset = read_patchset(patch_path)
    check = check_current(documents, patchset)
    replaced = {p.doc_id: tuple(Span(e.old_start, e.old_end, '', e.entity_type) for e in p.entries)
                for p in patchset.patches}
    print(f'{corpus}: {patch_path.name}, digests verified ({check["patches"]} patches)', flush=True)

    for label, types in (('person', IDENTITY), ('replaced', REPLACED)):
        people, exposed_people = set(), set()
        pairs = exposed_pairs = mentions = exposed_mentions = 0
        docs = exposed_docs = 0
        cases, exposed_cases = set(), set()
        region = {'header': 0, 'body': 0}
        clipped = {'clipped': 0, 'missed': 0}
        real_cases = True
        for document in documents:
            case, real = case_of(document, corpus)
            real_cases = real_cases and real
            cases.add(case)
            tokens = tokenise(document.text)
            caught = covered_tokens(tokens, replaced.get(document.doc_id, ()))
            cut = document.text.find('\n\n')
            cut = len(document.text) if cut < 0 else cut
            per_entity = defaultdict(bool)
            any_left = False
            for mention in document.mentions:
                if mention.type not in types:
                    continue
                idx = covered_tokens(tokens, (mention.span,))
                if not idx:
                    continue
                mentions += 1
                key = mention.gold_entity_id or mention.mention_id
                people.add(key)
                left = bool(idx - caught)
                if left:
                    # A mention can survive two ways, and they are different failures. Either the
                    # detector never found it, or it found it and the engine's overlap rule wrote a
                    # shorter span over part of it, leaving the rest. The second is invisible to any
                    # metric computed on the union of detected spans rather than on the release.
                    clipped['clipped' if (idx & caught) else 'missed'] += 1
                per_entity[key] = per_entity[key] or left
                if left:
                    exposed_mentions += 1
                    any_left = True
                    exposed_people.add(key)
                    exposed_cases.add(case)
                    if corpus == 'enron':
                        region['header' if mention.span.start < cut else 'body'] += 1
            docs += 1
            exposed_docs += int(any_left)
            for key, left in per_entity.items():
                pairs += 1
                exposed_pairs += int(left)
        r = {'distinct_people': len(people), 'distinct_people_exposed': len(exposed_people),
             'entity_document_pairs': pairs, 'entity_document_pairs_exposed': exposed_pairs,
             'mentions': mentions, 'mentions_exposed': exposed_mentions,
             'documents': docs, 'documents_exposed': exposed_docs,
             'cases': len(cases), 'cases_exposed': len(exposed_cases),
             'cases_are_real': real_cases,
             'exposed_mentions_clipped': clipped['clipped'],
             'exposed_mentions_never_found': clipped['missed']}
        if corpus == 'enron':
            r['exposed_mentions_by_region'] = region
        out.setdefault(corpus, {})[label] = r
        print(f"  {label:8s} people {r['distinct_people_exposed']:>6,}/{r['distinct_people']:>7,}"
              f" = {r['distinct_people_exposed']/max(r['distinct_people'],1):6.2%}"
              f"   pairs {r['entity_document_pairs_exposed']:>7,}/{r['entity_document_pairs']:>8,}"
              f"   docs {r['documents_exposed']:>6,}/{r['documents']:>6,}"
              f"   cases {r['cases_exposed']:>5,}/{r['cases']:>6,}"
              f"   clipped {clipped['clipped']:,} missed {clipped['missed']:,}" + (
                  f"   header/body {region['header']:,}/{region['body']:,}" if corpus == 'enron' else ''),
              flush=True)

json.dump(out, open('results/detection/exposure_from_release.json', 'w'), indent=1)
print('wrote results/detection/exposure_from_release.json')
