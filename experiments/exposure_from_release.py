'''Exposure measured against the released text itself, under every denominator.

Two earlier routes disagreed — leakage_profile.py combines cached spans through load_pool +
combine, this session's check re-derived them through detected_documents — and on TAB they
differ by five exposed people out of seventy. Neither is authoritative. What was *released* is the
condition-B patch set, whose old_start/old_end are the spans actually overwritten, after the
engine's own overlap-skipping rule. Those are what an attacker sees, so those are what exposure is
scored against here.

**Survival is "not covered by a textually effective replacement"** (plan §8.2, fixed 2026-10-03).
This script used to count a gold token as caught when *any* patch entry overlapped it. That is true
under C, where every detected type becomes ``[TYPE]``, and false under B: ``DATETIME``, ``QUANTITY``
and ``MISC`` are rendered by ``PassThrough``, which returns the original surface, so the entry
exists with the right offsets and the released text is unchanged. On CARDIO:DE that is 82 % of
mentions — 45,176 of 55,154 are dates. Under the old definition those counted as protected, so B
looked almost perfectly protective and the B-versus-C comparison compared an artefact of the
definition. ``construction.changed_text`` now decides it by comparing the replacement against the
text it overwrote, which covers the pass-through types without naming them and also catches a drawn
surrogate that collides with its own original. The count of entries that changed nothing is
reported per corpus rather than left implicit.

Denominators are kept apart because they were being conflated. leakage_profile.py builds its
entity map inside the per-document loop, so its "entities" are entity-document pairs: a person in
forty Enron messages counts forty times, which is how an 18 % figure came to be reported as the
share of *people*. Enron is additionally split at the header boundary, because 86 % of its gold
identifier tokens sit in the From/To/Cc/Subject block and a name surviving there is a different
failure from one surviving in a sentence.
'''
import argparse, json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, 'src'); sys.path.insert(0, 'experiments')
from pseudonymkit.conditions import CONSTRUCTED, POOLED
from pseudonymkit.construction import (
    changed_text, check_current, effective_spans, read_patchset,
)
from pseudonymkit.metrics.detection import covered_tokens, tokenise
from pseudonymkit.paths import cardiode_a, cardiode_conditions, condition_a_dir, work_dir
from pseudonymkit.domain import Span
from pseudonymkit.serialisation import iter_documents
from leakage_profile import case_of

REPLACED = frozenset(POOLED) | frozenset(CONSTRUCTED)
IDENTITY = frozenset({'PERSON'})
DEFAULT_TAG = 'union-single0.5-13det-1797ba'

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--tag', default=DEFAULT_TAG, help='which patch set to score exposure against')
ap.add_argument('--condition', default='B', choices=['B', 'C'],
                help='B is the surrogate release, C the placeholder one. Under C every detected '
                     'type is replaced by a visibly different string, so the two differ in '
                     'exactly the way the effectiveness rule above exists to measure.')
ap.add_argument('--corpora', nargs='+', default=None)
ap.add_argument('--out', type=Path, default=Path('results/detection'))
args = ap.parse_args()
TAG = args.tag
SOURCES = {
    'cardiode': (cardiode_a, cardiode_conditions),
    'tab': (lambda: condition_a_dir() / 'tab_A.jsonl.gz', lambda: work_dir() / 'results/conditions'),
    'ontonotes': (lambda: condition_a_dir() / 'ontonotes_A.jsonl.gz', lambda: work_dir() / 'results/conditions'),
    'enron': (lambda: condition_a_dir() / 'enron_A.jsonl.gz', lambda: work_dir() / 'results/conditions'),
}

