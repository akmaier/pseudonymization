import json, sys, statistics
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
rows = [r for r in rows if "error" not in r]
print("{:<46}{:>7}{:>7}{:>7}{:>8}{:>7}{:>16}{:>7}".format(
    "span source", "tokR", "entR", "a2rho", "a3R1", "a3q", "a5R1 (fold sd)", "a5f"))
def num(v, w=7, p=3):
    return ("{:>" + str(w) + "." + str(p) + "f}").format(v) if isinstance(v, (int, float)) else " " * (w - 1) + "-"
def with_sd(value, sd, w=16, p=3):
    """``0.320±0.015`` — the fold spread, which the row has carried all along."""
    if not isinstance(value, (int, float)):
        return " " * (w - 1) + "-"
    body = f"{value:.{p}f}"
    if isinstance(sd, (int, float)):
        body += f"\u00b1{sd:.{p}f}"
    return f"{body:>{w}}"
for r in sorted(rows, key=lambda r: -(r.get("token_recall") or 0)):
    print("{:<46}{}{}{}{}{}{}{}".format(
        r["source"][:45], num(r.get("token_recall")), num(r.get("entity_recall")),
        num(r.get("a2_rho")), num(r.get("a3_rank1"), 8), num(r.get("a3_queries"), 7, 0),
        with_sd(r.get("a5_rank1"), r.get("a5_rank1_sd")), num(r.get("a5_folds"), 7, 0)))
print("\n  a5R1 carries one standard deviation over its cross-validation folds — the only genuine"
      "\n  replicate dispersion here; a2 and a3 are single deterministic passes."
      "\n  a3 ranks against the full gallery, a5 against its own fold's held-out entities, so the"
      "\n  two Rank-1 columns are not yet on a common denominator.")
have = [r for r in rows if isinstance(r.get("token_recall"), float) and isinstance(r.get("a5_rank1"), float)]
if len(have) > 2:
    xs = [r["token_recall"] for r in have]; ys = [r["a5_rank1"] for r in have]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num_ = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    den = (sum((x-mx)**2 for x in xs) * sum((y-my)**2 for y in ys)) ** 0.5
    print("\nH1: correlation between detection recall and A5 leakage over {} sources: {:+.3f}".format(
        len(have), num_/den if den else float("nan")))
