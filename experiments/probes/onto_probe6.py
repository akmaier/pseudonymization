"""Why does .onf carry fewer NE annotations than .name, and what fails to align?"""
import sys, re, collections
sys.path.insert(0, ""${PSEUDONYMKIT_WORK:-$PWD}"")
sys.path.insert(0, "src")
from pathlib import Path
from onto_onf2 import parse_onf, align, norm_token, TRACE
from pseudonymkit.adapters import ontonotes as ON

ONF = Path("data/onto_onf/ontonotes-release-5.0/data/files/data")
NAME = Path("data/ontonotes")

print("=== per-document sentence/NE parity, english ===")
diffdocs = collections.Counter()
sent_gap = collections.Counter()
worst = []
for lang in ("english", "chinese", "arabic"):
    tot_name = tot_onf = 0
    docs_equal = docs_more_name = docs_more_onf = 0
    sent_name = sent_onf = 0
    for np in sorted((NAME / lang).rglob("*.name")):
        rel = np.relative_to(NAME / lang).with_suffix(".onf")
        op = ONF / lang / "annotations" / rel
        if not op.exists(): continue
        raw = np.read_text("utf-8", errors="replace")
        n_ename = len(re.findall(r'<ENAMEX TYPE="', raw))
        n_lines = len([l for l in raw.split("\n") if l.strip() and not l.startswith("<DOC") and not l.startswith("</DOC")])
        blocks = list(parse_onf(op.read_text("utf-8", errors="replace")))
        n_onf = sum(len(b["names"]) for b in blocks)
        tot_name += n_ename; tot_onf += n_onf
        sent_name += n_lines; sent_onf += len(blocks)
        if n_ename == n_onf: docs_equal += 1
        elif n_ename > n_onf:
            docs_more_name += 1
            if len(worst) < 400: worst.append((lang, str(rel), n_ename, n_onf, n_lines, len(blocks)))
        else: docs_more_onf += 1
    print(f"{lang}: ENAMEX={tot_name} onf_name={tot_onf}; docs equal={docs_equal} name>onf={docs_more_name} onf>name={docs_more_onf}; "
          f".name text lines={sent_name} .onf sentences={sent_onf}")

print("\nworst 12 (lang, doc, ENAMEX, onf_name, name_lines, onf_sents):")
worst.sort(key=lambda t: t[3] - t[2])
for w in worst[:12]: print("  ", w)

print("\n=== what fails to align, english ===")
fail = collections.Counter()
import random
random.seed(1)
paths = sorted((NAME / "english").rglob("*.name"))
for np in random.sample(paths, 300):
    rel = np.relative_to(NAME / "english").with_suffix(".onf")
    op = ONF / "english" / "annotations" / rel
    if not op.exists(): continue
    for s in parse_onf(op.read_text("utf-8", errors="replace")):
        spans, unaligned, leftover = align(s["tokens"], s["plain"], "english")
        for k in unaligned:
            fail[s["tokens"][k]] += 1
print("top 40 unaligned english tokens:", fail.most_common(40))
print("distinct unaligned token types:", len(fail), "occurrences:", sum(fail.values()))

print("\n=== what fails to align, arabic ===")
fa = collections.Counter()
ctx = []
paths = sorted((NAME / "arabic").rglob("*.name"))
for np in random.sample(paths, 120):
    rel = np.relative_to(NAME / "arabic").with_suffix(".onf")
    op = ONF / "arabic" / "annotations" / rel
    if not op.exists(): continue
    for s in parse_onf(op.read_text("utf-8", errors="replace")):
        spans, unaligned, leftover = align(s["tokens"], s["plain"], "arabic")
        for k in unaligned:
            t = s["tokens"][k]
            fa[norm_token(t, "arabic")] += 1
            if len(ctx) < 10 and k > 0:
                ctx.append((s["tokens"][max(0,k-1):k+2], s["plain"][:90]))
print("top 30 unaligned arabic normalised tokens:", fa.most_common(30))
print("distinct:", len(fa), "occurrences:", sum(fa.values()))
for c in ctx[:6]: print("  ctx:", c)
