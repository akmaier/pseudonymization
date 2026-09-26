# Experiment plan — the operating point as the privacy control

**Second paper. Draft specification, AM's to approve.** Written 2026-09-26 on AM's instruction
("Write a new experiment plan. This is a new paper."). It does not supersede
[`experiment_plan.md`](experiment_plan.md), which remains the specification of the first paper;
where the two disagree, this file governs *this* paper only and says so explicitly.

Nothing here is decided until AM says so in words. Section 14 lists what is still open.

---

## 0. What this paper is

The first paper reports four named operating points and asks what pseudonymisation costs. This one
makes **the detector's operating point the independent variable** and asks what it *buys* — measured
as re-identification risk, downstream utility, and the difference between a surrogate release and a
typed-placeholder release built from the same spans.

The question is not ours. It is Carrell's, left open in 2019 and unanswered since:

> "attack efficiency may improve as leak rates decline"
> — Carrell et al. 2019, Discussion, limitation 1

They could not answer it because they had one detector at one operating point. We have a cached span
layer over 15 detectors, 2,151 combinations per corpus, already scored.

---

## 1. The contribution, stated so it survives review

**AM's framing — "prior HIPS work misses ensembles" — is false as written and a reviewer will find
it.** The literature check turned up three counter-examples, and one of them has Bradley Malin as a
co-author:

| | pool | rule | reported |
|---|---|---|---|
| Kim, Heider & Meystre 2018 | 12 systems | vote, k = 1…12 swept | k=1: P 80.13 / R 95.42 · k=12: P 99.46 / R 27.12 |
| Horng et al. 2022 | 3 tools | 1 / 2 / 3 votes | 57.5/95.7 · 93.7/82.8 · 99.2/58.5 |
| Murugadoss et al. 2021 (Patterns) | deep + rule-based | at-least-1 union | R 0.994 / P 0.967, 10,000 Mayo notes, **HIPS surrogates** |

So "we can place the operating point almost anywhere" is already in print. What is **not** in print,
and what this paper supplies:

1. **Nobody treats the combination rule as an independent variable.** Kim 2018 reports its k-sweep in
   two sentences of prose with no table and no figure; Kim 2020 plots F1 against threshold, collapsing
   the plane to a scalar; Horng tabulates three points. Nobody plots the front.
2. **Nobody reports the defender's position in the sensitivity/specificity plane.** Carrell 2019
   reports *no defender precision at all* — only the 8 % miss rate. Chambon 2023 never computes
   specificity; the word does not occur in the paper, and the non-PHI token count that would be its
   denominator is not given either. BRATsynthetic has no detector at all. Of the ensemble papers only
   Baumgartner et al. 2024 reports specificity (0.943 / 0.933).
3. **Nobody measures attack success as a function of that position.** Murugadoss states its own scope
   limit — "does not address the risk of re-identification". Carrell 2019 names it as limitation 1.
4. **Nobody pairs a surrogate release with a typed-placeholder release on identical spans and attacks
   both.** Berg et al. 2020 pair them for *utility*; Bao et al. 2026 pair them for *re-detectability*;
   the whole HIPS line assumes placeholder exposure is 100 % by definition and never runs it.

**The one-sentence claim.** *We make the detector operating point the independent variable and measure
re-identification risk and downstream utility jointly as surfaces over it, with surrogate and
typed-placeholder releases built from identical spans.*

**The closest prior work, and it must be cited as such.** Berg, Henriksson & Dalianis (LOUHI 2020)
build five PHI models along the precision/recall trade-off (F1…F40: 96.07/92.82 → 12.74/99.94) crossed
with four concealment strategies (Pseudo / Class / Mask / Remove) and measure downstream clinical NER
at all twenty cells, writing: *"To our knowledge, no studies have specifically focused on the
trade-off between precision and recall and its impact on downstream tasks."* They did the utility
half. We add the adversary, the ensemble-generated plane, and specificity.

---

## 2. What the required papers actually do

All five read in full on 2026-09-26; retrieval route recorded in `references/`.

