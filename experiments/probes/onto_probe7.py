"""Definitive: .onf as the single source. Alignment quality, coref coverage, speakers."""
import sys, re, collections
sys.path.insert(0, ""${PSEUDONYMKIT_WORK:-$PWD}"")
sys.path.insert(0, "src")
from pathlib import Path
from onto_onf3 import parse_onf, align, span_of, norm_token, TRACE

ONF = Path("data/onto_onf/ontonotes-release-5.0/data/files/data")
NAME = Path("data/ontonotes")

A = collections.defaultdict(collections.Counter)
fail = collections.defaultdict(collections.Counter)
speakers = collections.defaultdict(lambda: collections.defaultdict(set))  # lang -> speaker -> docs
speaker_docs = collections.Counter()
coref_cross = collections.Counter()
genre_coref = collections.defaultdict(collections.Counter)

for lang in ("english", "chinese", "arabic"):
    for np in sorted((NAME / lang).rglob("*.name")):
        rel = np.relative_to(NAME / lang)
        genre = rel.parts[0]
        op = ONF / lang / "annotations" / rel.with_suffix(".onf")
        C = A[lang]
        C["docs"] += 1
        has_coref_file = np.with_suffix(".coref").exists()
        blocks = list(parse_onf(op.read_text("utf-8", errors="replace")))
        ndoc_coref = 0
        spk = set()
        for s in blocks:
            C["sent"] += 1
            spans, unaligned, leftover = align(s["tokens"], s["plain"], lang)
            C["tok"] += len(s["tokens"])
            C["tok_trace"] += sum(1 for t in s["tokens"] if TRACE.match(t))
            C["tok_unaligned"] += len(unaligned)
            for k in unaligned:
                fail[lang][s["tokens"][k]] += 1
            if not unaligned and not leftover:
                C["sent_clean"] += 1
            C["plain_chars"] += len(s["plain"])
            if s["speaker"]:
                spk.add(s["speaker"])
            for lab, i, j, surf in s["names"]:
                C["name"] += 1
                if span_of(spans, i, j) is None:
                    C["name_lost"] += 1
            for typ, cid, i, j, surf in s["corefs"]:
                C["coref"] += 1
                ndoc_coref += 1
                if span_of(spans, i, j) is None:
                    C["coref_lost"] += 1
        key = (bool(has_coref_file), ndoc_coref > 0)
        coref_cross[(lang, key)] += 1
        genre_coref[(lang, genre)][("file", has_coref_file)] += 1
        genre_coref[(lang, genre)][("onf", ndoc_coref > 0)] += 1
        if spk:
            speaker_docs[lang] += 1
            for s_ in spk:
                speakers[lang][s_].add(str(rel))

for lang in A:
    C = A[lang]
    ntok = C["tok"] - C["tok_trace"]
    print(f"\n### {lang}: {C['docs']} docs, {C['sent']} sentences, {C['plain_chars']} plain chars")
    print(f"  sentences fully aligned : {C['sent_clean']}/{C['sent']} = {100*C['sent_clean']/max(C['sent'],1):.2f}%")
    print(f"  non-trace tokens unaligned: {C['tok_unaligned']}/{ntok} = {100*C['tok_unaligned']/max(ntok,1):.3f}%")
    print(f"  NE annotations {C['name']}, unmappable {C['name_lost']} ({100*C['name_lost']/max(C['name'],1):.3f}%)")
    print(f"  coref annotations {C['coref']}, unmappable {C['coref_lost']} ({100*C['coref_lost']/max(C['coref'],1):.3f}%)")
    print("  top 15 unaligned tokens:", fail[lang].most_common(15))

print("\n=== does .onf carry co-reference for documents with no .coref file? ===")
print("(has .coref file, .onf has coref) -> documents")
for k in sorted(coref_cross): print("  ", k, coref_cross[k])

print("\n=== per-genre coref coverage: .coref file vs .onf ===")
for key in sorted(genre_coref):
    g = genre_coref[key]
    print(f"  {key[0]:8}/{key[1]:3}  .coref file: {g[('file',True)]:5d} of {g[('file',True)]+g[('file',False)]:5d}"
          f"   .onf coref: {g[('onf',True)]:5d}")

print("\n=== speakers ===")
for lang in speakers:
    docs = speaker_docs[lang]
    sp = speakers[lang]
    multi = {k: v for k, v in sp.items() if len(v) > 1}
    print(f"  {lang}: {docs} documents carry Speaker information; {len(sp)} distinct speaker names; "
          f"{len(multi)} appear in >1 document")
    top = sorted(sp.items(), key=lambda kv: -len(kv[1]))[:12]
    print("   top:", [(k, len(v)) for k, v in top])
