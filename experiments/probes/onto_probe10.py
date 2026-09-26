import sys, re, collections
sys.path.insert(0, ""${PSEUDONYMKIT_WORK:-$PWD}"")
sys.path.insert(0, "src")
from pathlib import Path
from onto_onf4 import parse_onf
from pseudonymkit.adapters import ontonotes as ON

NAME = Path("data/ontonotes")
ONF = Path("data/onto_onf/ontonotes-release-5.0/data/files/data")

# raw ENAMEX type inventory
types = collections.defaultdict(collections.Counter)
nested = 0
attrs = collections.Counter()
for lang in ("english", "chinese", "arabic"):
    for np in (NAME / lang).rglob("*.name"):
        raw = np.read_text("utf-8", errors="replace")
        for m in re.finditer(r'<ENAMEX TYPE="([^"]+)"([^>]*)>', raw):
            types[lang][m.group(1)] += 1
            for a in re.findall(r'(\w+)=', m.group(2)):
                attrs[a] += 1
        nested += len(re.findall(r"<ENAMEX[^>]*>[^<]*<ENAMEX", raw))
print("raw ENAMEX types:")
allt = collections.Counter()
for l in types: allt.update(types[l])
for t, c in allt.most_common():
    print(f"  {t:14}{c:8d}   mapped-> {ON.TYPE_MAP.get(t, 'MISC (UNMAPPED!)'):12} "
          f"en={types['english'][t]:6d} zh={types['chinese'][t]:6d} ar={types['arabic'][t]:6d}")
print("distinct raw types:", len(allt), " extra ENAMEX attributes:", attrs.most_common())
print("directly nested ENAMEX openings:", nested)

# side-by-side text
for lang, rel in (("english", "nw/wsj/00/wsj_0020"), ("english", "bc/cnn/00/cnn_0000"),
                  ("chinese", "bn/cts/00/cts_0001"), ("arabic", "nw/ann/00/ann_0002")):
    np = NAME / lang / (rel + ".name")
    if not np.exists():
        cand = sorted((NAME / lang / rel.rsplit("/",1)[0]).glob("*.name"))
        if not cand: continue
        np = cand[0]; rel = str(np.relative_to(NAME/lang))[:-5]
    text, ents = ON.parse_name(np.read_text("utf-8","replace"))
    op = ONF / lang / "annotations" / (rel + ".onf")
    plains = [s["plain"] for s in parse_onf(op.read_text("utf-8","replace"))]
    print(f"\n===== {lang}/{rel}")
    print("  ADAPTER TEXT TODAY  :", repr(text[:300]))
    print("  ONF PLAIN (proposed):", repr(" ".join(plains)[:300]))