| | detector | operating points | adversary | placeholder arm | utility |
|---|---|---|---|---|---|
| **Carrell 2013** (HIPS) DOI 10.1136/amiajnl-2012-001034 | MIST 1.2, single, **deliberately under-trained** | 1 per corpus | 2 human reviewers | no — assumed 100 % | no |
| **Carrell 2019** (parrot) DOI 10.1093/jamia/ocz114 | MIST 2.0.4, single, **same software both sides** | 1 (92 % sens., precision never reported) | re-tagging "parrot" | no — asserted 100 % | no |
| **Carrell 2020** (human) DOI 10.1093/jamia/ocaa095 | MIST 2.0, single | 1 per site, chosen at the median of 1,000 candidates | 4 hostile human readers | no | no |
| **Chambon 2023** DOI 10.1093/jamia/ocac219 | PubMedBERT **pipeline, not ensemble**; 5 models compared, never combined | 1 (argmax, no threshold) | **none** | no | no |
| **BRATsynthetic** arXiv 2210.16125 / Electronics **2025**, 14(19), 3945 | **none — no detector in the loop** | FNER 0.1/0.5/1/5 %, **injected onto gold**, 1,000 simulations | none | utility only | yes (journal version) |

Three things to carry into the writing.

**The parrot attack's mechanism is detector-error correlation, and the paper never states it.** From
Table 2: the attacker's tagger tagged **3,504 of 3,695 surrogates (94.8 %)** but only **99 of 310
leaks (31.9 %)**. The decision rule is one line — *untagged implies leaked* — and it yields 68 %
(211/310) recovery at 52 % (211/402) precision against an 8 % base rate. The signal is not that
surrogates look fake; it is that **the two detectors fail on the same spans**.

**Their own data already hints at our answer, and they do not comment on it.** Geographic location is
the single row in Table 2 where the attack fails to beat chance (56 % vs 49 %, χ² p = .107). It is
also the row where the defender's miss rate was 49 % instead of 8 %. Where the defender's sensitivity
collapsed, the parrot signal collapsed with it.

**BRATsynthetic's curve is injected; ours is observed.** Their false-negative rate is drawn onto gold
annotations at four chosen values and averaged over 1,000 random seeds. Every point on our plane is a
real ensemble of real detectors, with its real errors in their real places. That distinction is the
reason AM ruled out error injection (2026-09-26) and it is a contribution, not a constraint.

**Correction for `references/`:** Carrell 2013 is 2013 (JAMIA 20(2):342–348, e-pub 2012-07-06); the
DOI slug `amiajnl-2012-001034` encodes the submission year. `experiment_plan.md` lines 122 and 316 say
2012 and should say 2013. BRATsynthetic's journal version is **2025**, not 2026.

---

## 3. Hypotheses

Stated to be falsifiable. Each names the measurement that would refute it.

**H1 — Attack success is a function of the defender's operating point, and the function is not flat.**
Carrell's open question. The parrot attack works by error correlation, so its recovery rate should
depend on where the defender sits. *Refuted if* recovery is statistically indistinguishable across the
plane's extremes at the pre-registered primary cells.

**H2 — Over-detection is a privacy variable, not only a utility cost.** Two published mechanisms point
opposite ways: false positives add decoys to the attacker's haystack (HIPS), and false positives
create recoverable structure (Alexander & Beatty 2022: Philter false-positives on fractions like
"2/12" were date-shifted with the real dates, letting an attacker recover the per-patient offset and
de-shift every date including birthdate — 18,863 of 5,582,004 patients, >1 in 300, 99.9 % with a
recoverable birthdate). *Refuted if* attack success is independent of specificity at fixed
sensitivity.

**H3 — The surrogate-versus-placeholder gap is a property of the adversary, not of the release.**
B and C replace identical spans, so C is computable from B; the gap must close as the adversary
re-tags. *Refuted if* a measurable gap survives against the re-tagging adversary at any operating
point — which would be the positive result AM is looking for, and would need explaining.

**H4 — There is an interior optimum.** On CARDIO:DE, 337 of the existing 2,154 points are above 0.9 on
*both* rates. If utility and protection are jointly better there than at either extreme, "maximise
recall" is the wrong instruction. *Refuted if* the Pareto front runs to a corner.

`experiment_plan.md` §8.4's prediction ("A3 and A5 are strong on B and weak on C") belongs to the
first paper and does not bind this one (AM, 2026-09-26).

---

## 4. Corpora

| corpus | role | why |
|---|---|---|
| **CARDIO:DE** 🔒 | utility, exposure, the clinical claim, the discrimination surface | the only clinical corpus; DUA-bound, single-user |
| **Enron** | the attack curve | the only corpus with cross-document identity at scale — 3,697 gallery, 71.98 % unmodified-text linkage ceiling |

