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
| Kim, Heider & Meystre 2020 | pruned + stacked ensembles | greedy exclusion, sequence stacking | generalisation across two corpora |
| Horng et al. 2022 | 3 tools | 1 / 2 / 3 votes | 57.5/95.7 · 93.7/82.8 · 99.2/58.5 |
| Murugadoss et al. 2021 (Patterns) | deep + rule-based | at-least-1 union | R 0.994 / P 0.967, 10,000 Mayo notes, **HIPS surrogates** |

So "we can place the operating point almost anywhere" is already in print. What is **not** in print,
and what this paper supplies:

1. **Nobody treats the combination rule as an independent variable.** Kim 2018 reports its k-sweep in
   *two sentences of prose*, with no table and no figure — verified against the full text
   (2026-09-27): *"We examined how performance of the voting ensemble method was affected by the
   voting threshold ranging from one to twelve… When the voting threshold is set at 1, the voting
   ensemble achieved 80.13% precision and 95.42% recall. When the threshold was set at 12, precision
   was 99.46% and recall 27.12%."* Two endpoints in running text. Kim 2020 plots F1 against
   threshold, collapsing the plane to a scalar; Horng tabulates three points. Nobody plots the front.

   Across all three full texts the word **"specificity" occurs zero times**, "operating point" zero,
   "trade-off" zero, "attack" zero, "re-identification" zero, "utility" zero and "downstream" zero;
   "surrogate" occurs once in Kim 2018, in a sentence defining de-identification. These are the three
   papers a reviewer would reach for, and none of them measures anything this paper measures.
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
| **Enron** | the attack curve | the only corpus with cross-document identity at scale — a 3,697-identity reference population, 71.98 % unmodified-text linkage ceiling |

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

**What the planes span**, both recomputed under the CODE rule of §8.6 and complete at 2,154 rows
per corpus with zero error rows (2026-09-28):

**Token recall**, not "sensitivity": it is over *all* gold tokens, which is the sweep's own
denominator. Paper 1's "sensitivity" is over the types the conditions replace and its "person
sensitivity" over PERSON alone — three different denominators, and they must not be mixed.

**The 0.5 token-recall floor is not optional** (paper 1, and for its reason): specificity is
`1 − FP/negatives`, so an ensemble that predicts almost nothing has almost no false positives and
scores near 1.0 while catching nothing. Both rows are given so the artefact is visible.

| | CARDIO:DE | Enron |
|---|---|---|
| token recall | 0.00002 … **0.99884** | 0.00140 … **0.99769** |
| specificity | **0.86926** … 1.00000 | **0.62484** … 0.99952 |
| points above the 0.5 recall floor | 1,028 of 2,154 | 889 of 2,154 |
| specificity > 0.999, **no floor** | 846 | 7 |
| specificity > 0.999, **floor 0.5** | **62** | **0** |
| above 0.9 on both | **337** | **1** |
| points carrying A2, A3 and A5 | 2,140 | 2,154 |

Read the floored rows. Unfloored, Enron shows seven points above 0.999 specificity and every one
is degenerate — token recall between 0.0014 and 0.008, i.e. detecting essentially nothing, and
consequently carrying *high* attack rates (A3 up to 0.2551) because almost nothing was replaced.
Under the floor there are none.

**So the corner is reachable on clinical reports and not on e-mail.** 62 CARDIO:DE configurations
clear 0.999 specificity while still catching half the identifiers; Enron has none, and exactly one
point clears 0.9 on both axes — `Qwen3.6-35B + privacy_tagger | intersection`, at recall 0.910 and
specificity 0.919, which is *not* safe: A3 0.0641 and A5 0.1162, some 237× and 430× chance.

**Cross-checked against paper 1** at the recommended 13-detector union, and the attack numbers
reproduce exactly: A3 0.0093, A5 0.0394, unmodified-text ceiling 0.7198, 19,059 queries. Specificity
comes out at 0.6248 against paper 1's 0.6235, the small rise being the false-positive CODE spans
the §8.6 rule removed.

**Point selection — settled (AM, 2026-09-27): all of them.** The Enron attack column is running as
an eight-task Slurm array, 269 span sources each, submitted 2026-09-27 as job 778960
(`experiments/slurm/sweep_enron_array.sbatch`). CPU only; every task is resumable, so a wall-clock
kill costs one span source. The QOS runs four at a time, so the 2,150 complete in roughly two rounds.

