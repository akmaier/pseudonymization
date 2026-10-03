#!/usr/bin/env python3
"""Why a person mention survived — and on which side of the pipeline it was lost.

`exposure_from_release.py` says how many are exposed. This says where they went, and it exists
because the number did not match the one paper 1 reports. Measured on CARDIO:DE's recommended
13-detector union, condition B, 2026-10-03:

    PERSON gold tokens                                4,396
    DETECTION side, union of the 13                0.999773     1 token never found
    RELEASE   side, the patch set published        0.987261    56 tokens never overwritten
    detected mentions skipped by the overlap rule     13,440

**Both numbers are right and they measure different things.** 0.9998 is what the detectors found;
0.9873 is what the released text no longer says. The gap is the engine's own rule: a detected
mention that overlaps one already replaced is skipped (``Patch.skipped``), so a span that wins the
overlap can leave the name it overlapped standing while the patch set still records a replacement
in that region. ``experiment_plan_operating_point.md`` §12 lists this as a threat whose *"rate
currently unknown"*; this is the rate.

Two candidate causes were tested and are **not** it:

  * the survival rule (§8.2, corrected 2026-10-03) — a token overlapped only by a replacement that
    wrote the same characters back is no longer counted as caught. Worth 3 of the 37 mentions.
  * the CODE sanity rule (§8.6) — **zero**. No exposed person mention is overlapped by a CODE span
    the rule removed, so filtering degenerate CODE spans uncovered none of them. The hypothesis was
    mine and the measurement refutes it.

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
    raw_code = {d.doc_id: tuple(m.span for m in d.mentions if m.span.type == 'CODE')
                for d in detected}
    detected_spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}
    del detected

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
            survives = bool(index - effective)
            if not survives:
                continue
            counts['mentions_exposed'] += 1
            key = (document.doc_id, mention.gold_entity_id or mention.mention_id)
            exposed_pairs.add(key)
            # Which step left it. Not exclusive by accident: a mention can be overlapped by a
            # removed CODE span *and* by a pass-through entry, so the order states the precedence
            # and the overlap is counted too.
            by_code = bool(index & removed_cover)
            by_identical = bool(index & same)
            if by_code:
                counts['exposed_overlapped_by_a_removed_CODE_span'] += 1
                attributed.add(key)
            if by_identical:
                counts['exposed_overlapped_by_an_identical_replacement'] += 1
            if by_code and by_identical:
                counts['exposed_by_both'] += 1
            if not by_code and not by_identical:
                counts['exposed_with_no_overlapping_entry_at_all'] += 1

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
    print(f'  of which a removed CODE span had overlapped          '
          f'{len(attributed):>7,}')
    print(f'wrote {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
