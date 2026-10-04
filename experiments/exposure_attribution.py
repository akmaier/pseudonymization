#!/usr/bin/env python3
"""Why a person mention survived — and on which side of the pipeline it was lost.

`exposure_from_release.py` says how many person mentions the release leaves in clear text. This
says why, one cause per exposed mention, so the causes add up to the total:

* partly overwritten — a shorter replacement covered some of its tokens and not the rest;
* overwritten with its own characters — an unchanged-type replacement (DATETIME, QUANTITY, MISC)
  wrote the same text back (plan §8.2);
* covered only by a CODE span the CODE rule removed (plan §8.6);
* an entry overlaps its characters but none of its tokens;
* detected, but no replacement entry reached it;
* never detected.

It also puts the two sides of one ensemble side by side: what the detectors found (sensitivity over
the union of the ensemble's spans) and what the released text no longer says (the patch set).

Measured on CARDIO:DE, recommended 13-detector union, condition B, 2026-10-04:

    PERSON gold-standard tokens                      4,396
    detection side, union of the 13               0.999773     1 token never found
    release   side, the patch set                 0.987261    56 tokens never overwritten

    37 person mentions exposed, by cause
      31  their PERSON span lost the overlap to an earlier span that misses the name
          (the winner: ORG 18, MISC 8, DATETIME 5)
       3  overwritten with their own characters (an unchanged-type replacement)
       2  partly overwritten
       1  never detected
       0  covered only by a CODE span the rule removed (of 455 it removed)

The engine resolves overlaps by keeping the span that starts first. A title, an organisation or a
date that starts before a longer PERSON span and ends before the name wins, the PERSON span is
skipped, and the name stays in clear text although twelve detectors found it. This is the threat
``experiment_plan_operating_point.md`` §12 lists with its "rate currently unknown".

**Two corrections to the first version of this script (2026-10-03), which are part of the record:**

* It reported that the CODE rule accounted for none of the exposed mentions and called that a
  refutation. The test could not have found anything: the CODE rule runs inside
  ``detected_documents``, before combination, so the spans it compared against had already lost
  every CODE span the rule removes. The rule is now measured on the spans from *before* it.
* It explained the whole gap between the two sides as the engine's overlap rule without measuring
  that, and it labelled as "no overlapping entry at all" a count that never tested for entries.

Paper 1's project page had in fact already reported both routes — route one, the release, and route
two, the detectors (``docs/build_site.py``) — with CARDIO:DE route one at 28 of 1,957
person-document pairs, so the size of the gap was never new.

Read-only over the span cache. No span surface is printed or stored: the CARDIO:DE cache holds
DUA-restricted clinical text, so the artefact carries counts only.

    . config/env.sh
    python experiments/exposure_attribution.py --corpus cardiode
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Sequence

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')

from pseudonymkit.construction import (
    CODE_MIN_LENGTH,
    changed_text,
    code_filter,
    detected_documents,
    effective_spans,
    read_patchset,
)
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.domain import Span
from pseudonymkit.metrics.detection import covered_tokens, tokenise
from pseudonymkit.serialisation import iter_documents
# From run_utility, not from exposure_from_release: that module parses argv at import time -- it is
# a flat script -- so importing it here would make it reject this script's own flags.
from run_utility import SOURCES

DEFAULT_TAG = 'union-single0.5-13det-1797ba'


def ensemble_of(tag: str, pool: Sequence[str]) -> tuple[str, ...] | None:
    """The detectors a patch-set tag was built from, recovered from its fingerprint.

    `run_linear_a4.tag_for` hashes the sorted member names into six hex characters and records the
    member *count* in the tag, so the membership is recoverable by trying the subsets of that size
    — 105 of them for 13 of 15. Recovering it matters because the detection-side number has to come
    from the same ensemble as the release-side one; deriving it from the whole cached pool would
    compare two different ensembles and the gap would be meaningless.

    Returns ``None`` when no subset matches, which happens if the cache has changed since the patch
    set was built. That is reported rather than silently papered over with the full pool.
    """
    rest, _, fingerprint = tag.rpartition('-')
    size_part = rest.rpartition('-')[2]
    if not size_part.endswith('det') or not size_part[:-3].isdigit():
        return None
    size = int(size_part[:-3])
    if size > len(pool):
        return None
    for subset in itertools.combinations(sorted(pool), size):
        digest = hashlib.sha256('\x1f'.join(subset).encode('utf-8')).hexdigest()[:6]
        if digest == fingerprint:
            return subset
    return None


def overlap_losers(spans):
    """``{skipped span: the span that beat it}`` under the engine's own rule.

    ``Pseudonymiser.pseudonymise`` visits mentions sorted by ``(start, -length)`` and skips any whose
    start falls before the end of the last one it replaced. Replayed here on the ensemble's spans,
    because the patch set keeps only a count of skipped mentions, not which ones or why.
    """
    losers = {}
    cursor = 0
    winner = None
    for span in sorted(spans, key=lambda s: (s.start, -(s.end - s.start))):
        if span.start < cursor:
            losers[span] = winner
            continue
        winner = span
        cursor = span.end
    return losers


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus', required=True, choices=sorted(SOURCES))
    ap.add_argument('--tag', default=DEFAULT_TAG)
    ap.add_argument('--condition', default='B', choices=['B', 'C'])
    ap.add_argument('--entity-type', default='PERSON')
    ap.add_argument('--cache', type=Path, default=Path('results/detector_cache'))
    ap.add_argument('--out', type=Path, default=Path('results/detection'))
    args = ap.parse_args()

    a_path, cond_root = SOURCES[args.corpus]
    documents = list(iter_documents(a_path()))
    patch_path = cond_root() / f'{args.corpus}_{args.condition}_{args.tag}.patch.jsonl'
    if not patch_path.exists():
        raise SystemExit(f'no patch set at {patch_path}')
    patchset = read_patchset(patch_path)
    print(f'{args.corpus}: {patch_path.name}', flush=True)

    # The ensemble the patch set was built from, so the CODE spans considered are the ones that
    # were actually in play. The tag names the rule and the member count but not the members, so
    # the pool is taken from the cache and the union is the rule the tag records.
    cache = DetectorCache(args.cache, args.corpus)
    pool = sorted(p.stem.replace('__', '/') for p in cache.root.glob('*.jsonl'))
    members = ensemble_of(args.tag, pool)
    if members is None:
        print(f'  the tag {args.tag} names no subset of the {len(pool)} cached detectors; '
              f'the detection side cannot be derived and is reported as unavailable', flush=True)
        members = pool
        derived_detection = False
    else:
        print(f'  tag resolves to {len(members)} detectors; excluded: '
              f'{[n for n in pool if n not in members]}', flush=True)
        derived_detection = True
    detected, _ = detected_documents(documents, cache, list(members), rule='union')
    detected_spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}
    del detected
    # **The spans before the CODE rule, which is the only place it can be measured.** The rule runs
    # inside ``detected_documents`` (construction.py, before combination), so the spans that call
    # returns have already lost every CODE span it removes. The first version of this script took
    # its "removed" set from them and so could never find anything; it reported zero and called
    # that a refutation. Here the filter is switched off for one call, the union is rebuilt from the
    # same cache, and the removed set is what the real filter drops from it.
    import pseudonymkit.construction as construction
    real_filter = construction.code_filter
    construction.code_filter = lambda spans: tuple(spans)
    try:
        unfiltered, _ = detected_documents(documents, cache, list(members), rule='union')
    finally:
        construction.code_filter = real_filter
    raw_code = {d.doc_id: tuple(m.span for m in d.mentions if m.span.type == 'CODE')
                for d in unfiltered}
    del unfiltered

    patches = {p.doc_id: p for p in patchset.patches}
    counts: dict[str, int] = defaultdict(int)
    gold_tokens = detected_tokens = released_tokens = 0
    exposed_pairs: set[tuple[str, str]] = set()
    attributed: set[tuple[str, str]] = set()

    for document in documents:
        patch = patches.get(document.doc_id)
        if patch is None:
            continue
        tokens = tokenise(document.text)
        effective = covered_tokens(tokens, effective_spans(patch, document.text))
        kept = {(s.start, s.end) for s in code_filter(raw_code.get(document.doc_id, ()))}
        removed = tuple(s for s in raw_code.get(document.doc_id, ())
                        if (s.start, s.end) not in kept)
        removed_cover = covered_tokens(tokens, removed)
        detected_cover = covered_tokens(tokens, detected_spans.get(document.doc_id, ()))
        # Tokens covered only by an entry that wrote the same characters back.
        same = covered_tokens(tokens, tuple(
            Span(e.old_start, e.old_end, '', e.entity_type)
            for e in patch.entries if not changed_text(e, document.text)))

        entry_spans = tuple((e.old_start, e.old_end) for e in patch.entries)
        losers = overlap_losers(detected_spans.get(document.doc_id, ()))
        removed_count = len(removed)
        counts['code_spans_removed_by_the_rule'] += removed_count

        for mention in document.mentions:
            if mention.type != args.entity_type:
                continue
            index = covered_tokens(tokens, (mention.span,))
            if not index:
                continue
            counts['mentions'] += 1
            gold_tokens += len(index)
            detected_tokens += len(index & detected_cover)
            released_tokens += len(index & effective)
            if not (index - effective):
                continue
            counts['mentions_exposed'] += 1
            key = (document.doc_id, mention.gold_entity_id or mention.mention_id)
            exposed_pairs.add(key)
            # One category per exposed mention, tested in this order, so they add up to the total.
            if index & effective:
                cause = 'partly overwritten (clipped by a shorter replacement)'
            elif index & same:
                cause = 'overwritten with its own characters (an unchanged-type replacement)'
            elif index & removed_cover:
                cause = 'covered only by a CODE span the rule removed'
                attributed.add(key)
            elif any(s < mention.span.end and mention.span.start < e for s, e in entry_spans):
                cause = 'an entry overlaps its characters but none of its tokens'
            elif any(covered_tokens(tokens, (lost,)) & index for lost in losers):
                cause = 'its detected span lost the overlap to an earlier span that misses the name'
                for lost, won in losers.items():
                    if covered_tokens(tokens, (lost,)) & index and won is not None:
                        counts[f'  winner type: {won.type} ({won.type_src or "-"})'] += 1
                        break
            elif index & detected_cover:
                cause = 'detected, but no replacement entry reached it'
            else:
                cause = 'never detected'
            counts[f'exposed: {cause}'] += 1

    result = {
        'corpus': args.corpus, 'condition': args.condition, 'tag': args.tag,
        'entity_type': args.entity_type, 'code_min_length': CODE_MIN_LENGTH,
        'detectors_in_pool': len(pool),
        'detectors_in_ensemble': len(members) if derived_detection else None,
        'gold_tokens': gold_tokens,
        # The two sides of the same ensemble. The first is what the detectors found, the second
        # what the released text no longer says, and the gap is the engine's overlap rule.
        'sensitivity_detection_side': (detected_tokens / gold_tokens) if gold_tokens else None,
        'sensitivity_release_side': (released_tokens / gold_tokens) if gold_tokens else None,
        'tokens_never_detected': gold_tokens - detected_tokens,
        'tokens_never_overwritten': gold_tokens - released_tokens,
        'detected_mentions_skipped_by_the_overlap_rule':
            sum(p.skipped for p in patchset.patches),
        'counts': dict(counts),
        'exposed_entity_document_pairs': len(exposed_pairs),
        'exposed_pairs_attributable_to_the_CODE_rule': len(attributed),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f'exposure_attribution_{args.corpus}_{args.condition}.json'
    destination.write_text(json.dumps(result, indent=1), encoding='utf-8')
    if gold_tokens:
        print(f'  {args.entity_type} gold tokens {gold_tokens:,}', flush=True)
        if derived_detection:
            print(f'    detection side, union of the ensemble : '
                  f'{detected_tokens / gold_tokens:.6f}  '
                  f'({gold_tokens - detected_tokens:,} never found)', flush=True)
        print(f'    release   side, the patch set         : '
              f'{released_tokens / gold_tokens:.6f}  '
              f'({gold_tokens - released_tokens:,} never overwritten)', flush=True)
        print(f'    detected mentions skipped by the overlap rule: '
              f'{sum(p.skipped for p in patchset.patches):,}', flush=True)
    for key, value in sorted(counts.items()):
        print(f'  {key:52s} {value:>7,}')
    print(f'  exposed entity-document pairs                        '
          f'{len(exposed_pairs):>7,}')
    print(f'  of which only a CODE span the rule removed had covered '
          f'{len(attributed):>5,}')
    print(f'wrote {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