The **full plane is reported as an estimated surface** — every point, CI bands, no per-point tests —
and a small **primary set** carries the hypothesis tests: gold, maximum sensitivity, maximum
specificity, the recommended 13-detector union, and the best interior point by the H4 criterion.
See §9.7.

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

## 7. The adversary, and how it chooses

**One realistic adversary, not a knowledge axis** (AM, 2026-09-26). It is the parrot: it runs its
own detector over the released text and treats every name-like span its detector fails to tag as a
suspected survivor. That is Kerckhoffs-consistent, it is the field's standard attacker, and its
behaviour across the plane is the open question.

But the attacker must also **pick one of the 2,151 combinations** (AM, 2026-09-27), and that turns
out to be the design decision the paper turns on.

### 7.1 Why the choice matters

Write `d` for the defender's span source and `a` for the attacker's, over the candidate spans `V`
returned by a condition-form-agnostic tagger (`capitalised_spans()`; `_NAME_LIKE` needs a capital
followed by lowercase, so it cannot match `[PERSON]`). For a position `p`:

- a **surrogate** sits at `p` ⟺ `d` fired at `p`
- the attacker **flags** `p` ⟺ `a` did **not** fire at `p`
- a **survivor** sits at `p` ⟺ `gold(p)` and `d` did not fire at `p`

So the attack's two rates are

```
recall(d, a)    = P( ¬a | gold ∧ ¬d )      — survivors the attacker flags
precision(d, a) = P( gold ∧ ¬d | ¬a, p∈V ) — flags that are really survivors
```

and the attacker wants a detector that **misses what `d` missed** and **catches what `d` caught**.
Both are satisfied exactly by `a = d`: then `¬a` holds on every survivor (recall 1) and on no
surrogate (precision 1, up to the ordinary capitalised words in `V`).

**So copying the defender is the dominant strategy, and it is trivially perfect.** This is not a
finding, it is an identity — and it is why Carrell got 68 % rather than 100 %: his attacker could not
copy, it had to *train a fresh* MIST on its own annotations of the release, so the two error sets
were correlated but not equal (it tagged 94.8 % of surrogates against 31.9 % of leaks). An attacker
allowed to select `d` out of our cache measures nothing.

**The realistic constraint is therefore that the attacker does not know which of the 2,150 the
defender used.** With that, picking `a` becomes a real decision problem under uncertainty, and the
defender's choice of `d` becomes a real defence. Two reference points bound it, and neither is a
realistic attacker: **A-copy** (`a = d`) is the identity above, value 1, reported and not run; and
**A-oracle-response** (the best `a` knowing `d` but forbidden to copy it) bounds a well-informed
attacker. The realistic middle is §7.4.

### 7.2 The attacker re-tags, so the attack needs a second detection pass

**AM, 2026-09-27.** The parrot does not read the defender's patch set; it runs a detector of its own
over the *released* text. That is a **second detection pass**, over condition B and condition C, and
it is new compute — the 3.9 GB span cache covers condition A only.

Its cost is why the real attack is the **last** experiment, not the first: two corpora × two
conditions × a detector pass each, with LLMs in the pool, against a defender space of 2,150 points.
The cross product is not runnable and does not need to be.

### 7.3 Two phases: choose the point cheaply, then attack it properly

**Phase 1 — the safety analysis.** Determine the defender point we believe is safest, using the
attacker variants below **computed from the same span data** — the condition-A cache — as a stand-in
for the attacker's re-tagging (AM, 2026-09-27). This is set arithmetic, costs no model time, and
runs over the whole plane.

The stand-in is an approximation with published support: Bao et al. (arXiv 2608.03172, 2026) show by
equivalence testing across 11 detectors, 7 benchmarks and 7 languages that surrogate substitution is
**detection-neutral** — a detector finds a surrogate span about as readily as the original. So where
a detector fires on condition A is a good predictor of where it fires on condition B. The
approximation is stated as one, and phase 2 measures the error in it.

**Phase 2 — the real parrot attack.** Only at the point phase 1 selects: a genuine second detection
pass over the released text, on **CARDIO:DE and Enron, conditions B and C**, against the full
surrogate and placeholder pools. This is the headline attack and the paper's expensive run.

Nothing in phase 2 is scheduled until phase 1 has named the point.

### 7.4 The four attacker variants

