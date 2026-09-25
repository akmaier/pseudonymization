'''Does the residual leak carry the residual linkage?

AM, 2026-09-25: "given that we put surrogates, what is the actual risk that any of the sparsely
leaked information is actually used to re-ID?"

The recommended Enron release still names a person in clear text in 1.6 % of person-document
occurrences, and context linkage recovers 0.0093 of held-out people against 1/3697 chance.  Those
two facts are reported side by side and no experiment connects them.  Arithmetic suggests they
might be the same fact -- 0.0160 x 0.7198 (the unmodified-text ceiling) = 0.0115, close to the
0.0093 observed -- but that assumes leaked mentions are no more linkable than average, which is
exactly what is untested.

So: build the counterfactual release in which the detector missed nothing, by unioning the
recommended 13 with the corpus's own PERSON annotations, and run the identical attacks over it.
Only PERSON is added.  Unioning the whole gold would also replace organisations, locations and
dates, changing far more than the leak and confounding the answer.

  arm "release"       the 13-detector union, exactly as shipped -- a control: it must reproduce
                      the sweep's 0.009287 / 0.039351, or the harness differs and nothing else
                      here can be read
  arm "oracle-person" the same union plus gold PERSON, so person leakage is zero by construction

If A3 falls to chance the leak is the whole residual risk.  If it holds near 0.0093 the leak is
incidental and the surrogate context carries it.  A5 is run the same way, on the same folds and
seed, because the learned attack already exceeds what leakage alone predicts.
'''
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, 'src')
sys.path.insert(0, 'experiments')

from pseudonymkit.attacks import (
    LearnedLinkage,
    StructuralLinkage,
    build_gallery,
    build_queries,
    disjoint_document_split,
    truth_map,
)
from pseudonymkit.construction import construct, detected_documents, to_pseudonymised_corpus
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.domain import Corpus, Mention
from pseudonymkit.metrics.detection import covered_tokens, tokenise
from pseudonymkit.serialisation import iter_documents
from score_detection import CORPORA

from build_BC import inventory_for, read_key

CORPUS = 'enron'
ENTITY = 'PERSON'
SEED = 0
FOLDS = 5
T0 = time.time()


def log(message: str) -> None:
    print(f'[{time.time() - T0:7.1f}s] {message}', flush=True)


def exposed_person_mentions(documents, spans_by_doc) -> tuple[int, int]:
    """Gold PERSON mentions with at least one token no span covers, and the total."""
    left = total = 0
    for document in documents:
        tokens = tuple(tokenise(document.text))
        caught = covered_tokens(tokens, spans_by_doc.get(document.doc_id, ()))
        for mention in document.mentions:
            if mention.type != ENTITY:
                continue
            idx = covered_tokens(tokens, (mention.span,))
            if not idx:
                continue
            total += 1
            left += bool(idx - caught)
    return left, total


