"""Ensemble results on CARDIO:DE: detection, H1 and H5."""
import json, sys, statistics, itertools, collections

det = {}
for line in open("results/detection/cardiode.jsonl"):
    r = json.loads(line)
    det[r["detector"]] = r
leak = {}
for line in open("results/leakage_sweep/cardiode_PERSON.jsonl"):
    r = json.loads(line)
    if "error" not in r:
        leak[r["source"]] = r

def f(v, w=6, p=3):
    return ("{:>" + str(w) + "." + str(p) + "f}").format(v) if isinstance(v, (int, float)) else " " * (w - 1) + "-"

singles = {k: v for k, v in det.items() if v["size"] == 1}
ens = {k: v for k, v in det.items() if v["size"] > 1}
print("sources: {} singletons, {} ensembles, gold {}".format(
    len(singles), len(ens), "yes" if "gold" in det else "no"))

best_single_tok = max(singles.values(), key=lambda r: r["token_recall"])
best_single_ent = max(singles.values(), key=lambda r: r["entity_recall"] or 0)
print("\n--- what ensembling buys (detection) ---")
print("best single, token recall  {:.3f}   {}".format(best_single_tok["token_recall"], best_single_tok["detector"][:44]))
print("best single, entity recall {:.3f}   {}".format(best_single_ent["entity_recall"], best_single_ent["detector"][:44]))
for size in (2, 3):
    sub = [r for r in ens.values() if r["size"] == size]
    if not sub: continue
    bt = max(sub, key=lambda r: r["token_recall"]); be = max(sub, key=lambda r: r["entity_recall"] or 0)
    print("best {}-ensemble tok {:.3f} (+{:.3f})  ent {:.3f} (+{:.3f})".format(
        size, bt["token_recall"], bt["token_recall"] - best_single_tok["token_recall"],
        be["entity_recall"], be["entity_recall"] - best_single_ent["entity_recall"]))

# ---- H1: leakage recomputed at each recall level -------------------------------------------
print("\n--- H1: leakage against detection recall, over {} sources ---".format(len(leak)))
def corr(xs, ys):
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((a-mx)*(b-my) for a, b in zip(xs, ys))
    den = (sum((a-mx)**2 for a in xs) * sum((b-my)**2 for b in ys)) ** 0.5
    return num/den if den else float("nan")
for metric in ("a5_rank1", "a3_rank1", "a2_rho"):
    pairs = [(r["token_recall"], r[metric]) for r in leak.values()
             if isinstance(r.get("token_recall"), float) and isinstance(r.get(metric), float)]
    if len(pairs) > 10:
        print("  recall vs {:<9} r = {:+.3f}   (n={})".format(metric, corr(*zip(*pairs)), len(pairs)))
# banded
print("  by recall band, mean A5 Rank-1:")
bands = collections.defaultdict(list)
for r in leak.values():
    tr, a5 = r.get("token_recall"), r.get("a5_rank1")
    if isinstance(tr, float) and isinstance(a5, float):
        bands[min(int(tr * 5), 4)].append(a5)
for b in sorted(bands):
    lo, hi = b * 0.2, (b + 1) * 0.2
    print("    recall {:.1f}-{:.1f}  n={:<5} A5 Rank-1 {:.3f}".format(lo, hi, len(bands[b]), statistics.fmean(bands[b])))

# ---- H5: LLM-only subset vs the same plus one classical ------------------------------------
print("\n--- H5: does adding one classical detector to an LLMs-only subset help? ---")
by_set = {}
for k, r in det.items():
    if r["size"] >= 1 and r.get("ensemble"):
        by_set[(frozenset(r["ensemble"]), r.get("rule"), r.get("k"))] = r
gains_tok, gains_ent, examples = [], [], []
for (names, rule, k), r in by_set.items():
    if not names or not all(n.startswith("llm:") for n in names):
        continue
    for other, o in by_set.items():
        onames, orule, ok = other
        if orule != rule or ok != k or len(onames) != len(names) + 1:
            continue
        extra = onames - names
        if len(extra) != 1: continue
        added = next(iter(extra))
        if added.startswith("llm:") or not (onames - extra) == names:
            continue
        dt = o["token_recall"] - r["token_recall"]
        de = (o["entity_recall"] or 0) - (r["entity_recall"] or 0)
        gains_tok.append(dt); gains_ent.append(de)
        examples.append((dt, added, "+".join(sorted(names))[:40], rule))
if gains_tok:
    print("  {} (LLM subset, +1 classical) pairs".format(len(gains_tok)))
    print("  token recall gain : mean {:+.3f}  median {:+.3f}  helps in {:.0%} of pairs".format(
        statistics.fmean(gains_tok), statistics.median(gains_tok),
        sum(1 for g in gains_tok if g > 0) / len(gains_tok)))
    print("  entity recall gain: mean {:+.3f}  median {:+.3f}".format(
        statistics.fmean(gains_ent), statistics.median(gains_ent)))
    per = collections.defaultdict(list)
    for dt, added, _, _ in examples: per[added].append(dt)
    print("  which classical detector adds most:")
    for name, gs in sorted(per.items(), key=lambda kv: -statistics.fmean(kv[1])):
        print("    {:<50} mean {:+.3f}  (n={})".format(name[:49], statistics.fmean(gs), len(gs)))
else:
    print("  no matched pairs found")
