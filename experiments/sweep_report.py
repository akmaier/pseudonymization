import json, sys
rows = [json.loads(l) for l in open("results/detection/cardiode.jsonl")]
print(f"span sources scored: {len(rows)}")
by = {}
for r in rows:
    by.setdefault(r["size"], []).append(r)
for k in sorted(by):
    label = {0: "gold", 1: "single detector"}.get(k, f"{k}-detector ensemble")
    print(f"  size {k} ({label}): {len(by[k])}")

def show(title, rs, key, extra="precision"):
    print(f"\n{title}")
    for r in sorted(rs, key=lambda r: -(r.get(key) or 0))[:5]:
        name = r["detector"][:50]
        rec = r["token_recall"]; prec = r["precision"]
        iwp = r["information_weighted_precision"]
        er = r["entity_recall"]
        ers = f"{er:.3f}" if er is not None else "  -  "
        print(f"   {name:<52} tokR={rec:.3f} entR={ers} P={prec:.3f} iwP={iwp:.3f}")

singles = [r for r in rows if r["size"] == 1]
ens = [r for r in rows if r["size"] > 1]
show("single detectors, by token recall", singles, "token_recall")
if ens:
    show("ensembles, by token recall", ens, "token_recall")
    show("ensembles with recall >= 0.5, by information-weighted precision",
         [r for r in ens if r["token_recall"] >= 0.5], "information_weighted_precision")
    best = max(ens, key=lambda r: (r["token_recall"] or 0) * (r["information_weighted_precision"] or 0))
    print(f"\nbest recall x iwP product: {best['detector'][:60]}")
    print(f"   size {best['size']}, rule {best['rule']}, tokR={best['token_recall']:.3f}, "
          f"iwP={best['information_weighted_precision']:.3f}")
