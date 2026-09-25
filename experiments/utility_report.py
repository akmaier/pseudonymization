import json, collections, statistics, sys

path = sys.argv[1]
by = collections.defaultdict(dict)          # task -> condition -> {doc_id: score}
for line in open(path):
    r = json.loads(line)
    if not r.get("doc_id") or "score" not in r:
        continue
    by[r["task"]].setdefault(r["condition"], {})[r["doc_id"]] = r["score"]

def pm(values, fmt="{:.4f}", signed=False):
    """``mean±sd`` over documents. ``sd`` is omitted, never printed as zero, below two documents."""
    values = list(values)
    if not values:
        return "n/a"
    body = ("{:+.4f}" if signed else fmt).format(statistics.fmean(values))
    if len(values) < 2:
        return body
    return body + "\u00b1" + fmt.format(statistics.stdev(values)).lstrip("+")


print("{:<30}{:>17}{:>17}{:>17}   {:>18}{:>18}".format(
    "task", "A", "B", "C", "B-A", "C-A"))
for task in sorted(by):
    conds = by[task]
    if "A" not in conds:
        continue
    cells = [pm(conds[c].values()) if c in conds else "n/a" for c in ("A", "B", "C")]
    shared = set(conds.get("A", {})) & set(conds.get("B", {})) & set(conds.get("C", {}))
    # The paired differences, kept rather than averaged away. A and B are scored on the same
    # documents with the same frozen weights, so they are strongly correlated and SD(B-A) is much
    # smaller than either marginal — quoting only the marginals would make a tight effect look
    # like noise.
    dba = [conds["B"][d] - conds["A"][d] for d in shared] if shared else []
    dca = [conds["C"][d] - conds["A"][d] for d in shared] if shared else []
    print("{:<30}{:>17}{:>17}{:>17}   {:>18}{:>18}   n={}".format(
        task, cells[0], cells[1], cells[2],
        pm(dba, signed=True), pm(dca, signed=True), len(shared)))
print("\n  \u00b1 is one sample standard deviation over documents (ddof=1); "
      "the unit of replication is the document, not a fold.")

# paired significance, as §8.3 requires
try:
    from pseudonymkit.metrics.utility import wilcoxon  # type: ignore
except Exception:
    wilcoxon = None
print()
for task in sorted(by):
    conds = by[task]
    if not {"A", "B", "C"} <= set(conds):
        continue
    shared = sorted(set(conds["A"]) & set(conds["B"]) & set(conds["C"]))
    b_worse = sum(1 for d in shared if conds["B"][d] < conds["A"][d])
    c_worse = sum(1 for d in shared if conds["C"][d] < conds["A"][d])
    b_same = sum(1 for d in shared if conds["B"][d] == conds["A"][d])
    c_same = sum(1 for d in shared if conds["C"][d] == conds["A"][d])
    print("{:<30} B: {:>3} worse, {:>3} unchanged | C: {:>3} worse, {:>3} unchanged  (of {})".format(
        task, b_worse, b_same, c_worse, c_same, len(shared)))
