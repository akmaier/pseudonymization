import sys, re, collections
sys.path.insert(0, ""${PSEUDONYMKIT_WORK:-$PWD}"")
sys.path.insert(0, "src")
from pathlib import Path
from onto_onf4 import parse_onf, align, span_of, norm_token, TRACE, ar_key

ONF = Path("data/onto_onf/ontonotes-release-5.0/data/files/data")
NAME = Path("data/ontonotes")

A = collections.defaultdict(collections.Counter)
fail = collections.defaultdict(collections.Counter)
for lang in ("english", "chinese", "arabic"):
    for np in sorted((NAME / lang).rglob("*.name")):
        rel = np.relative_to(NAME / lang)
        op = ONF / lang / "annotations" / rel.with_suffix(".onf")
        C = A[lang]; C["docs"] += 1
        for s in parse_onf(op.read_text("utf-8", errors="replace")):
            C["sent"] += 1
            spans, unaligned, leftover = align(s["tokens"], s["plain"], lang)
            C["tok"] += len(s["tokens"])
            C["tok_trace"] += sum(1 for t in s["tokens"] if TRACE.match(t))
            C["tok_unaligned"] += len(unaligned)
            for k in unaligned: fail[lang][s["tokens"][k]] += 1
            if not unaligned and not leftover: C["sent_clean"] += 1
            if not unaligned: C["sent_tok_ok"] += 1
            C["chars"] += len(s["plain"])
            for lab, i, j, surf in s["names"]:
                C["name"] += 1
                if span_of(spans, i, j) is None: C["name_lost"] += 1
            for typ, cid, i, j, surf in s["corefs"]:
                C["coref"] += 1
                if span_of(spans, i, j) is None: C["coref_lost"] += 1

for lang in A:
    C = A[lang]; ntok = C["tok"] - C["tok_trace"]
    print(f"\n### {lang}: {C['docs']} docs, {C['sent']} sentences, {C['chars']} chars of detokenised text")
    print(f"  sentences with every token aligned : {C['sent_tok_ok']}/{C['sent']} = {100*C['sent_tok_ok']/C['sent']:.2f}%")
    print(f"  ... and no leftover text           : {C['sent_clean']}/{C['sent']} = {100*C['sent_clean']/C['sent']:.2f}%")
    print(f"  non-trace tokens unaligned: {C['tok_unaligned']}/{ntok} = {100*C['tok_unaligned']/ntok:.4f}%")
    print(f"  NE annotations {C['name']}, unmappable {C['name_lost']} ({100*C['name_lost']/max(C['name'],1):.3f}%)")
    print(f"  coref annotations {C['coref']}, unmappable {C['coref_lost']} ({100*C['coref_lost']/max(C['coref'],1):.3f}%)")
    print("  top unaligned:", fail[lang].most_common(12))

# ---------- Arabic: does .source agree with the ONF plain text? ----------
print("\n=== arabic: .onf Plain vs .source raw ===")
AUX = Path("data/onto_aux/ontonotes-release-5.0/data/files/data")
import difflib
have = miss = 0
agree = collections.Counter()
CLITIC = collections.Counter()
for np in sorted((NAME / "arabic").rglob("*.name")):
    rel = np.relative_to(NAME / "arabic")
    sp = AUX / "arabic" / "annotations" / rel.with_suffix(".source")
    op = ONF / "arabic" / "annotations" / rel.with_suffix(".onf")
    if not sp.exists():
        miss += 1; continue
    have += 1
    src = sp.read_text("utf-8", errors="replace")
    segs = re.findall(r"<seg[^>]*>(.*?)</seg>", src, re.S)
    src_key = ar_key(re.sub(r"\s+", "", " ".join(segs)))
    plains = [s["plain"] for s in parse_onf(op.read_text("utf-8", errors="replace"))]
    onf_key = ar_key(re.sub(r"\s+", "", " ".join(plains)))
    sm = difflib.SequenceMatcher(a=src_key, b=onf_key, autojunk=False)
    m = sum(b.size for b in sm.get_matching_blocks())
    agree["src_chars"] += len(src_key); agree["onf_chars"] += len(onf_key); agree["matched"] += m
    for p in plains:
        for t in p.split():
            if len(t) <= 2 and ar_key(t) in {"و","ب","ل","ك","ف","ال","ه","ها","هم","س","لل"}:
                CLITIC[ar_key(t)] += 1
            CLITIC["__all__"] += 1
print(f"  .source present for {have} of {have+miss} arabic NE documents")
print(f"  whitespace-free, hamza-normalised character agreement (LCS): "
      f"{agree['matched']} matched; source {agree['src_chars']} chars, onf-plain {agree['onf_chars']} chars "
      f"-> {100*agree['matched']/max(agree['onf_chars'],1):.2f}% of the ONF text found in .source")
print("  detached clitic tokens still standing alone in the ONF plain text:",
      {k: v for k, v in CLITIC.most_common(12)})
