"""Full-corpus measurement of the .onf route: detokenised text + gold spans on one index."""
import sys, re, collections, unicodedata
sys.path.insert(0, ""${PSEUDONYMKIT_WORK:-$PWD}"")
sys.path.insert(0, "src")
from pathlib import Path
from onto_onf2 import parse_onf, align, span_of, norm_token, strip_marks, TRACE
from pseudonymkit.adapters import ontonotes as ON

ONF = Path("data/onto_onf/ontonotes-release-5.0/data/files/data")
NAME = Path("data/ontonotes")

agg = collections.defaultdict(collections.Counter)
badex = collections.defaultdict(list)
for lang in ("english", "chinese", "arabic"):
    for np in sorted((NAME / lang).rglob("*.name")):
        rel = np.relative_to(NAME / lang).with_suffix(".onf")
        op = ONF / lang / "annotations" / rel
        A = agg[lang]
        A["docs"] += 1
        if not op.exists():
            A["onf_missing"] += 1; continue
        ntext, nents = ON.parse_name(np.read_text("utf-8", errors="replace"))
        n_onf_name = n_onf_coref = 0
        for s in parse_onf(op.read_text("utf-8", errors="replace")):
            A["sent"] += 1
            spans, unaligned, leftover = align(s["tokens"], s["plain"], lang)
            A["tok"] += len(s["tokens"])
            A["tok_trace"] += sum(1 for t in s["tokens"] if TRACE.match(t))
            A["tok_unaligned"] += len(unaligned)
            if not unaligned and not leftover:
                A["sent_clean"] += 1
            elif not unaligned:
                A["sent_leftover_only"] += 1
            n_onf_name += len(s["names"]); n_onf_coref += len(s["corefs"])
            for lab, i, j, surf in s["names"]:
                A["onf_name"] += 1
                sp = span_of(spans, i, j)
                if sp is None:
                    A["name_lost"] += 1; continue
                got = s["plain"][sp[0]:sp[1]]
                want = " ".join(norm_token(t, lang) for t in s["tokens"][i:j+1])
                g, w = got.replace(" ", ""), want.replace(" ", "")
                if lang == "arabic":
                    g, w = strip_marks(g), strip_marks(w)
                if g == w:
                    A["name_ok"] += 1
                else:
                    A["name_mismatch"] += 1
                    if len(badex[lang]) < 8:
                        badex[lang].append((want, got))
            for typ, cid, i, j, surf in s["corefs"]:
                A["onf_coref"] += 1
                if span_of(spans, i, j) is None:
                    A["coref_lost"] += 1
        A["name_file_ents"] += len(nents)
        A["onf_name_ann"] += n_onf_name
        A["onf_coref_ann"] += n_onf_coref

hdr = ["docs","sent","sent_clean","sent_leftover_only","tok","tok_trace","tok_unaligned",
       "name_file_ents","onf_name_ann","name_ok","name_mismatch","name_lost",
       "onf_coref_ann","coref_lost"]
for lang in agg:
    A = agg[lang]
    print(f"\n### {lang}")
    for k in hdr:
        print(f"   {k:22} {A[k]:10d}")
    print(f"   sentences fully clean:      {100*A['sent_clean']/max(A['sent'],1):6.2f}%")
    print(f"   + leftover-only:            {100*(A['sent_clean']+A['sent_leftover_only'])/max(A['sent'],1):6.2f}%")
    print(f"   non-trace tokens unaligned: {A['tok_unaligned']} / {A['tok']-A['tok_trace']} = "
          f"{100*A['tok_unaligned']/max(A['tok']-A['tok_trace'],1):.3f}%")
    print(f"   .onf NE annotations vs .name file spans: {A['onf_name_ann']} vs {A['name_file_ents']}")
    for w, g in badex[lang][:5]:
        print(f"     mismatch want={w!r} got={g!r}")