TAB and OntoNotes are out: 0 of 8,701 TAB and 0 of 13,230 OntoNotes entities appear in two documents,
so linkage returns Rank-1 = 0 even on unmodified text. They stay in the first paper.

CARDIO:DE cannot carry the linkage arm either — its unmodified-text ceiling is 2.73 %, 56.2 % of its
people appear in one document, and the intersection cell leaves 6 queries. **Enron carries linkage;
CARDIO:DE carries utility, exposure and the discrimination surface.** Neither corpus carries both.

All CARDIO:DE constraints from `CLAUDE.md` §3 remain in force unchanged.

---

## 5. The independent variable: the operating-point plane

**It is already computed.** `results/detection/{cardiode,enron,ontonotes,tab}.jsonl` hold **2,151 rows
each** — 1 gold + 15 singletons + 315 pair-rule + 1,820 triple-rule — derived offline from the 3.9 GB
cached span layer. No detector rerun, no GPU (AM, 2026-09-26).

**Specificity is not stored but is exactly recoverable** from what is:

```
TP          = token_recall × gold_tokens
predicted   = TP / precision
specificity = 1 − (predicted − TP) / (total_tokens − gold_tokens)
```

Verified against the published CARDIO:DE recommended-13 union point: derived 0.8685838 against
published 0.8685838. So the plane needs no re-scoring anywhere.

**What the CARDIO:DE plane spans** (2,154 rows in `results/leakage_sweep/cardiode_PERSON.jsonl`):

| | |
|---|---|
| sensitivity | 0.0000166 … **0.99884** |
| specificity | **0.868584** … 1.000000 |
| points with sensitivity > 0.95 | 196 |
| points with specificity > 0.999 | 846 |
| **points above 0.9 on both** | **337** |
| points already carrying A2, A3 and A5 | **2,140** |

That last row is the important one: **the CARDIO:DE attack surface under condition B is already
measured.** Enron has only 4 rows under the corrected gold (263 under the superseded gold, and
union-heavy at 260/2/1, so it never walks the axis).

**Point selection.** Reporting all 2,151 is neither necessary nor honest as a "sweep" — many are
near-duplicates. Proposal, for AM: report the **full plane as an estimated surface** (every point, CI
bands, no per-point tests), and pre-register a small **primary set** that carries the hypothesis
tests — gold, maximum sensitivity, maximum specificity, the recommended 13-detector union, and the
best interior point by the H4 criterion. See §9.

---

## 6. Conditions

Unchanged from the first paper, and the pairing is what makes this design work.

- **A** — unmodified. The ceiling; without it no rate on B or C has a scale.
- **B** — realistic surrogate, HMAC-keyed, consistent per entity. This is HIPS.
- **C** — typed placeholder `[PERSON]`.

`construct()` emits B and C from **one span set in one pass**, so the two releases differ in exactly
one thing. No published HIPS study has this control: Carrell 2013, 2019 and 2020 all assume placeholder
exposure is 100 % rather than measuring it.

**One confound must be closed before any run.** `build_BC.inventory_for` compiles its surrogate pools
from the documents the *current* operating point detected, so the same entity receives a different
surrogate at a different point. The code names this and leaves it to AM. **One inventory must be
pinned for the whole plane**, compiled once from the union over every detector, as `sweep_leakage.py`
already does internally.

---

## 7. The adversary

**One realistic adversary, not an axis** (AM, 2026-09-26).

It is the parrot, because it is the field's standard attacker, it is Kerckhoffs-justified, and it is
the one whose behaviour across the plane is the open question:

- **Knows:** the released corpus, and that it was pseudonymised by a published method. Holds the same
  public gazetteers the surrogate generator draws from (US Census surnames, UCI given names, the
  German lists) — these are public *by construction*, so withholding them would not be realistic.
- **Computes:** runs its own detector over the released text; treats every name-like span its detector
  fails to tag as a suspected survivor; then ranks identities for the spans it believes are real.
- **Outputs:** a suspected-survivor set (scored as a discrimination problem) and a ranked identity list
  per query (scored as Rank-1 / Rank-5 / mAP).

