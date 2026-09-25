"""Per-rule precision against CARDIO:DE gold — which ensemble stops EF becoming a company."""
import sys, collections
sys.path.insert(0, "src")
from pseudonymkit.construction import detected_documents
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.paths import cardiode_a

docs = list(iter_documents(cardiode_a()))
cache = DetectorCache("results/detector_cache", "cardiode")
dets = sorted(p.stem.replace("__", "/") for p in cache.root.glob("*.jsonl"))

gold = collections.defaultdict(set)      # doc -> {(start,end,type)}
gold_any = collections.defaultdict(set)  # doc -> {(start,end)} regardless of type
for d in docs:
    for m in d.mentions:
        gold[d.doc_id].add((m.span.start, m.span.end, m.type))
        gold_any[d.doc_id].add((m.span.start, m.span.end))

print(f"{'rule':<12}{'spans':>8}{'P(any)':>9}{'R(any)':>9}{'P(typed)':>10}   worst-precision types")
for label, rule, kw in [("union", "union", {}), ("vote3", "vote", {"k": 3}),
                        ("vote5", "vote", {"k": 5}), ("vote8", "vote", {"k": 8}),
                        ("vote11", "vote", {"k": 11}), ("intersect", "intersection", {})]:
    built, _ = detected_documents(docs, cache, dets, rule=rule, rule_kwargs=kw)
    tp_any = tp_typed = pred = 0
    per_type = collections.defaultdict(lambda: [0, 0])   # type -> [tp, pred]
    for d in built:
        g, ga = gold[d.doc_id], gold_any[d.doc_id]
        for m in d.mentions:
            pred += 1
            key = (m.span.start, m.span.end)
            per_type[m.type][1] += 1
            if key in ga:
                tp_any += 1
                if (m.span.start, m.span.end, m.type) in g:
                    tp_typed += 1
                    per_type[m.type][0] += 1
    n_gold = sum(len(v) for v in gold_any.values())
    worst = sorted(((tp / p, t, p) for t, (tp, p) in per_type.items() if p >= 200))[:3]
    print(f"{label:<12}{pred:>8}{tp_any/max(pred,1):>9.3f}{tp_any/max(n_gold,1):>9.3f}"
          f"{tp_typed/max(pred,1):>10.3f}   "
          + ", ".join(f"{t} {pr:.2f} (n={p})" for pr, t, p in worst))
