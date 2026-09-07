# First end-to-end cells — TAB, gold spans

45 cells: normaliser {N0, N2, N4} × policy {deterministic, document, full} × technique {counter,
table, hash, hmac, aes_siv}, opaque-tag surrogates, gold spans, TAB annotator `first`.
1,268 documents, 22,391 PERSON/LOC mentions, 8,701 PERSON chains and 3,603 LOC chains.
Rows in [`results/tab_first_cells.jsonl`](results/tab_first_cells.jsonl); reproduce with
`python experiments/run_cells.py --tab <checkout>` (about 30 seconds).

## 1. H1 holds, and it is not subtle

**Every technique row is identical.** Counter, mapping table, SHA-256, HMAC and AES-SIV produce the
same fragmentation, the same collision rate, the same A2 top-1 and the same rank correlation, in
every one of the nine policy × normaliser combinations.

| policy | Spearman ρ (PERSON) | A2 top-1 (PERSON) |
|---|---:|---:|
| deterministic | **1.000** | 0.013 |
| document-randomised | 0.209 | 0.000 |
| fully-randomised | undefined | 0.000 |

The axis practitioners agonise over — hash versus HMAC versus encryption — moves nothing. The axis
they treat as a deployment detail moves everything. That is the paper's claim, measured.

## 2. The wrinkle: perfect correlation, near-zero identification

Under a deterministic policy ρ = 1.000 — the frequency signal survives **completely** — yet A2
recovers only 1.3 % of PERSON entities at top-1.

Both numbers are right, and the gap is the interesting part. TAB's entity-frequency distribution is
almost flat: most people are named once or twice inside a single judgment. Rank alignment inside a
tie block that large is arbitrary, so a perfectly preserved signal fails to *identify* anyone.

So H1 needs stating more precisely than `PLAN.md` currently does:

> Under a deterministic policy the frequency signal is preserved **completely and identically across
> techniques**. Whether that signal converts into identification depends on the **corpus's frequency
> skew**, not on the cryptography.

This is a testable prediction rather than a hedge. **Enron should convert it and TAB should not** —
the same people recur across thousands of messages there, so the tie blocks break up. LOC already
hints at it here: places repeat more than people, and LOC top-1 (3.0–4.1 %) is two to three times
PERSON's.

## 3. The normaliser frontier, in the engine this time

Measured independently of the earlier standalone probe, and agreeing with it:

| normaliser | PERSON fragmentation | PERSON collisions |
|---|---:|---:|
| N0 raw | 0.118 | 0.000 |
| N2 (default) | 0.097 | 0.023 |
| N4 surname only | 0.014 | 0.090 |

Monotone, before any cryptography is involved. LOC barely moves (0.007 → 0.005) while its collisions
climb to 0.045 — PERSON fails by fragmenting, LOC by colliding, as predicted.

## 4. Reading the fully-randomised row correctly

Fragmentation there is 0.244, not 1.000, because it is measured per (document, chain) and **76 % of
PERSON chains have only one mention in their document** — a single-mention chain cannot fragment.
Collisions are 0.000 because every mention gets its own pseudonym. Both are the policy working as
specified, which is why the metric records the policy alongside the number.

## 5. What this does not yet show

Gold spans only, so no detector error is in these numbers; opaque tags only, so axis C is untouched;
one corpus, and the one with the least frequency skew of any in the meta corpus. The A1 dictionary
attack, the utility tasks and the detector ensembles are all still ahead.