The realistic attacker does not know which of the 2,150 the defender used, so it reaches for
something sensible. AM's four (2026-09-27), all drawn from the same pool the defender draws from,
because every detector in it is public:

| | attacker's span source | the attacker's reasoning |
|---|---|---|
| **(a)** | **union-13** — the recommended ensemble | misses the least, so almost every span it fails to tag is a real survivor |
| **(b)** | **union-3** — the max-sensitivity triple | the same instinct at a cost a real attacker would actually pay |
| **(c)** | **a balanced point** | neither error dominates |
| **(d)** | **max-specificity-3** | only fires on things that really are entities, so its misses are informative in the other direction |

(a) and (b) chase recall: a high-sensitivity attacker tags nearly all the surrogates, so its
*untagged* set is small and almost pure survivors — high precision, and recall limited by how much
of the defender's miss set it also misses. (d) is the opposite instinct: it fires only where it is
confident, so its untagged set is large and noisy, but everything it *does* tag is real signal.
Which instinct wins is exactly what phase 1 measures, and it is not obvious in advance.

**Variant (c) is Youden's *J* = sensitivity + specificity − 1** (AM, 2026-09-28), computable from
every row of the plane (§5).

**"Safe" is defined against these, and AM fixed it on 2026-09-28: a defender point is safe when
the *best* attack over the variants approaches the chance rate there.** Not merely lower than
elsewhere — approaching 1/N, N the reference population (§7.8). It is a property of the strongest attacker, so the worst of
the four governs, and it is measurable on the plane we already have.

**Measured on condition B with A3 and A5, 2026-09-28, and the two corpora do not behave alike:**

| | points at or below chance | best attack, floor over the whole plane | max Youden *J* point |
|---|---:|---|---|
| **CARDIO:DE** (chance 1/207) | **654** of 1,834 measurable | 0.0 | *J* = 0.9642, recall 0.9765, spec 0.9877, **attack 0** |
| **Enron** (chance 1/3697) | **0 of 2,154** | 0.03234 = **120× chance** | *J* = 0.8618, recall 0.9632, spec 0.8986, attack 0.105 = 390× |

Counted as **lift = rate ÷ that attack's own chance**, maximised over A2, A3 and A5, with a floor of
30 scored queries. Both qualifications matter and an earlier count of 777 had neither: chance is
**not** shared across attacks (§7.8), and CARDIO:DE has points with *zero* queries where the attack
could not run and `0 ≤ chance` scored as safety. Absence of measurement is not safety.

So on German medical reports 777 configurations reach chance and the *J*-optimal one is attack-free
at 0.9765/0.9877; on English e-mail **no configuration of fifteen detectors is safe by this
definition**, and the floor across the entire plane is 120× chance.

Read with §4's caveat, not around it: CARDIO:DE's unmodified-text linkage ceiling is 2.73 %, so a
point that reaches chance there may be describing the corpus rather than the protection. The
honest pair of statements is that e-mail admits no safe operating point and clinical reports admit
many *but cannot demonstrate it*, which is why Enron carries the attack curve.

Against these four sit the reference strategies of §7.1: **A-copy** (`a = d`, the analytic ceiling,
reported not run) and **A-oracle-response** (best `a` knowing `d`). The four variants are the
realistic middle, and one of them — whichever is worst for the defender — is what the safest point
must be chosen against.

### 7.8 What "chance" means, and why it is not one number

**Terminology (AM, 2026-09-28).** The paper says **reference population**: the set of identities the
attacker already holds and matches a released mention against. The code calls it the *gallery*,
after person re-identification, which carries no meaning to a clinical or legal reader — the term
stays in `build_gallery` and in the `a3_gallery` field, and is translated at the boundary.

A ranking attack's chance rate is one over the number of identities it ranks among, so it is a
property of **the attack**, not of the release:

| attack | chance | CARDIO:DE | Enron |
|---|---|---|---|
| A3, A5 | 1 / reference population | 4.83e-3 (1/207) | 2.70e-4 (1/3697) |
| A2, public prior | 1 / name-list size | 1.82e-5 | 6.16e-6 |
| A2, corpus-internal prior | derived from the release | **1,089 distinct values** | **1,898 distinct** |
| A4 | 1 / candidates shown | 0.1 | 0.1 |

