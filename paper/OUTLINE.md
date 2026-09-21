# Outline — TrustFMI @ ACCV 2026

Six to eight pages is tight for a study with four corpora and three measurement families, so this
outline is written against a **budget**: what earns its space, and what gets cut to the repository.
Section lengths are targets, and they sum to eight.

The **abstract is written last** (AM, 2026-09-21) and is not drafted here.

---

## 1. Introduction — 0.75 p

**The claim.** Text pseudonymisation is evaluated in halves — detection benchmarks measure recall,
utility papers measure task loss, re-identification papers measure attacks — and almost never on the
same documents. The consequence is that the field cannot say what a given pseudonymisation *policy*
costs, because the three costs are never priced against one another.

**What this paper does.** Holds the corpus, the conditions and the statistics fixed, varies the
pseudonymisation function and policy, and reports detection, utility and leakage from one design over
four corpora in four languages.

**The three findings worth the title**, stated here and delivered later:

1. The detector's *precision* dominates the pseudonymisation *policy* for utility — replicated on
   three corpora.
2. The two attack families move in **opposite directions** with detection recall: structural linkage
   falls, frequency attack rises. "Detect more" is protective against one and exposing against the
   other.
3. A consensus rule that looks like a sensible default silently deletes whole identifier classes and
   whole languages.

---

## 2. Related work — 0.75 p

Compressed hard; `references/` carries the full survey.

- **Detection benchmarks** (TAB, REDACT, PIIBench, the 2026 OpenAI privacy-filter evaluation) — own
  the detection ground and are *not* what this paper competes on. Say so explicitly.
- **Surrogate generation** — i2b2/Stubbs & Uzuner, MIST/Carrell, BRATsynthetic, Eder et al. Where
  "hiding in plain sight" comes from and what it predicts.
- **Utility under de-identification** — Tau-Eval's near-lossless placeholder result is the field's
  real comparison point and our condition C, not a straw man.
- **Re-identification** — Fellegi–Sunter record linkage; Packhäuser et al. as the image analogue of
  A5; Oh et al. (SPIA) on moving the unit of evaluation.
- **The gap.** §4.1: no published work reports collision, fragmentation or drift on text. Ours are
  the first.

---

## 3. Design — 1 p

The section that makes the rest legible. One figure, one table.

### 3.1 Three conditions
A (unmodified), B (deterministic HMAC-SHA256, realistic surrogate), C (typed placeholder). B and C
differ in **exactly one axis level** — the surrogate form — which is what makes the pair a clean
contrast rather than two differently configured pipelines.

### 3.2 Axes
Detector (15 levels + gold), combination rule (union / intersection / vote *k*), ensemble size
(1–3), corpus (4). What is held fixed: key normaliser N2, HMAC, the frozen task models.

### 3.3 Operating points
Fast against maximum, on specificity and sensitivity; cost is the **slowest member** because
detectors run in parallel; the fast cells take the cheapest ensemble within 10 % of the maximum.
Why a sensitivity floor is not optional — specificity is maximised by detecting nothing.

### 3.4 What is measured
Detection (§8.1, entity- and token-level, information-weighted precision), utility (§8.3, frozen
models, Wilcoxon/McNemar with BH within a task family), leakage (A2 frequency, A3 structural, A4 LLM
ranked-candidate, A5 learned), stability (collision, fragmentation, drift).

---

## 4. Corpora — 0.75 p

One table: documents, tokens, mentions/document, languages, gold provenance, role.

Per corpus, the one fact that changes how its results read:

- **CARDIO:DE** — identifiers are *ours*, placed by the condition-A fill, so detection gold is
  complete by construction and A2's numbers do not transfer. 84.7 % of gold tokens are dates the
  design never replaces.
- **TAB** — real names, richest annotation, DIRECT/QUASI classes, but the applicant is named once
  while "the applicant" appears 17 times.
- **OntoNotes** — three languages; **report per language, never pooled** (§6.2).
- **Enron** — real names in a natural frequency distribution, genuine cross-document identity via
  the mailbox owner, and the only corpus where A3 and A5 are computable at all.

---

## 5. Methods — 0.5 p

Only what a reader needs to reproduce or to trust:

- the surrogate inventories and where each pool comes from (§14 gazetteers; attested pools compiled
  from the corpus where no gazetteer exists, and why that is the honest fallback);
