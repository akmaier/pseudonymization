#!/usr/bin/env python3
'''Phase 1, the expensive half: what an attacker can count, and what it can flag.

Two quantities per span source, both needed before the safety criterion of plan §7.3 can be
applied, and neither present in the leakage sweep.

**The candidate space.** AM, 2026-09-28: "An attacker would always have access to the number of
pseudonyms or placeholders, right?" Under condition B the surrogate is consistent per entity, so
the distinct surrogate surfaces in the release estimate how many people are in it -- no auxiliary
knowledge, just reading the text. That is the candidate space an attacker actually chooses among,
so chance is 1/N with N counted from the release, not 1/162,240 from a census surname list. What
this script counts is the distinct gold PERSON entities the ensemble replaced, which is what those
surfaces stand for up to collision and fragmentation; both are measured elsewhere and the gap is
reported rather than assumed away.

**The flagging statistics.** The parrot flags a name-like span its own detector failed to tag. For
each of §7.4's four attacker variants this records, against each defender point: how many true
survivors it flags, how many surrogates it mistakes for survivors, and the totals -- i.e. the
recall and precision of survivor-detection, which is the attack's real output.

Phase 1 stand-in (§7.3): the attacker's view is computed over condition-A offsets rather than a
rebuilt release, justified by Bao et al. 2026's finding that surrogate substitution is
detection-neutral. Phase 2 measures the error in that.

Read-only over the cache. CPU, no model calls.
'''
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')

from pseudonymkit.attacks.frequency import _NAME_LIKE
from pseudonymkit.construction import detected_documents
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.domain import Span
from pseudonymkit.metrics.detection import covered_tokens, tokenise
from pseudonymkit.serialisation import iter_documents
from sweep_leakage import CORPORA, parse_label

T0 = time.time()


def log(message: str) -> None:
    print(f'[{time.time() - T0:7.1f}s] {message}', flush=True)


def token_index(documents):
    """Tokens once per document; every set below is an index into this."""
    return {d.doc_id: tuple(tokenise(d.text)) for d in documents}


def gold_person(documents, tokens):
    """doc_id -> {entity_id: frozenset(token indices)} for gold PERSON mentions."""
    out = {}
    for d in documents:
        per = {}
        for m in d.mentions:
            if m.type != 'PERSON' or not m.gold_entity_id:
                continue
            idx = covered_tokens(tokens[d.doc_id], (m.span,))
            if idx:
                per.setdefault(m.gold_entity_id, set()).update(idx)
        if per:
            out[d.doc_id] = {k: frozenset(v) for k, v in per.items()}
    return out


def name_like(documents, tokens):
    """doc_id -> set of token indices the attacker's own crude tagger would look at.

    A2's `_NAME_LIKE` is deliberately not one of the study's detectors and is condition-form
    agnostic: its pattern needs a capital followed by lowercase, so it cannot match `[PERSON]`.
    `capitalised_spans` returns the surfaces only, so the offsets are taken from the pattern
    directly -- passing strings to `covered_tokens` would have silently yielded empty sets.
    """
    out = {}
    for d in documents:
        spans = tuple(Span(m.start(), m.end(), m.group(0), 'PERSON')
                      for m in _NAME_LIKE.finditer(d.text))
        out[d.doc_id] = covered_tokens(tokens[d.doc_id], spans) if spans else set()
    return out


def covered_by(documents, cache, names, rule, kwargs, tokens):
    """doc_id -> set of token indices this span source replaces."""
    detected, _ = detected_documents(documents, cache, list(names), rule=rule, rule_kwargs=kwargs)
    return {d.doc_id: covered_tokens(tokens[d.doc_id], tuple(m.span for m in d.mentions))
            for d in detected}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--sources', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--cache', type=Path, default=Path('results/detector_cache'))
    ap.add_argument('--variants', type=Path, default=None,
                    help='JSON {name: span-source label} for the four attacker variants of §7.4. '
                         'Omit to compute the candidate space only.')
    args = ap.parse_args()

    documents = list(iter_documents(CORPORA[args.corpus]()))
    tokens = token_index(documents)
    log(f'{args.corpus}: {len(documents):,} documents tokenised')
    gold = gold_person(documents, tokens)
    entities = {e for per in gold.values() for e in per}
    log(f'  gold PERSON: {len(entities):,} distinct identities over {len(gold):,} documents')
    candidates = name_like(documents, tokens)
    log(f'  name-like tokens the attacker sees: {sum(len(v) for v in candidates.values()):,}')

    cache = DetectorCache(args.cache, args.corpus)
    attackers = {}
    if args.variants:
        for name, label in json.loads(args.variants.read_text()).items():
            names, rule, kwargs = parse_label(label)
            attackers[name] = (label, covered_by(documents, cache, names, rule, kwargs, tokens))
            log(f'  attacker {name}: {label[:60]}')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.out.exists():
        done = {json.loads(l)['source'] for l in args.out.open()}
        log(f'  resuming: {len(done)} sources already done')

    wanted = [l for l in args.sources.read_text().split() if l and l not in done]
    log(f'  {len(wanted)} span sources to do')

    with args.out.open('a', buffering=1) as handle:
        for n, label in enumerate(wanted, 1):
            names, rule, kwargs = parse_label(label)
            replaced = covered_by(documents, cache, names, rule, kwargs, tokens)
            n_replaced = n_survivor = 0
            survivor_tokens, surrogate_tokens = {}, {}
            for doc_id, per in gold.items():
                cov = replaced.get(doc_id, set())
                surv, surr = set(), set()
                for entity, idx in per.items():
                    if idx & cov:
                        surr |= (idx & cov)
                    else:
                        surv |= idx
                survivor_tokens[doc_id] = surv
                surrogate_tokens[doc_id] = surr
            # distinct identities replaced = the candidate space the attacker can count
            replaced_entities = {e for doc_id, per in gold.items()
                                 for e, idx in per.items() if idx & replaced.get(doc_id, set())}
            survivor_entities = {e for doc_id, per in gold.items()
                                 for e, idx in per.items() if not (idx & replaced.get(doc_id, set()))}
            row = {
                'source': label,
                'candidate_space': len(replaced_entities),
                'survivor_entities': len(survivor_entities),
                'gold_entities': len(entities),
                'survivor_tokens': sum(len(v) for v in survivor_tokens.values()),
                'surrogate_tokens': sum(len(v) for v in surrogate_tokens.values()),
            }
            for aname, (alabel, acov) in attackers.items():
                flagged = tp = fp = 0
                for doc_id, cand in candidates.items():
                    unflagged_by_attacker = cand - acov.get(doc_id, set())
                    flagged += len(unflagged_by_attacker)
                    tp += len(unflagged_by_attacker & survivor_tokens.get(doc_id, set()))
                    fp += len(unflagged_by_attacker & surrogate_tokens.get(doc_id, set()))
                row[f'{aname}_flagged'] = flagged
                row[f'{aname}_true_survivor'] = tp
                row[f'{aname}_surrogate_mistaken'] = fp
                row[f'{aname}_label'] = alabel
            handle.write(json.dumps(row) + '\n')
            if n % 25 == 0:
                log(f'  {n}/{len(wanted)}  {n / max(time.time() - T0, 1) * 3600:.0f}/h')
    log(f'wrote {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