A2's candidate space is a 54,830-name surname list, 265× larger than CARDIO:DE's reference
population, and its oracle-prior chance **moves with the operating point** because that prior is
read off the release. A4's is a ten-way choice, three orders the other way. Comparing raw rates
across attacks is therefore meaningless; everything is reported as **lift over that attack's own
chance**, which is scale-free and puts a ten-way ranking and a 3,697-person register on one axis.

**Why 1/N is the right chance when the attacker "does not know" the population.** It does know it:
A3 and A5 are 1-in-N identification tasks and the threat model *grants* the attacker that
population — without it there is no ranking to do. Concretely, `build_gallery` (the code's name for it) builds it from the
**unmodified condition-A text** of the document-disjoint half, so our attacker holds the original
documents for half the corpus. That is a strong assumption and it is what makes 1/N correct: the
rate is conditional on it, and should be read as "one in N, where N is the number of identities the
attacker already holds". State it in the limitations rather than letting 1/N look like a property
of the data.

### 7.5 The variable that drives it is error correlation, not the operating point

Two ensembles can sit at the *same* (sensitivity, specificity) and miss completely *different*
identifiers. The attack depends on the overlap of the miss sets, not on their size. So the plan
measures it directly — for every (`d`, `a`) pair evaluated, the Jaccard index and the φ coefficient
between the two miss sets on gold mentions — and tests whether it predicts attack success better
than the operating point does.

Carrell 2019 collapses this into "we gave the attacker the same software" and never measures it. It
is the hidden parameter of the whole HIPS literature, and with 2,150 interchangeable span sources on
both sides it is finally a variable rather than a constant.

### 7.6 Why phase 1 is affordable

The flagging step is **pure set arithmetic over the cached spans** — no condition-B build, no model,
no attack. Precompute one boolean row per span source over the candidate positions, pack the bits,
and each (`d`, `a`) pair is a handful of bitwise operations.

With four attacker variants rather than all 2,150, phase 1 is 4 × 2,150 = 8,600 pairs per corpus and
runs in minutes. The full 2,150 × 2,150 best-response matrix stays available for §7.1's
A-oracle-response bound and for H3b, at ~215 k pairs against a stratified defender sample.

### 7.7 What stays fixed

Condition A remains the ceiling. The span-aware bound — an adversary told *which* spans were
replaced can compute C from B, so the B-versus-C gap is identically zero — is stated once as an
analytic remark. Neither is an arm and neither is an axis.

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

## 8.6 The CODE sanity rule (AM, 2026-09-27)

**Decision: degenerate CODE spans are filtered before construction, as a stated defender step.**
AM approved this on 2026-09-27 and asked that it be discussed briefly in the paper.

**What prompted it.** Two Enron span sources aborted with
`SurrogateRejected: no surrogate passed code_is_consistent for type='CODE' in 512 draws; last
candidate 'www.' for 'www.'`. The engine was being asked to invent a realistic replacement for the
string `www.`, which identifies nobody.

**Where it comes from — domain mismatch, and it is measurable.** `privacy_tagger` is the CodEAlltag
German e-mail tagger. On German clinical text it behaves: 2,689 CODE spans on CARDIO:DE, of which
**7** are punctuation-only. On English Enron mail it fragments addresses and URLs and labels the
pieces:

| count | source label | surface |
|---:|---|---|
| 2,423 | `EMAIL` | `.` |
| 844 | `EMAIL` | `@` |
| 354 | `UFID` | `-` |
| 133 | `URL` | `@` |
| 27 | `URL` | `http` |

It is not only punctuation. Of the 2,278,898 CODE spans presidio and `privacy_tagger` produce on
Enron, **35,633 are four characters or shorter**, led by Enron's own mail routing — `HOU` 4,936,
`ECT` 2,402, `HOU/` 2,144, `@ECT` 2,053 (Houston; Enron Capital & Trade). On CARDIO:DE the same
figure is 2,526 of 29,309 (8.6 %).

**The rule.** A CODE span is kept only if it contains at least one alphanumeric character **and** is
at least five characters long.

An earlier phrasing of this rule — "at least one alphanumeric" alone — was wrong and is recorded
here so it is not repeated: `www.` contains three, as do `HOU`, `ECT` and `m0`. Alphanumeric alone
removes roughly 4,200 of the 35,633.

Five is a judgement and is justified rather than assumed: no identifier class in the taxonomy that
routes to CODE — e-mail, phone, IBAN, card, ID, URL, licence — identifies anyone at four characters
or fewer, and a fragment that short cannot be given a consistent surrogate, which is what the engine
discovered the hard way. **The plane's sensitivity to the threshold (4, 5, 6) is reported at the
recommended ensemble**, so the choice is visible rather than buried.

**Why it is a finding and not only a fix.** It bears directly on §3's H2. A false positive is a
decoy only if it could plausibly be a real identifier; `.` and `HOU` camouflage nothing and only
damage the text. So over-detection is not one thing, and the paper distinguishes **name-like
decoys** from **noise decoys**. No prior work in §2 separates them, because none of them varies the
operating point at all.

**Consequence, and it is not small.** CODE spans are replaced in condition B, so the released text
changes, so the attacks change. Every row computed without the rule is therefore incomparable with
rows computed under it. That covers the Enron sweep in flight and the 2,154 CARDIO:DE rows of §5.
Two things follow, and the second is AM's to confirm:

- **Paper 1 is not retrofitted.** Its numbers are internally consistent under the unfiltered
  behaviour and it is at submission. The rule belongs to this paper.
- **Paper 2's planes are recomputed under the rule.** The before/after is reported at the
  recommended ensemble only — one extra point, which is the "quick discussion" AM asked for, rather
  than a second full arm.

**Not yet implemented.** The predicate above is a proposal pending AM's word on the threshold; the
rule was got wrong once already and the plane is expensive to recompute.

## 9. Statistical protocol

`experiment_plan.md` fixes Wilcoxon / McNemar / BH with an effect size for utility and specifies
**nothing** for attack rates. AM's instruction was to find the answer in the literature (2026-09-26).
**The literature has no standard** — and that absence is documented by the field's own position
papers (Lison et al. 2021 §6.3 calls attack-based evaluation "an alternative which has so far received
little attention"; TAB reports its privacy metrics with no interval and no test anywhere). So we
specify one and justify each element by precedent.

1. **Unit of analysis: the protected entity.** One query per entity against a document-disjoint
   reference population. Never the span; spans within a document are not independent.
2. **Fixed query population.** Today the queries only exist where a span was replaced, so on Enron the
   count falls **19,059 / 9,355 / 9,408 / 494** across union / vote-2 / vote-3 / intersection, and on
   CARDIO:DE **138 / 83 / 63 / 6**. A rate on a moving denominator is not a curve. Define Q\* once by
   seeded sample from the entities present at the gold point and carry exactly that set through every
   cell, scoring an absent query as an explicit miss.
3. **Intervals always.** Bootstrap CI resampling **entities** (carrying all of an entity's documents
   together), 10,000 resamples. Precedent: Chambon 2023 (percentile, 1,000 samples); Bolle, Ratha &
   Pankanti's subsets bootstrap for the repeated-measures structure; El Emam et al. 2011 for interval
   estimation of a re-identification proportion.
4. **Chance baseline mandatory.** Print that attack's own chance (§7.8) and the lift beside every
   Rank-1, and test against
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
| discrimination surface (§8.3), phase 1 | ❌ nothing in the repo has ever asked | ❌ |
| second detection pass over B and C (§7.2), phase 2 | ❌ the cache is condition A only | ❌ the cache is condition A only |
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

- **Enron leakage re-scoring** — running since 2026-09-27 as jobs 778960 (`miti`, tasks 0-3) and
  778965 (`turbo`, tasks 4-7), 269 span sources each, all eight shards resumable. Measured
  throughput on the first two hours is 11 rows per 10 minutes across six tasks, i.e. about 200 s per
  span source, so a shard is ~24.5 h against the 24 h soft limit and will need one resubmit; the
  eight shards complete in roughly 49 h at six concurrent.

  **The resident set is the throughput lever, and it is avoidable.** A task holds four corpus-sized
  object graphs at once: `documents`; `union_detected`, the union over all 15 detectors, built for
  the inventory at `sweep_leakage.py:170` and **never freed**, so it stays resident for the whole
  shard — the sibling script `leak_ablation.py:95` does `del union_all` at exactly this point; the
  tokenised scoring index from `prepare()`; and then, per span source, a third copy from
  `detected_documents()` and a fourth from `to_pseudonymised_corpus()`, both of which materialise
  `list[Document]`. Every one of those stages is a per-document map over sequential data. Only the
  reference population (3,697 profiles) and the query set genuinely need to be global, and they
  are small.
  The `del` is one line and free; streaming the per-source stages is what would let two tasks share
  a node and halve the wall clock. Neither is a mid-run change — the plan requires a commit hash on
  every result row, and editing the script under a resumable job would mean rows from one shard were
  computed by two versions of it.

  **Concurrency is capped by node memory, not by the queue.** The `turbo` QOS is the fast lane —
  priority 10000 against `miti`'s 0, 10 concurrent jobs against 4, 100 submittable against 8 — but
  a task holds about **88 GB resident** (lme53 was down to 4.5 GB free with one task on it), the
  cluster has roughly six nodes that can hold that, and `SelectTypeParameters=NONE` means Slurm does
  **not** treat memory as a consumable resource and will double-book a node if asked. Six concurrent
  is therefore the ceiling until the resident set is reduced, and asking for more would buy an OOM
  rather than throughput. Six run; two wait behind `%2` on the turbo array.
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
| Enron detector coverage | **resolved** — all 15 detectors reached 100 % cache coverage of the 58,636 documents (checked 2026-09-27), so `--min-coverage` skips nothing and every one of the 2,150 sources is the operator its label claims. The earlier "12,505 documents missing a detector" figure was stale. |

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

Settled since the first draft, kept here so the record shows when:

- ~~Point selection~~ — **all 2,150** (AM, 2026-09-27); running as jobs 778960 and 778965.
- ~~The attacker's detector pool~~ — the whole pool is attacker-available because every detector in
  it is public; the attacker does not know which the defender used; the four realistic variants are
  §7.4 (AM, 2026-09-27).
- ~~Whether the attack needs its own detection pass~~ — **yes**, and it is therefore the last
  experiment, after phase 1 has named the point (AM, 2026-09-27).
- ~~Reading the three near-miss ensemble papers~~ — Kim 2018, Kim 2020 and Horng 2022 obtained and
  read in full on 2026-09-27. Result in §1.
- ~~The CODE sanity threshold~~ — **at least one alphanumeric and at least five characters**
  (AM, 2026-09-27, §8.6). Implemented in `construction.py`, shared with `score_detection.py`, and
  both planes recomputed: 2,154 rows per corpus, zero error rows, no `SurrogateRejected` left.
- ~~Fixing the sweep's memory~~ — done 2026-09-27. Measured peak 11.92 GiB against an 84 G request
  that was itself the concurrency limit; now 24 G, BLAS threads pinned to the allocation, two tasks
  a node across five or six nodes. Throughput 1.18 -> 2.26 rows/min.

Still open:

1. **The definition of the "balanced" attacker variant (c)** (§7.4). Proposed: Youden's
   *J* = sensitivity + specificity − 1. Alternatives: nearest to (1, 1); max min(sens, spec).
2. **Which variant the safest point is chosen against** (§7.3 phase 1) — the worst of the four, or
   the most likely one. Choosing against the worst is the defensible reading and is what phase 1 is
   set up to report.
3. **The defender set for the full best-response matrix** (§7.6). Proposed: the primary cells plus a
   stratified sample of about 100 spanning the plane. The four named variants run against the whole
   plane regardless; this is only about the A-oracle-response bound and H3b.
4. **The primary cell set** for hypothesis testing (§9.7). Proposed: gold, max sensitivity, max
   specificity, recommended 13, best interior point.
5. **H4's "best interior point" criterion** — what exactly is optimised. "The `d` that minimises the
   worst variant's success subject to a utility floor" is the natural candidate; the floor is AM's.
6. **Venue** for this second paper. Authors settled 2026-09-28: paper 1's list plus **Soroosh
   Tayebi Arasteh** (RWTH Aachen; exact affiliation line to confirm). He is already cited in paper 1
   as `arasteh2024speaker`.
7. **Reference hygiene** — the additions are *prepared, not applied*: what a paper cites is decided
   by what it ends up covering, so these are held until writing (AM, 2026-09-28). Candidates: add Murugadoss 2021, Alexander & Beatty 2022, Simancek &
   Vydiswaran 2024, Pilán et al. 2024/2025, Kim/Heider/Meystre 2018 and 2020, Horng 2022, Bao et al.
   2026 and Carlini 2022 to `references/`; fix Carrell 2013's year in `experiment_plan.md` lines 122
   and 316; BRATsynthetic's journal version is Electronics **2025** 14(19) 3945, not 2026.

**Publisher PDFs are never committed** (AM, 2026-09-27). `.gitignore` enforces it; `references/`
carries the citation, the DOI and the honest read status.
