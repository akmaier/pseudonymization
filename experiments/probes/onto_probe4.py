"""How much co-reference does the exact-span rule throw away?"""
import sys, collections
sys.path.insert(0, "src")
from pathlib import Path
from pseudonymkit.adapters import ontonotes as ON

ROOT = Path("data/ontonotes")
tot = collections.Counter()
per_lang = collections.defaultdict(collections.Counter)
chain_sizes = collections.Counter()
for lang in ("english", "chinese", "arabic"):
    for np in sorted((ROOT / lang).rglob("*.name")):
        cp = np.with_suffix(".coref")
        text, ents = ON.parse_name(np.read_text("utf-8", errors="replace"))
        if not cp.exists():
            per_lang[lang]["docs_no_coref"] += 1
            per_lang[lang]["ne_no_coref"] += len(ents)
            continue
        ct, cs = ON.parse_coref(cp.read_text("utf-8", errors="replace"))
        mapped, dropped = ON.map_coref_onto_name(text, ct, cs)
        per_lang[lang]["docs"] += 1
        per_lang[lang]["coref_spans_in_file"] += len(cs)
        per_lang[lang]["coref_spans_mapped"] += len(mapped)
        per_lang[lang]["coref_spans_dropped"] += dropped
        exact = {(s, e): c for s, e, c in mapped}
        # containment index
        for (s, e, t) in ents:
            per_lang[lang]["ne"] += 1
            if (s, e) in exact:
                per_lang[lang]["ne_exact"] += 1
                continue
            # smallest mapped coref span containing this NE
            cands = [(ce - cs_, cs_, ce, c) for cs_, ce, c in mapped if cs_ <= s and e <= ce]
            if cands:
                per_lang[lang]["ne_contained"] += 1
            else:
                ov = [1 for cs_, ce, c in mapped if cs_ < e and s < ce]
                if ov:
                    per_lang[lang]["ne_overlap_only"] += 1
                else:
                    per_lang[lang]["ne_unlinked"] += 1
        # chain size distribution on exact matches
        by_chain = collections.Counter()
        for (s, e, t) in ents:
            c = exact.get((s, e))
            if c is not None:
                by_chain[c] += 1
        for c, n in by_chain.items():
            chain_sizes[n] += 1

print(f"{'lang':9}" + "".join(f"{k:>22}" for k in
      ["docs","docs_no_coref","coref_spans_in_file","coref_spans_mapped","coref_spans_dropped"]))
for l in per_lang:
    print(f"{l:9}" + "".join(f"{per_lang[l][k]:>22}" for k in
      ["docs","docs_no_coref","coref_spans_in_file","coref_spans_mapped","coref_spans_dropped"]))
print()
print(f"{'lang':9}{'ne':>10}{'exact':>10}{'contained':>12}{'overlap_only':>14}{'unlinked':>10}{'ne_no_coref_doc':>17}")
for l in per_lang:
    d = per_lang[l]
    print(f"{l:9}{d['ne']:>10}{d['ne_exact']:>10}{d['ne_contained']:>12}{d['ne_overlap_only']:>14}{d['ne_unlinked']:>10}{d['ne_no_coref']:>17}")
tot = collections.Counter()
for l in per_lang: tot.update(per_lang[l])
print("TOTAL:", {k: tot[k] for k in ["ne","ne_exact","ne_contained","ne_overlap_only","ne_unlinked","ne_no_coref","coref_spans_in_file","coref_spans_mapped","coref_spans_dropped"]})
print("\nchains by number of *named* mentions they carry (exact rule):")
for n in sorted(chain_sizes)[:12]:
    print(f"  {n:3d} named mentions: {chain_sizes[n]:7d} chains")
print("  chains with >=2 named mentions:", sum(v for k, v in chain_sizes.items() if k >= 2),
      "of", sum(chain_sizes.values()))
