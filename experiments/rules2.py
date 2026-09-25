"""Overlap-based (entity-level) precision/recall per rule, against CARDIO:DE gold."""
import sys, collections, bisect
sys.path.insert(0, "src")
from pseudonymkit.construction import detected_documents
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.paths import cardiode_a

docs = list(iter_documents(cardiode_a()))
cache = DetectorCache("results/detector_cache", "cardiode")
dets = sorted(p.stem.replace("__", "/") for p in cache.root.glob("*.jsonl"))

gold = {d.doc_id: sorted((m.span.start, m.span.end, m.type) for m in d.mentions) for d in docs}

def overlaps(spans, s, e):
    """Gold spans overlapping [s,e)."""
    lo = bisect.bisect_left(spans, (s - 200, 0, ""))
    out = []
    for gs, ge, gt in spans[lo:]:
        if gs >= e: break
        if ge > s: out.append((gs, ge, gt))
    return out

print(f"{'rule':<11}{'spans':>8}{'P':>7}{'R':>7}{'P|type':>8}   per-type precision (n>=300)")
for label, rule, kw in [("union","union",{}), ("vote3","vote",{"k":3}), ("vote5","vote",{"k":5}),
                        ("vote8","vote",{"k":8}), ("vote11","vote",{"k":11})]:
    built, _ = detected_documents(docs, cache, dets, rule=rule, rule_kwargs=kw)
    tp = tpt = pred = 0
    covered = collections.defaultdict(set)
    per = collections.defaultdict(lambda: [0, 0])
    for d in built:
        g = gold[d.doc_id]
        for m in d.mentions:
            pred += 1; per[m.type][1] += 1
            hits = overlaps(g, m.span.start, m.span.end)
            if hits:
                tp += 1
                for h in hits: covered[d.doc_id].add(h)
                if any(h[2] == m.type for h in hits):
                    tpt += 1; per[m.type][0] += 1
    n_gold = sum(len(v) for v in gold.values())
    rec = sum(len(v) for v in covered.values()) / n_gold
    shown = sorted(((t[0]/t[1], k) for k, t in per.items() if t[1] >= 300))
    print(f"{label:<11}{pred:>8}{tp/max(pred,1):>7.3f}{rec:>7.3f}{tpt/max(pred,1):>8.3f}   "
          + "  ".join(f"{k} {p:.2f}" for p, k in shown))
