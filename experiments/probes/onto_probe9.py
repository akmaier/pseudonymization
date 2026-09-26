"""The .speaker layer, and what cross-document identity OntoNotes can actually supply."""
import sys, re, collections
sys.path.insert(0, ""${PSEUDONYMKIT_WORK:-$PWD}"")
sys.path.insert(0, "src")
from pathlib import Path
from pseudonymkit.adapters import ontonotes as ON

AUX = Path("data/onto_aux/ontonotes-release-5.0/data/files/data")
NAME = Path("data/ontonotes")
PLACE = re.compile(r"^(speaker[#_]?\d*|[AB]\d*|(?:[AB],)+[AB]|unknown|_?Anonymous_?|_\d+_|Speaker\d*)$", re.I)

rows = []
for lang in ("english", "chinese", "arabic"):
    for np in sorted((NAME / lang).rglob("*.name")):
        rel = np.relative_to(NAME / lang)
        sp = AUX / lang / "annotations" / rel.with_suffix(".speaker")
        text, ents = ON.parse_name(np.read_text("utf-8", errors="replace"))
        nlines = len([l for l in np.read_text("utf-8", errors="replace").split("\n")
                      if l.strip() and not l.startswith("<DOC") and not l.startswith("</DOC")])
        recs = []
        if sp.exists():
            for l in sp.read_text("utf-8", errors="replace").split("\n"):
                f = l.split()
                if len(f) >= 3:
                    recs.append((f[2], f[3] if len(f) > 3 else "", f[4] if len(f) > 4 else ""))
        rows.append((lang, rel.parts[0], str(rel), nlines, recs, ents))

print(f"{'lang/genre':22}{'docs':>7}{'with .speaker':>15}{'lines==sents':>14}")
by = collections.defaultdict(lambda: [0, 0, 0])
for lang, g, rel, nl, recs, ents in rows:
    k = f"{lang}/{g}"
    by[k][0] += 1
    if recs:
        by[k][1] += 1
        by[k][2] += (len(recs) == nl)
for k in sorted(by):
    print(f"{k:22}{by[k][0]:7d}{by[k][1]:15d}{by[k][2]:14d}")

names = collections.defaultdict(set)     # name -> docs
gender = collections.Counter()
native = collections.Counter()
for lang, g, rel, nl, recs, ents in rows:
    for n, gd, nv in recs:
        names[n].add((lang, rel))
        gender[gd] += 1
        native[nv] += 1
real = {n: d for n, d in names.items() if not PLACE.match(n)}
print(f"\ndistinct speaker labels: {len(names)}; non-placeholder: {len(real)}")
print("gender field:", gender.most_common())
print("nativeness field:", native.most_common(6))
multi = {n: d for n, d in real.items() if len(d) > 1}
print(f"non-placeholder speakers appearing in >1 document: {len(multi)}")
sizes = collections.Counter(len(d) for d in real.values())
print("documents per non-placeholder speaker:", sorted(sizes.items())[:12])
top = sorted(real.items(), key=lambda kv: -len(kv[1]))[:20]
print("top speakers:", [(n, len(d)) for n, d in top])

# does a real speaker name appear as a PERSON ENAMEX anywhere?
person_surfaces = collections.Counter()
for lang, g, rel, nl, recs, ents in rows:
    for s, e, t in ents:
        if t == "PERSON":
            person_surfaces[" ".join(( "").join("").split()) or ""] += 0
# rebuild properly
person_surfaces = collections.Counter()
for lang, g, rel, nl, recs, ents in rows:
    txt = None
    np = NAME / lang / rel
    txt, es = ON.parse_name((NAME / lang / rel).read_text("utf-8", errors="replace"))
    for s, e, t in es:
        if t == "PERSON":
            person_surfaces[txt[s:e]] += 1
def key(n): return n.replace("_", " ").strip().lower()
person_keys = {key(k) for k in person_surfaces}
hit = [n for n in real if key(n) in person_keys]
print(f"\nreal speaker names that also occur as a PERSON ENAMEX: {len(hit)} of {len(real)}")
print("  examples:", hit[:15])
lastname_hit = [n for n in real if any(part.lower() in {p.lower() for k in person_keys for p in k.split()}
                                       for part in n.split("_") if len(part) > 2)]
print(f"real speaker names whose surname occurs in some PERSON mention: {len(lastname_hit)}")

# genre source-prefix identity (blogs, wsj sections, broadcast programmes)
print("\n=== identity handles hidden in the document path ===")
src = collections.defaultdict(set)
for lang, g, rel, nl, recs, ents in rows:
    parts = rel.split("/")
    src[(lang, g)].add(parts[1] if len(parts) > 1 else "")
for k in sorted(src):
    print(f"  {k[0]:8}/{k[1]:3} sources: {len(src[k]):4d}  e.g. {sorted(src[k])[:6]}")
wb = [r for r in rows if r[1] == "wb"]
auth = collections.Counter()
for lang, g, rel, nl, recs, ents in wb:
    stem = rel.split("/")[-1]
    m = re.match(r"^([a-z0-9.]+)_([A-Za-z0-9]+)_", stem)
    auth[(m.group(1), m.group(2)) if m else ("?", stem[:12])] += 1
print(f"\n  wb documents: {len(wb)}; distinct (site, author) handles in the filename: {len(auth)}")
print("  top:", auth.most_common(12))