out = {}
for corpus, (a_path, cond_root) in SOURCES.items():
    if args.corpora and corpus not in args.corpora:
        continue
    documents = list(iter_documents(a_path()))
    patch_path = cond_root() / f'{corpus}_{args.condition}_{TAG}.patch.jsonl'
    if not patch_path.exists():
        # Report, do not substitute (§1): a missing patch set is a cell that has not been built,
        # not a corpus with nothing to measure.
        print(f'{corpus}: no patch set at {patch_path} — SKIPPED, not substituted', flush=True)
        continue
    patchset = read_patchset(patch_path)
    check = check_current(documents, patchset)
    text_of = {d.doc_id: d.text for d in documents}
    replaced, entries_total, entries_identical = {}, 0, 0
    # The superseded rule is kept and scored beside the corrected one, so the size of the
    # correction is an artefact on disk rather than a remark in a commit message. It is also the
    # measurement the plan's threat table lists as "rate currently unknown": an unchanged-type
    # entry can win the engine's overlap rule and leave the name it overlapped in clear text while
    # still looking, to any metric computed on entry offsets, like a replacement.
    any_overlap = {}
    identical_types = defaultdict(int)
    for patch in patchset.patches:
        text = text_of.get(patch.doc_id, '')
        replaced[patch.doc_id] = effective_spans(patch, text)
        any_overlap[patch.doc_id] = tuple(
            Span(e.old_start, e.old_end, '', e.entity_type) for e in patch.entries)
        entries_total += len(patch.entries)
        for entry in patch.entries:
            if not changed_text(entry, text):
                entries_identical += 1
                identical_types[entry.entity_type] += 1
    entries_effective = entries_total - entries_identical
    print(f'{corpus}: {patch_path.name}, digests verified ({check["patches"]} patches)', flush=True)
    print(f'  entries {entries_total:,}: {entries_effective:,} changed the text, '
          f'{entries_identical:,} = {entries_identical / max(entries_total, 1):.1%} did not'
          + (f' ({", ".join(f"{t} {n:,}" for t, n in sorted(identical_types.items(), key=lambda kv: -kv[1])[:4])})'
             if identical_types else ''), flush=True)

    for label, types in (('person', IDENTITY), ('replaced', REPLACED)):
        people, exposed_people, any_people = set(), set(), set()
        pairs = exposed_pairs = mentions = exposed_mentions = 0
        exposed_mentions_any = hidden_by_identical = 0
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
            caught_any = covered_tokens(tokens, any_overlap.get(document.doc_id, ()))
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
                if idx - caught_any:
                    exposed_mentions_any += 1
                    any_people.add(key)
                elif left:
                    # Overlapped by an entry that wrote the same characters back. The old rule
                    # called this protected; the released text says otherwise.
                    hidden_by_identical += 1
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
        r['condition'] = args.condition
        r['tag'] = TAG
        r['patch_entries'] = entries_total
        r['patch_entries_effective'] = entries_effective
        r['patch_entries_identical'] = entries_identical
        r['patch_entries_identical_by_type'] = dict(identical_types)
        r['superseded_any_overlap_rule'] = {
            'mentions_exposed': exposed_mentions_any,
            'distinct_people_exposed': len(any_people),
            'mentions_hidden_by_an_identical_replacement': hidden_by_identical,
        }
        out.setdefault(corpus, {})[label] = r
        print(f"  {label:8s} people {r['distinct_people_exposed']:>6,}/{r['distinct_people']:>7,}"
              f" = {r['distinct_people_exposed']/max(r['distinct_people'],1):6.2%}"
              f"   pairs {r['entity_document_pairs_exposed']:>7,}/{r['entity_document_pairs']:>8,}"
              f"   docs {r['documents_exposed']:>6,}/{r['documents']:>6,}"
              f"   cases {r['cases_exposed']:>5,}/{r['cases']:>6,}"
              f"   clipped {clipped['clipped']:,} missed {clipped['missed']:,}"
              f"   [superseded rule: {exposed_mentions_any:,} mentions, {len(any_people):,} people;"
              f" {hidden_by_identical:,} mentions it hid behind an identical replacement]" + (
                  f"   header/body {region['header']:,}/{region['body']:,}" if corpus == 'enron' else ''),
              flush=True)

args.out.mkdir(parents=True, exist_ok=True)
suffix = '' if args.condition == 'B' else f'_{args.condition}'
destination = args.out / f'exposure_from_release{suffix}.json'
json.dump({'condition': args.condition, 'tag': TAG, 'corpora': out},
          open(destination, 'w'), indent=1)
print(f'wrote {destination}')
