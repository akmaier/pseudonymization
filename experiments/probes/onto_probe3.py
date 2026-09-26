"""Can .onf be detokenised faithfully, and do its Leaves carry name+coref on one index?"""
import sys, re, collections, random
sys.path.insert(0, ""${PSEUDONYMKIT_WORK:-$PWD}"")
sys.path.insert(0, "src")
from onto_onf import parse_onf, align
from pathlib import Path

B = Path("data/onto_probe/ontonotes-release-5.0/data/files/data")
NAMEROOT = Path("data/ontonotes")

# .onf files present under the extracted probe tree, keyed like the adapter's doc ids
onf = {}
for p in B.rglob("*.onf"):
    parts = p.relative_to(B).parts   # <lang>/annotations/<genre>/.../stem.onf
    lang = parts[0]
    tail = parts[2:]
    onf[(lang, "/".join(tail)[:-4])] = p
print("onf files extracted:", len(onf))

# which .name documents have an .onf here
names = {}
for lang in ("english", "chinese", "arabic"):
    for p in (NAMEROOT / lang).rglob("*.name"):
        names[(lang, str(p.relative_to(NAMEROOT / lang))[:-5])] = p
print(".name documents:", len(names))
have = [k for k in names if k in onf]
print(".name documents with an extracted .onf:", len(have))
missing_by_lang = collections.Counter(k[0] for k in names if k not in onf)
print("missing (extraction still running or genuinely absent):", dict(missing_by_lang))

random.seed(0)
for lang in ("english", "chinese", "arabic"):
    pool = [k for k in have if k[0] == lang]
    if not pool:
        print(f"\n### {lang}: no .onf sample available yet"); continue
    sample = random.sample(pool, min(150, len(pool)))
    sents = toks = trace = unmatched = 0
    full_ok = 0
    ann_name = ann_coref = 0
    name_span_ok = name_span_bad = 0
    bad_examples = []
    for key in sample:
        blob = onf[key].read_text("utf-8", errors="replace")
        for s in parse_onf(blob):
            sents += 1
            spans, um, consumed = align(s["tokens"], s["plain"], arabic=(lang == "arabic"))
            toks += len(s["tokens"])
            trace += sum(1 for sp in spans if sp is None)
            unmatched += um
            full_ok += bool(consumed and um == 0)
            for kind, label, i, j, surf in s["anns"]:
                if kind == "name":
                    ann_name += 1
                    sub = [spans[k] for k in range(i, min(j + 1, len(spans))) if k < len(spans) and spans[k]]
                    if sub:
                        st, en = sub[0][0], sub[-1][1]
                        got = s["plain"][st:en]
                        want = surf.strip()
                        if got.replace(" ", "") == want.replace(" ", "").replace("-LRB-", "(").replace("-RRB-", ")"):
                            name_span_ok += 1
                        else:
                            name_span_bad += 1
                            if len(bad_examples) < 6:
                                bad_examples.append((want, got))
                    else:
                        name_span_bad += 1
                else:
                    ann_coref += 1
    print(f"\n### {lang}: {len(sample)} documents, {sents} sentences, {toks} treebank tokens")
    print(f"  sentences fully aligned (all non-trace tokens matched, plain consumed): {full_ok}/{sents} = {100*full_ok/max(sents,1):.2f}%")
    print(f"  tokens with no plain-text span (traces + failures): {trace} ({100*trace/max(toks,1):.2f}%)")
    print(f"  NON-trace tokens that failed to match: {unmatched} ({100*unmatched/max(toks,1):.3f}%)")
    print(f"  Leaves annotations: name={ann_name} coref={ann_coref}")
    print(f"  name spans recovered correctly on the detokenised text: {name_span_ok}/{ann_name+0} bad={name_span_bad}")
    for w, g in bad_examples:
        print(f"    want={w!r} got={g!r}")