**Two consequences for the code.** First, the attacker must be anchored on *its own view* of the
released text, not on the defender's patch set. Every attack in the repo today iterates
`replacements()`, so a mention the detector **missed** never becomes a query — and a missed mention is
precisely what HIPS claims to hide. The anchor is `capitalised_spans()`, the condition-form-agnostic
regex A2 already uses; `_NAME_LIKE` requires a capital followed by lowercase, so it cannot match
`[PERSON]`. Under C it returns survivors; under B it returns survivors **plus** surrogates. That set
difference is the mechanism, expressed as something measurable.

Second, condition A stays as the ceiling, and the span-aware bound (an adversary told *which* spans
were replaced can compute C from B, so the gap is identically zero) is stated once as an analytic
remark. It is not an arm and not an axis.

---

## 8. Measurements

**8.1 Detection.** Sensitivity, specificity, precision, information-weighted precision, per type and
person-only, at every point. Already computed; specificity derived per §5.

**8.2 Exposure.** Per operating point, on the denominators the first paper settled: person–document
pairs, distinct people, documents, cases. One correction is required first —
`exposure_from_release.py` treats any gold token overlapped by *any* patch entry as caught, which is
true for C and false for B, because `PassThrough` renders DATETIME, QUANTITY and MISC verbatim. On
CARDIO:DE those unchanged types are 82 % of mentions. **Survival must be redefined as "not covered by
a textually effective replacement"** before exposure feeds anything here.

**8.3 The discrimination surface — the paper's central figure.** At each operating point, AUROC for
surrogate-versus-survivor over the attacker's own name-like spans, with the features ablated into two
groups that Carrell 2019 conflates and nobody has separated:

- **(a) error correlation** — did an attacker-side detector tag this span? (Carrell's entire signal)
- **(b) generator artefacts** — gazetteer membership; single-token-ness (`ListInventory` returns
  exactly one `Entry`, and the pools hold given names and surnames as separate entries, so a
  two-token mention is replaced by one token); `.title()` orthography (`Mcdonald` for `McDonald`);
  population-frequency mismatch (the draw is uniform and never frequency-matched); within- and
  cross-document repetition.

Holding the span set fixed and swapping only the generator separates (a) from (b). **AUROC as a
surface over the plane is the figure the paper is built on.**

**8.4 Attacks.** A2 frequency (B only — on C every identifier of a type is one string, so an empty
A2/C column is the correct outcome, not a missing run), A3 context linkage, A4 LLM candidate ranking,
A5 learned linkage. Two zero-cost instrumentation changes to A4, both forced by the literature:

- **Score three-way** — recovered / misled-to-surrogate / failed — so "the ranker believed the fake
  name" becomes a measured outcome class rather than an unexplained B-vs-C gap. Pilán et al. found
  Presidio's synthetic replacements scored *lower* risk than outright suppression and named the cause:
  such replacements "substitute it by new information that is rarely found in any background
  knowledge".
- **Run both a free-guess and a forced-choice regime.** Patsakis & Lykousas (Sci Rep 2023) got 0 %
  recovery on Faker surrogates, then recovered 544/1080 (50.4 %) against 784/1080 (72.6 %) on the
  placeholder version **by rewriting the prompt alone**. Prompt sensitivity of this size makes a
  single-regime A4 number uninterpretable.

**Memorisation control:** run Staab et al.'s (ICLR 2024, Appendix B) decontamination protocol verbatim
on Enron rather than inventing one — prefix/suffix greedy continuation scored on normalised
Levenshtein, BLEU-4, token equality, longest prefix match and longest common substring, with manual
inspection above 0.6 similarity.

**8.5 Utility.** CARDIO:DE: medication IE and section classification, both scored against external
gold through `OffsetMap` and therefore **fair between B and C**. Enron: **folder classification**
(AM, 2026-09-26 — "folder is ok. Keep the others too"), plus `ner_agreement` retained.

`ner_agreement` cannot carry a B-versus-C comparison and must never be used for one: its reference is
the frozen recogniser's output on the *original* text, so `[PERSON]` is never tagged and every
replaced mention is a forced disagreement — CARDIO:DE union is B 0.611 against C 0.004. It is valid
*between operating points within one condition*, and that is how it is reported.

---

## 9. Statistical protocol

`experiment_plan.md` fixes Wilcoxon / McNemar / BH with an effect size for utility and specifies
**nothing** for attack rates. AM's instruction was to find the answer in the literature (2026-09-26).
**The literature has no standard** — and that absence is documented by the field's own position
papers (Lison et al. 2021 §6.3 calls attack-based evaluation "an alternative which has so far received
little attention"; TAB reports its privacy metrics with no interval and no test anywhere). So we
specify one and justify each element by precedent.

1. **Unit of analysis: the protected entity.** One query per entity against a document-disjoint
   gallery. Never the span; spans within a document are not independent.
2. **Fixed query population.** Today the queries only exist where a span was replaced, so on Enron the
   count falls **19,059 / 9,355 / 9,408 / 494** across union / vote-2 / vote-3 / intersection, and on
   CARDIO:DE **138 / 83 / 63 / 6**. A rate on a moving denominator is not a curve. Define Q\* once by
   seeded sample from the entities present at the gold point and carry exactly that set through every
   cell, scoring an absent query as an explicit miss.
3. **Intervals always.** Bootstrap CI resampling **entities** (carrying all of an entity's documents
   together), 10,000 resamples. Precedent: Chambon 2023 (percentile, 1,000 samples); Bolle, Ratha &
   Pankanti's subsets bootstrap for the repeated-measures structure; El Emam et al. 2011 for interval
   estimation of a re-identification proportion.
4. **Chance baseline mandatory.** Print 1/|gallery| and the lift beside every Rank-1, and test against
   chance with an exact binomial. Precedent: Carrell 2019/2020's chance column. This makes "the attack
   did nothing" reportable rather than embarrassing.
5. **Condition comparisons paired on the entity.** McNemar's exact test for Rank-1/Rank-5; paired
   permutation (10,000) on per-query AP for mAP. **Not Wilcoxon for mAP** — Smucker, Allan & Carterette
   2007 recommend discontinuing it for mean differences. The deliberate divergence from the utility
   protocol is stated in the paper.
6. **Effect size beside every p.** Paired risk difference in percentage points with bootstrap CI;
   McNemar discordant-pair odds ratio as secondary. Report the condition-A ceiling in the same row.
7. **Primary versus sweep — this is what makes the multiplicity tractable.** A pre-registered
   **primary** set of cells (gold, max sensitivity, max specificity, recommended 13, best interior
   point — per corpus, per attack) carries hypothesis tests under Benjamini–Hochberg at q = 0.05 within
   one family per (corpus × attack). The **full plane is estimation**: curves with CI bands, no
   per-point p-values. Bonferroni is the only precedent in this literature (Carrell 2020, 40 tests) and
   is indefensible at 2,151 points × 3 conditions.
8. **Minimum detectable effect in every table caption.** For paired McNemar at the cell's n and
   observed discordance, the Δ detectable at 80 % power. Nobody in this literature does this; it
   pre-empts the obvious question about CARDIO:DE's smaller n.
9. **A regulator-legible column.** Rank-1 converted to probabilistic k = 1/risk, against the
   thresholds Pilán et al. use (citing El Emam 2013, EMA Policy 0070, Health Canada).

**Framing precedent.** Carlini et al. 2022 argue membership-inference attacks must be reported as a
full ROC with TPR at low FPR rather than average-case accuracy. Our claim is the same statement
transposed: **a protection claim evaluated at one operating point is not evaluated.**

---

## 10. What exists and what must be run

| | CARDIO:DE | Enron |
|---|---|---|
| detection plane (2,151 points) | ✅ computed | ✅ computed |
| specificity | ✅ derivable, no run | ✅ derivable, no run |
| A2 / A3 / A5 under B, per point | ✅ **2,140 points** | ❌ 4 points — needs re-scoring against the corrected gold |
| condition C per point | ❌ `sweep_leakage.py` line 426 is `conditions=("B",)` | ❌ same |
| A4 per point | ❌ never run inside the sweep | ❌ **no Enron A4 row of any kind exists** |
| discrimination surface (§8.3) | ❌ nothing in the repo has ever asked | ❌ |
| utility per point | ❌ | ❌ folder classification not wired |

**Engineering, in dependency order.** (1) Pin one inventory across the plane. (2) Survivor-anchored
attack path on `capitalised_spans()`. (3) Occurrence-level surrogate/survivor labeller — the existing
`_truth_tables` is surface-keyed and silently relabels a survivor whose name collides with some other
entity's surrogate, and collisions are 10.1 % on CARDIO:DE PERSON. (4) Condition C in the cheap
in-memory leakage path. (5) Fixed query population Q\*. (6) Explicit `--tag` on `run_leakage.py`, which
resolves its patch set by glob-and-take-first and has already attacked the wrong ensemble once.
(7) `reference=` pass-through for `ner_agreement` — it re-detects the original text per condition,
which is 351,816 Presidio calls per Enron point with half of them recomputation. (8) A4 concurrency —
it is a serial list comprehension, one gateway call per query. (9) Three-way A4 scoring and the
two prompt regimes. (10) `run_attack_statistics.py` pairing on query id.

---

## 11. Compute

No GPU and no detector reruns anywhere (AM, 2026-09-26). Three real costs:

- **Enron leakage re-scoring** — 257 s per span source measured. The full 2,151 is 6.4 days serial, so
  it is a Slurm array job or a selected spanning subset of the plane. **AM's call (§14).**
- **Enron utility** — as written it exceeds the 24 h wall clock at one point; the `reference=` fix
  roughly halves it.
- **A4** — free gateway, but serial and self-contending: `medication_ie` fell from ~533 to 45
  documents an hour while A4 ran against the same model. The A4 arm and the CARDIO:DE utility arm must
  not run concurrently against `gpt-oss-120b`.

Disk: 2,151 patch sets were estimated at 50 GB, against 2.0 T free at 95 % used (recorded 2026-09-06,
needs re-checking). Slurm and cluster conduct per `CLAUDE.md` §6, unchanged.

---

## 12. Threats to validity

| threat | control |
|---|---|
| attacks anchored on replaced spans cannot see a missed mention | survivor-anchored path (§7) — **blocking; nothing else is interpretable without it** |
| surrogate inventory moves with the operating point | one pinned inventory across the plane (§6) |
| query population moves with the operating point | fixed Q\* (§9.2) |
| A4's candidates come from gold, so a surrogate contradicts all ten | three-way scoring + both prompt regimes (§8.4) |
| memorisation of public corpora | Staab Appendix-B decontamination on Enron (§8.4) |
| `ner_agreement` is structurally hostile to C | never used between conditions (§8.5) |
| under B, an unchanged-type false positive can win the overlap and publish a name C destroys | counted as its own column per operating point; rate currently unknown |
| CARDIO:DE condition A is itself a seeded fill (resynthesis bias, cf. Yeniterzi et al. 2010) | seed stamped on every row; stated in limitations |
| Enron detector coverage | 12,505 of 58,636 documents are missing at least one of the 13; a vote(k) over a short pool is a different operator, not a worse one |

---

## 13. Reproducibility

Inherited from `experiment_plan.md` §9 unchanged: every result row carries cell configuration, seed,
sampling scheme and rate, corpus version, detector, prompt version, library versions and commit hash;
results are artefacts on disk, never numbers in prose; model availability is re-probed before every
run and recorded. Decoding for A4 is pinned and recorded (Staab et al. used temperature 0.1).

Added for this paper: every row carries the operating point's **(sensitivity, specificity)** and the
6-hex build tag, so detection, utility and attack rows join. `experiment_plan.md` §17 item 13 records
that no result-row schema exists; this paper cannot be analysed without one.

---

## 14. Open — AM's to decide

1. **Point selection.** Full 2,151 as a Slurm array on Enron, or a spanning subset? The plane is
   already computed either way; this is only about how many points get attacks and utility.
2. **The primary cell set** for hypothesis testing (§9.7). Proposed: gold, max sensitivity, max
   specificity, recommended 13, best interior point.
3. **The attacker's detector pool.** Kerckhoffs says give it ours (Carrell gave the attacker the same
   software). With ensembles we could instead vary defender/attacker *error correlation* by choosing
   overlapping or disjoint subsets — genuinely new, and arguably still one realistic adversary rather
   than an axis. Not built in without AM's word.
4. **H4's "best interior point" criterion** — what exactly is optimised.
5. **Authorship and venue** for this second paper.
6. **Reference hygiene**, proposed not done: add Murugadoss 2021, Alexander & Beatty 2022, Simancek &
   Vydiswaran 2024, Pilán et al. 2024/2025, Kim/Heider/Meystre 2018 and 2020, Horng 2022 and Carlini
   2022 to `references/`; fix Carrell 2013's year in `experiment_plan.md` lines 122 and 316.

**Still to be opened by a human.** Kim 2018 (PMC6371277), Kim 2020 (PMC8075417) and Horng 2022
(PMC9712864) are **abstract-level plus tool-extracted body text** — the PDFs could not be downloaded.
These are exactly the three papers a reviewer will use to test the novelty claim, so they must be read
in full before the related-work section is written.