def main() -> int:
    documents = list(iter_documents(CORPORA[CORPUS]()))
    corpus = Corpus(CORPUS, tuple(documents))
    key = read_key(Path.home() / '.config' / 'pseudonymkit' / 'hmac.key')
    cache = DetectorCache(Path('results/detector_cache'), CORPUS)
    recommended = Path('results/leakage_sweep/large_ensemble.txt').read_text().strip().split('+')
    log(f'{CORPUS}: {len(documents):,} documents, {len(recommended)} detectors recommended')

    # The inventory is compiled exactly as the sweep compiles it -- over the union of every cached
    # detector, not over the gold -- so the surrogate pools the two arms draw from are identical.
    detectors_all = sorted(p.stem.replace('__', '/') for p in cache.root.glob('*.jsonl'))
    union_all, _ = detected_documents(documents, cache, detectors_all, 'union')
    cover = {(m.type, d.language) for d in union_all for m in d.mentions}
    inventory, _ = inventory_for({d.language for d in documents}, documents=union_all, cover=cover)
    del union_all
    log(f'  inventory covers {len(cover)} (type, language) pairs')

    gallery_docs, query_docs = disjoint_document_split(corpus, seed=SEED)
    gallery = build_gallery(corpus, ENTITY, documents=gallery_docs)
    log(f'  gallery {len(gallery):,} profiles; split {len(gallery_docs):,}/{len(query_docs):,}')

    detected, _ = detected_documents(documents, cache, recommended, 'union')
    arms = {'release': detected}

    # The counterfactual: every gold PERSON span the ensemble did not already produce, added as
    # though a detector had found it. Types other than PERSON are left exactly as the release has
    # them, so the only difference between the arms is the person leak.
    augmented, added = [], 0
    by_id = {d.doc_id: d for d in detected}
    for document in documents:
        found = by_id[document.doc_id]
        existing = {(m.span.start, m.span.end) for m in found.mentions}
        extra = []
        for number, mention in enumerate(document.mentions):
            if mention.type != ENTITY:
                continue
            if (mention.span.start, mention.span.end) in existing:
                continue
            extra.append(Mention(doc_id=document.doc_id,
                                 mention_id=f'oracle-{number}',
                                 span=mention.span))
        added += len(extra)
        augmented.append(found.with_mentions(tuple(found.mentions) + tuple(extra)))
    arms['oracle-person'] = augmented
    log(f'  oracle arm adds {added:,} PERSON spans the ensemble did not produce')

    out = {}
    for name, docs in arms.items():
        spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in docs}
        left, total = exposed_person_mentions(documents, spans)
        log(f'{name}: {left:,}/{total:,} gold PERSON mentions still uncovered '
            f'({left / max(total, 1):.2%})')

        patches = construct(docs, corpus=CORPUS, conditions=('B',), inventory=inventory, key=key)
        released = to_pseudonymised_corpus(documents, patches['B'], check=False)
        log(f'  {name}: built condition B, '
            f'{sum(len(p.entries) for p in patches["B"].patches):,} replacements')

        queries = build_queries(released, ENTITY, documents=query_docs)
        truth = truth_map(released, ENTITY)
        a3 = StructuralLinkage().run(queries, gallery, truth, 'deterministic', 'hmac')
        folds = [LearnedLinkage(seed=SEED, folds=FOLDS, fold=f).run(
                     queries, gallery, truth, 'deterministic', 'hmac') for f in range(FOLDS)]
        a5 = [f.rank1 for f in folds]
        out[name] = {
            'uncovered_person_mentions': left, 'person_mentions': total,
            'replacements': sum(len(p.entries) for p in patches['B'].patches),
            'a3_rank1': a3.rank1, 'a3_rank5': a3.rank5, 'a3_queries': a3.queries,
            'a5_rank1': statistics.fmean(a5), 'a5_rank1_sd': statistics.stdev(a5),
            'a5_folds': FOLDS, 'gallery': len(gallery), 'seed': SEED,
        }
        log(f'  {name}: A3 rank-1 {a3.rank1:.6f} over {a3.queries:,} queries, '
            f'A5 rank-1 {statistics.fmean(a5):.6f} +- {statistics.stdev(a5):.6f}')

    chance = 1 / len(gallery)
    out['chance'] = chance
    out['note'] = ('arm "release" is the shipped 13-detector union and must reproduce the sweep; '
                   'arm "oracle-person" adds the corpus PERSON annotations to it, so no person '
                   'mention survives in clear text and any remaining recovery is carried by '
                   'context rather than by the leak')
    Path('results/leakage').mkdir(parents=True, exist_ok=True)
    Path('results/leakage/enron_leak_ablation.json').write_text(json.dumps(out, indent=1) + '\n')

    log('')
    log(f'chance {chance:.6f}  (gallery {len(gallery):,})')
    for name in ('release', 'oracle-person'):
        r = out[name]
        log(f'{name:14s} leak {r["uncovered_person_mentions"]:>6,}  '
            f'A3 {r["a3_rank1"]:.6f} ({r["a3_rank1"] / chance:6.1f}x chance)  '
            f'A5 {r["a5_rank1"]:.6f} +- {r["a5_rank1_sd"]:.6f} '
            f'({r["a5_rank1"] / chance:6.1f}x chance)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
