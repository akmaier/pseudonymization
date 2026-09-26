"""Residual artefacts in the ONF plain text, per (lang, genre) - what detokenisation still leaves."""
import sys, re, collections
sys.path.insert(0, ""${PSEUDONYMKIT_WORK:-$PWD}"")
sys.path.insert(0, "src")
from pathlib import Path
from onto_onf4 import parse_onf

NAME = Path("data/ontonotes")
ONF = Path("data/onto_onf/ontonotes-release-5.0/data/files/data")
PATS = {
    "LRB/RRB": re.compile(r"-[LR][RCS]B-"),
    "``/''":   re.compile(r"``|''"),
    "split_clitic": re.compile(r"\s(n't|'s|'re|'ve|'ll|'m|'d)\b"),
    "space_b4_punct": re.compile(r"\s[,.;:!?]"),
    "sp-hyph-sp": re.compile(r"\S \- \S"),
    "/. /? /-": re.compile(r"/[.?\-,]"),
    "han_space": re.compile(r"[一-鿿] [一-鿿]"),
    "%pw": re.compile(r"%\w+"),
}
now = collections.defaultdict(collections.Counter)
chars = collections.Counter()
for lang in ("english", "chinese", "arabic"):
    for np in sorted((NAME / lang).rglob("*.name")):
        rel = np.relative_to(NAME / lang)
        op = ONF / lang / "annotations" / rel.with_suffix(".onf")
        t = " ".join(s["plain"] for s in parse_onf(op.read_text("utf-8", errors="replace")))
        k = (lang, rel.parts[0])
        chars[k] += len(t)
        for n, p in PATS.items():
            now[k][n] += len(p.findall(t))
names = list(PATS)
print(f"{'lang/genre':22}{'chars':>10}" + "".join(f"{n[:12]:>15}" for n in names))
tot = collections.Counter()
for k in sorted(now):
    print(f"{k[0][:3]+'/'+k[1]:22}{chars[k]:10d}" + "".join(f"{now[k][n]:15d}" for n in names))
    tot.update(now[k])
print("TOTAL:", dict(tot), "chars:", sum(chars.values()))
