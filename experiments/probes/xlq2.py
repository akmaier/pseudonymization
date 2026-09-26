"""How much of CodEAlltag_XL is usable? stat() every file; read only those above the cut."""
import os, collections, json, time

import os
C = os.path.join(os.environ.get("PSEUDONYMKIT_CORPORA",
                                          "corpora"), "codealltag")
SEGS = ["EVENTS", "FINANCE", "GERMAN", "MOVIES", "PHILOSOPHY", "TEENS", "TRAVELS"]
BANDS = [0, 1, 25, 50, 100, 200, 400, 800, 1600, 3200, 1 << 30]
CUT = 200
REPL = b"\xef\xbf\xbd"
t0 = time.time()
out = {}

for seg in SEGS:
    root = f"{C}/pXL_{seg}"
    band = collections.Counter()
    n = total = above = damaged = 0
    for base, _, files in os.walk(root):
        for f in files:
            if not f.endswith(".txt"):
                continue
            path = os.path.join(base, f)
            try:
                size = os.stat(path).st_size
            except OSError:
                continue
            n += 1
            total += size
            for i in range(len(BANDS) - 1):
                if BANDS[i] <= size < BANDS[i + 1]:
                    band[BANDS[i]] += 1
                    break
            if size >= CUT:
                above += 1
                try:
                    if REPL in open(path, "rb").read():
                        damaged += 1
                except OSError:
                    pass
    out[seg] = {"files": n, "bytes": total, "above_cut": above,
                "damaged_above_cut": damaged, "eligible": above - damaged,
                "bands": dict(sorted(band.items()))}
    print(f"[{time.time()-t0:6.0f}s] {seg:<11}{n:>7} files {total/1e6:>7.1f} MB  "
          f">={CUT}B {above:>7}  damaged {damaged:>6}  eligible {above-damaged:>7}", flush=True)

pool = collections.Counter()
for seg in SEGS:
    for k, v in out[seg]["bands"].items():
        pool[k] += v
tot = sum(pool.values())
print("\nsize bands over all 7 segments:")
cum = 0
for k in sorted(pool):
    cum += pool[k]
    print(f"  [{k:>5} .. ) {pool[k]:>9}  {100*pool[k]/tot:5.2f} %   cumulative below top {100*cum/tot:6.2f} %")
print()
elig = {s: out[s]["eligible"] for s in SEGS}
print(f"eligible per segment: {elig}")
print(f"smallest segment eligible: {min(elig.values())}  -> equal-n cap {min(elig.values())}")
print(f"total eligible: {sum(elig.values())} of {tot} ({100*sum(elig.values())/tot:.1f} %)")
json.dump(out, open("data/codealltag_xl_quality.json", "w"), indent=2)
print("written: data/codealltag_xl_quality.json")
