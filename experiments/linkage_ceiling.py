'''Why context linkage barely works on CARDIO:DE even before replacement.

AM, 2026-09-26: "The clinical ceiling is very low. Why?"

On unmodified text the structural attack recovers {71.98}% of held-out Enron people and
{2.73}% of CARDIO:DE ones. Both numbers come from the same code over the same fixed similarity,
so the gap is a property of the corpora, and the paper asserts CARDIO:DE's clinical realism is
partial without measuring what that costs the attack. This measures it.

Two quantities, because two independent things have to hold before a linkage attack can succeed.

**The person has to appear twice.** The gallery profile is built from documents *other* than the
one the query comes from, so a person appearing in a single document lands in one half of a
document-disjoint split and can never be recovered. That caps the attack before it ranks anything.

**The profiles have to differ.** Ranking is cosine over surrounding-word counts. If every person in
the corpus is surrounded by the same words, the correct profile is no closer than a wrong one. A
discharge letter puts the same diagnosis, medication and section vocabulary around everyone; an
e-mail correspondent carries their own projects and colleagues. The mean cosine between two
*different* gallery profiles measures exactly this, and is comparable across corpora because it is
scale-free.

Read-only: no model, no GPU, no writes outside results/detection/.
'''
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')

from pseudonymkit.attacks import build_gallery, disjoint_document_split
from pseudonymkit.domain import Corpus
from pseudonymkit.paths import cardiode_a_optional, condition_a_dir
from pseudonymkit.serialisation import iter_documents

ENTITY = 'PERSON'
SEED = 0
PAIR_SAMPLE = 100_000
"""Pairs drawn to estimate the mean cosine. Exhaustive below the cutoff, sampled above it: Enron's
3,697 profiles make 6.8 million pairs, and the estimate is stable long before that."""
EXHAUSTIVE_BELOW = 1_200

SWEEP = Path('results/leakage_sweep')


def cosine(a, b):
    shared = a.keys() & b.keys()
    if not shared:
        return 0.0
    num = sum(a[k] * b[k] for k in shared)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return num / (na * nb) if na and nb else 0.0


def ceiling_from_sweep(corpus: str):
    """The unmodified-text Rank-1 the sweep already recorded for the recommended 13."""
    path = SWEEP / f'{corpus}_PERSON.jsonl'
    if not path.exists():
        return None
    for line in path.open():
        row = json.loads(line)
        if row.get('size') == 13 and row.get('rule') == 'union':
            return row.get('a3_ceiling_rank1')
    return None


def measure(name: str, path: Path) -> dict:
    documents = list(iter_documents(path))
    corpus = Corpus(name, tuple(documents))

    per_identity = defaultdict(set)
    for document in documents:
        for mention in document.mentions:
            if mention.type == ENTITY and mention.gold_entity_id:
                per_identity[mention.gold_entity_id].add(document.doc_id)

    spread = Counter(len(v) for v in per_identity.values())
    identities = len(per_identity)
    gallery_docs, query_docs = disjoint_document_split(corpus, seed=SEED)
    gset, qset = set(gallery_docs), set(query_docs)
    in_both = sum(1 for docs in per_identity.values() if (docs & gset) and (docs & qset))

    gallery = build_gallery(corpus, ENTITY, documents=gallery_docs)
    vectors = [dict(p.context) for p in gallery.values() if p.context]

    rng = random.Random(SEED)
    if len(vectors) <= EXHAUSTIVE_BELOW:
        sims = [cosine(vectors[i], vectors[j])
                for i in range(len(vectors)) for j in range(i + 1, len(vectors))]
        how = f'exhaustive over {len(sims):,} pairs'
    else:
        sims = []
        while len(sims) < PAIR_SAMPLE:
            i, j = rng.randrange(len(vectors)), rng.randrange(len(vectors))
            if i != j:
                sims.append(cosine(vectors[i], vectors[j]))
        how = f'{PAIR_SAMPLE:,} pairs sampled at seed {SEED}'

    return {
        'documents': len(documents),
        'identities': identities,
        'mean_documents_per_identity': sum(len(v) for v in per_identity.values()) / max(identities, 1),
        'identities_in_one_document': spread[1],
        'identities_in_one_document_share': spread[1] / max(identities, 1),
        'identities_in_both_split_halves': in_both,
        'identities_in_both_split_halves_share': in_both / max(identities, 1),
        'gallery_profiles': len(gallery),
        'mean_cosine_between_different_profiles': statistics.fmean(sims),
        'median_cosine_between_different_profiles': statistics.median(sims),
        'cosine_estimate': how,
        'mean_context_words_per_profile': statistics.fmean(len(v) for v in vectors),
        'unmodified_text_rank1': ceiling_from_sweep(name),
        'split_documents': [len(gallery_docs), len(query_docs)],
        'seed': SEED,
    }


def main() -> int:
    sources = {'enron': condition_a_dir() / 'enron_A.jsonl.gz'}
    cardiode = cardiode_a_optional()
    if cardiode is None:
        print('CARDIO:DE not configured (PSEUDONYMKIT_DUA unset): measuring Enron only. '
              'The comparison this script exists for needs both.', flush=True)
    else:
        sources['cardiode'] = cardiode

    out = {}
    for name, path in sources.items():
        out[name] = measure(name, path)
        r = out[name]
        print(f"== {name}: {r['documents']:,} documents, {r['identities']:,} {ENTITY} identities, "
              f"mean {r['mean_documents_per_identity']:.2f} documents each", flush=True)
        print(f"   in one document only : {r['identities_in_one_document']:,} "
              f"({r['identities_in_one_document_share']:.1%}) -- unreachable by construction")
        print(f"   in both split halves : {r['identities_in_both_split_halves']:,} "
              f"({r['identities_in_both_split_halves_share']:.1%})")
        print(f"   mean cosine between two different profiles: "
              f"{r['mean_cosine_between_different_profiles']:.3f} "
              f"(median {r['median_cosine_between_different_profiles']:.3f}, {r['cosine_estimate']})")
        print(f"   mean context words per profile: {r['mean_context_words_per_profile']:.0f}")
        if r['unmodified_text_rank1'] is not None:
            print(f"   Rank-1 on unmodified text: {100 * r['unmodified_text_rank1']:.2f} %")
        print(flush=True)

    Path('results/detection').mkdir(parents=True, exist_ok=True)
    Path('results/detection/linkage_ceiling.json').write_text(json.dumps(out, indent=1) + '\n')
    print('wrote results/detection/linkage_ceiling.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