- the detector pool and the token budget (script-aware characters-per-token — see §10, it is a
  limitation *and* a finding);
- reproducibility: config + seed, model ids, commit hash with every result.

---

## 6. Detection results — 1.25 p

### 6.1 The cost/quality front
The headline table: four operating points × four corpora, with **both** error rates and cost.
The finding: **the fast cell is usually not the worse cell** — CARDIO:DE's fast point gives up 0.077
sensitivity, is *more* specific than the maximum, and is 444× cheaper. Cost spans three orders of
magnitude while quality spans less than two-fold.

### 6.2 Ensembles do not transfer, and neither does a corpus average
Four corpora, four different winning ensembles. And OntoNotes must be split: English 0.983, Chinese
0.710, Arabic 0.549 — a single 0.747 describes none of them, and Arabic carries 45 % of the gold
tokens from 7 % of the documents.

### 6.3 What consensus deletes
`vote` over fifteen detectors is eight of them, and at that threshold DEMOGRAPHIC, MISC and QUANTITY
fall to **zero** on all three corpora scored, CODE loses 94–99 %, and Arabic detection falls to 1.7 %.
Eleven of fifteen detectors emit DEMOGRAPHIC; eight never agree on one, because the harmonised label
collapses categories that are not the same thing.

---

## 7. Utility results — 1 p

### 7.1 Precision, not policy
NER agreement under B: 0.611 with the permissive union, 0.973 with the precise rule — same policy,
same surrogates, same corpus. Median losses across the three corpora with statistics.

### 7.2 Surrogates versus placeholders
B beats C decisively for token-level tasks (C collapses to 0.004 on CARDIO:DE) and is **worth nothing**
for document-level ones (section classification 0.677 under B, 0.711 under C).

### 7.3 The caveat that must travel with it
Utility "preserved" under the precise rule on Arabic and Chinese means 98.3 % and 93.3 % of
identifiers were never replaced. The work was not done. This is the paper's sharpest methodological
warning and it belongs in the results, not the limitations.

---

## 8. Leakage results — 1.25 p

### 8.1 Leakage at every recall level (H1)
The denominator correction first: A2's raw top-1 *falls* with recall because the candidate pool grows.
Measured against chance for its own pool it rises monotonically — TAB 31×→75×, OntoNotes 48×→91×.

### 8.2 The two attacks disagree
On Enron, A3 falls from 0.172 to 0.051 as recall rises while A2's lift holds or rises. Better
detection protects against structural linkage and exposes to frequency analysis. A3 ceiling on
condition A is 0.706; A5 roughly doubles A3 throughout, which is what learning buys the adversary.

### 8.3 A4, and why Rank-1 alone misleads
TAB: condition A 0.999 → condition B 0.087 Rank-1, but **Rank-5 0.514**. Chance in a 1-in-10 closed
world is 0.100/0.500 — so B reduces the LLM attacker to guessing. State the threat model plainly:
the attacker holds the candidate population, and in one arm auxiliary text about them.

### 8.4 What actually survives
Per document, per case, per entity — the three denominators disagree and the token rate flatters.
CARDIO:DE at maximum sensitivity: 26.8 % of letters carry a finding, 73.2 % are clean, 7.0 % of
patients keep a name in the clear.

---

## 9. Discussion — 0.5 p

What a practitioner should take: pick the fast operating point; do not trust a consensus rule without
checking what it deletes; report per language; read Rank-5 as well as Rank-1; and measure specificity,
not just recall, because that is where utility is lost.

---

## 10. Limitations — 0.5 p

Stated, not hedged: the token budget was mis-set for non-Latin script and the multilingual numbers
were re-run because of it; the detection table scores truncated replies while the conditions drop
them; the surrogate inventory depends on which detector found the spans; CARDIO:DE's identifiers are
constructed; A3/A5 are computable on two corpora only; Enron's sweep covers 263 promising sources
rather than all 1,743, chosen on the other corpora's scores.

---

## What is cut to the repository

Stability (collision/fragmentation/drift) is a genuine first — §4.1 says nobody reports it on text —
but it needs a page to do properly and there is not one. **Proposal: one paragraph in §6 with the
Enron result** (PERSON drift 0.377, ORG collision 0.173 *and* drift 0.486 — N2 failing in both
directions at once), and the full table in the repository. If we go to the 8-page limit rather than 6,
this is the first thing that earns the extra space back.
