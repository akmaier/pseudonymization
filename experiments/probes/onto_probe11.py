"""On the .onf leaf index: how much co-reference can a nesting rule recover, and how ambiguous is it?"""
import sys, collections
sys.path.insert(0, ""${PSEUDONYMKIT_WORK:-$PWD}"")
sys.path.insert(0, "src")
from pathlib import Path
from onto_onf4 import parse_onf
from pseudonymkit.adapters import ontonotes as ON

NAME = Path("data/ontonotes")
ONF = Path("data/onto_onf/ontonotes-release-5.0/data/files/data")
TM = ON.TYPE_MAP

C = collections.Counter()
per_type = collections.defaultdict(collections.Counter)
chain_named = collections.Counter()   # (docs) chain -> named mentions
docs_with_chain = collections.Counter()
cluster_sizes = collections.Counter()
for lang in ("english", "chinese", "arabic"):
    for np in sorted((NAME / lang).rglob("*.name")):
        rel = np.relative_to(NAME / lang)
        op = ONF / lang / "annotations" / rel.with_suffix(".onf")
        has_cf = np.with_suffix(".coref").exists()
        chains = collections.Counter()
        clusters = collections.defaultdict(set)
        for si, s in enumerate(parse_onf(op.read_text("utf-8", errors="replace"))):
            cor = [(i, j, cid) for typ, cid, i, j, _ in s["corefs"]]
            for cid, _, i, j in [(c[2], 0, c[0], c[1]) for c in cor]:
                clusters[cid].add((si, i, j))
            for lab, i, j, surf in s["names"]:
                t = TM.get(lab, "MISC")
                C["ne"] += 1; per_type[t]["ne"] += 1
                if not has_cf:
                    C["ne_nocorefdoc"] += 1; per_type[t]["ne_nocorefdoc"] += 1; continue
                exact = [c for c in cor if c[0] == i and c[1] == j]
                if exact:
                    C["exact"] += 1; per_type[t]["exact"] += 1
                    chains[(si, exact[0][2])] += 0
                    chains[exact[0][2]] += 1
                    continue
                cont = [c for c in cor if c[0] <= i and j <= c[1]]
                if cont:
                    cont.sort(key=lambda c: (c[1] - c[0]))
                    inner = cont[0]
                    # how many NE annotations does that innermost span contain?
                    k = sum(1 for l2, i2, j2, _ in s["names"] if inner[0] <= i2 and j2 <= inner[1])
                    C["contained"] += 1; per_type[t]["contained"] += 1
                    if k == 1:
                        C["contained_unique"] += 1; per_type[t]["contained_unique"] += 1
                        chains[inner[2]] += 1
                    else:
                        C["contained_shared"] += 1; per_type[t]["contained_shared"] += 1
                else:
                    ov = [c for c in cor if c[0] <= j and i <= c[1]]
                    if ov: C["overlap"] += 1; per_type[t]["overlap"] += 1
                    else: C["unlinked"] += 1; per_type[t]["unlinked"] += 1
        for cid, n in chains.items():
            if isinstance(cid, str) and n:
                chain_named[n] += 1
        for cid, ms in clusters.items():
            cluster_sizes[len(ms)] += 1

print("NE co-reference attachment on the .onf leaf index (all 5,994 documents):")
for k in ["ne","exact","contained","contained_unique","contained_shared","overlap","unlinked","ne_nocorefdoc"]:
    print(f"  {k:20} {C[k]:8d}  ({100*C[k]/C['ne']:5.2f}%)")
print("\nby harmonised type:")
print(f"{'type':14}{'ne':>9}{'exact':>9}{'+cont.uniq':>12}{'=linked':>9}{'linked%':>9}")
for t in sorted(per_type, key=lambda x: -per_type[x]["ne"]):
    d = per_type[t]
    linked = d["exact"] + d["contained_unique"]
    print(f"{t:14}{d['ne']:9d}{d['exact']:9d}{d['contained_unique']:12d}{linked:9d}{100*linked/d['ne']:8.1f}%")

print("\nchains carrying N named mentions (exact + unique containment):")
tot = sum(chain_named.values())
ge2 = sum(v for k, v in chain_named.items() if k >= 2)
print(f"  chains with >=1 named mention: {tot}; with >=2: {ge2}")
print("  distribution:", sorted(chain_named.items())[:10])
print("\nfull gold co-reference clusters (all mentions, not just named):")
print("  clusters:", sum(cluster_sizes.values()), " mentions:", sum(k*v for k,v in cluster_sizes.items()))
print("  size distribution head:", sorted(cluster_sizes.items())[:10])
