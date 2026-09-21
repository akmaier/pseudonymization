# Outline — TrustFMI @ ACCV 2026

**8 pages of content, references free.** Only full papers enter the proceedings, so this is a full
paper. Structure is the standard five sections (AM, 2026-09-21); targets sum to eight.

| section | pages |
|---|---:|
| 1. Introduction | 1.25 |
| 2. Material and methods | 2.25 |
| 3. Results | 3.0 |
| 4. Discussion | 1.0 |
| 5. Conclusion | 0.5 |

**The link to imaging is multimodal data** (AM, 2026-09-21). Safe sharing of a large clinical
database needs *both* the images and the text anonymised — a de-identified scan in a record whose
report still names the patient is not shared safely. Both are open problems, neither is solved by
the other, and AI is what makes either tractable at scale. This paper takes the text half and asks
what AI-based anonymisation actually delivers, across applications and across languages.

There is **no separate related-work section**; the literature is placed where it does work — the gap
in §1, the instrument choices in §2, and the comparisons in §3.

The **abstract is written last** and is not drafted here.

---

## 1. Introduction — 1.25 p

**No subsections** (AM, 2026-09-21) — short headlines eat space and break the argument into pieces
that should flow. One continuous passage, in this order:

Clinical data is multimodal by nature: a chest radiograph travels with its report, a cardiology study
with its discharge letter. Anonymising the pixels and anonymising the prose are different open
problems — defacing and burned-in-text removal on one side, finding the identifiers in running text
and replacing them on the other — and solving either alone does not permit sharing. A database is
releasable only when both halves are. AI is the reason either is now tractable at the scale a
database needs, and also why the guarantees are harder to state: the systems are learned, their
failures are distributional, and their errors are not uniform across languages or document types.
Packhäuser et al. re-identified patients from de-identified chest radiographs; this paper measures
the text analogue.

Then the gap: text anonymisation is evaluated in halves — detection benchmarks report recall, utility
papers report task loss, re-identification papers report attack success, almost never on the same
documents — so nobody can say what a given policy costs. And the numbers that are reported are
aggregates over a corpus, which is not the quantity a data-protection officer needs.

Then the contribution: one design, four corpora, four languages, three conditions, measured on the
same documents with the same statistics. Two claims:

1. The detector's **precision** dominates the pseudonymisation **policy** for utility.
2. The re-identification attacks move in **opposite directions** with detection recall: better
   detection protects against one and exposes to another.

*(A third claim about consensus rules deleting identifier classes was removed — it is an observation
from the results, not a hypothesis the study was designed to test. It stays in §3.1 as a finding.)*

---

## 2. Material and methods — 2.25 p

### 2.1 Corpora — 0.6 p
One table: documents, tokens, mentions/document, languages, gold provenance, role.
**CARDIO:DE** (400 German cardiology letters, DUA-bound) is the clinical anchor; **TAB** (1,268 ECHR
judgments), **OntoNotes** (5,994 documents, English/Chinese/Arabic) and **Enron** (58,636 messages)
test whether anything generalises. One caveat each: CARDIO:DE's identifiers are ours by construction
and 84.7 % of its gold tokens are dates the design never replaces; TAB names the applicant once
against 17 "the applicant"; OntoNotes is reported per language and never pooled; Enron is the only
corpus with genuine cross-document identity.

### 2.2 Conditions — 0.3 p
A unmodified · B deterministic HMAC-SHA256 with a realistic surrogate · C typed placeholder. B and C
differ in **exactly one axis level**, the surrogate form, which is what makes the pair a contrast
rather than two pipelines. Key normaliser N2, held fixed and revisited in §3.4.

### 2.3 Detectors and ensembles — 0.5 p
Fifteen detectors: rule-based, zero-shot NER, fine-tuned de-identification encoders, multilingual
NER, a German clinical tagger, and eight gateway LLMs. Combination rules (union, intersection,
vote *k*) and ensemble sizes 1–3. The token budget belongs here: output cost is **script-dependent**
and for a reasoning model largely **fixed**, not proportional to input — getting this wrong truncated
92 % of Chinese replies, and it is reported because it is a trap anyone repeating this will hit.

### 2.4 Operating points — 0.4 p
Fast against maximum, on **sensitivity and specificity**, the detector's two error rates against
their own denominators. Cost is the **slowest member**, since detectors run in parallel. Fast takes
the cheapest ensemble within 10 % of the maximum. A sensitivity floor is not optional: specificity is
maximised by detecting nothing.

### 2.5 Measurements — 0.45 p
Detection (token and entity level, information-weighted precision) and utility (frozen models, NER
agreement plus two clinical tasks, Wilcoxon or McNemar with Benjamini–Hochberg within a task family).
**Exposure is counted per document, per case and per entity**, not only per token.

### 2.6 The attacks — 0.5 p  *(expanded; no A-numbers)*
**Named, not numbered** (AM, 2026-09-21). "A1–A5" is our shorthand and it is opaque to a reader
meeting it once. Each gets a name, a plain sentence on what the adversary does, and — the part
usually left out — **what the adversary must already know**:

- **Frequency matching.** Counts how often each surrogate appears and lines that ranking up against
  a reference distribution of real names. *Needs*: a reference distribution that matches the
  population. It therefore transfers only where the name distribution is natural, which excludes
  CARDIO:DE, whose names we placed.
- **Context linkage.** Builds a profile of each person from the words around their mentions, then
  matches a profile from the released documents against profiles built from *other* documents.
  *Needs*: other documents about the same people, and an identity that spans documents at all —
  which is why it is computable on Enron and CARDIO:DE and not on TAB or OntoNotes.
- **LLM candidate ranking.** Shows a language model one marked mention in the released document plus
  a numbered list of ten candidate names, and asks it to rank them. *Needs*: the candidate
  population, and in one arm a snippet of other text about each candidate. This is a closed world —
  chance is one in ten — and the paper says so rather than letting 8.7 % read as "8.7 % of people
  re-identified".
- **Learned linkage.** The same task as context linkage, but with a model *trained* on part of the
  data instead of a fixed similarity. *Needs*: everything context linkage needs, plus training
  examples. The gap between the two measures what learning buys the adversary.
- A **dictionary lookup** attack is defined in the design and **not run**: there is no unkeyed
  condition for it to work against.

### 2.7 Stability, and the key normaliser — 0.25 p
Collision (two people receiving one surrogate), fragmentation (one person receiving several within a
document) and drift (one person receiving several across documents). These need a name for the rule
that decides when two mentions are "the same" — we call it the **key normaliser** rather than N0–N4.
The setting used throughout **casefolds, collapses whitespace, and removes titles and punctuation**,
so *Dr. Weber* and *weber* agree while *Weber* and *Kay Weber* do not. Stating the rule matters
because §3.4 shows it failing in both directions at once.

---

## 3. Results — 3.0 p

### 3.1 Detection — 0.9 p
The cost/quality front: four operating points × four corpora, both error rates and cost.
**The fast cell is usually not the worse cell** — CARDIO:DE's gives up 0.077 sensitivity, is *more*
specific than the maximum, and is 444× cheaper. Cost spans three orders of magnitude, quality less
than two-fold. Four corpora, four different winning ensembles: **nothing transfers**.
**Language is not a detail**: OntoNotes is English 0.983, Chinese 0.710, Arabic 0.549, and the
pooled 0.747 describes none of them — Arabic carries 45 % of the gold tokens from 7 % of documents.
**Consensus deletes classes**: at 8-of-15, DEMOGRAPHIC, MISC and QUANTITY fall to zero on all three
corpora, CODE loses 94–99 %, Arabic detection falls to 1.7 %.

### 3.2 Utility — 0.8 p
Precision, not policy: NER agreement under B is 0.611 with the permissive union and 0.973 with the
precise rule — same policy, same surrogates, same corpus — replicated on TAB and OntoNotes with
per-document statistics. Surrogates beat placeholders decisively for token-level tasks (C collapses
to 0.004) and are **worth nothing** for document-level ones (0.677 under B against 0.711 under C).
And the caveat that must travel with the headline: "preserved" utility under the precise rule on
Arabic and Chinese means 98.3 % and 93.3 % of identifiers were never replaced.

### 3.3 Leakage — 0.9 p
**Recall level matters, and the denominator must be held constant**: A2's raw top-1 *falls* as recall
rises because the candidate pool grows; measured against chance for its own pool it rises
monotonically, TAB 31×→75×, OntoNotes 48×→91×.
**The attacks disagree**: on Enron A3 falls 0.172→0.051 as recall rises while A2's lift holds. A3's
condition-A ceiling is 0.706, and A5 roughly doubles A3 throughout — what learning buys the
adversary. **A4 and why Rank-1 misleads**: TAB 0.999 → 0.087 Rank-1 but Rank-5 0.514, against a
1-in-10 chance of 0.500, so B reduces the LLM attacker to guessing.
**What actually survives** — the section the title rests on: per document, per case, per entity, the
three disagree and the token rate flatters. CARDIO:DE at maximum sensitivity leaves 26.8 % of letters
carrying a finding, 73.2 % clean, 7.0 % of patients with a name in the clear; the distribution of
surviving findings per document, not just the rate, because one residual mention and seven are
different problems for an attacker.

### 3.4 Stability — 0.4 p
The first collision, fragmentation and drift figures reported on text. **N2 fails in both directions
at once on Enron**: ORG collides at 17.3 % while drifting at 48.6 %; PERSON drifts at 37.7 % against
CARDIO:DE's 5.0 %, because the key is computed from the surface form and one person is written four
ways. CARDIO:DE's low figure is an artefact of its constructed recurrence, and we say so.

---

## 4. Discussion — 1.0 p

**Strengths first** (AM, 2026-09-21), then the weaknesses.

**What works, and works well.** A cheap ensemble is a genuinely good deployment: on German clinical
letters the fast operating point catches 89.5 % of identifiers we placed and costs three tenths of a
second a document — 191× less than the best ensemble of any kind, which buys 9.7 points of
sensitivity for that. Pseudonymisation with realistic surrogates
keeps clinical information extraction statistically indistinguishable from the original text under a
precise rule, which is the result a hospital needs before it will release anything. And the attacks
confirm the protection is real: the strongest language-model attacker drops from near-perfect on
unmodified text to chance inside a ten-candidate closed world.

**Where it is still open.** The **large ensemble is the most promising configuration we have and its
results are not final.** On CARDIO:DE and TAB it looks strong on both error rates at once, which no
small ensemble manages, and the runs are still going — the numbers in §3 for that cell are provisional
and will be replaced before submission. We say which they are rather than leaving the reader to guess.

**What a practitioner should do.** Take the fast operating point unless something specific demands
more. Check what a consensus rule deletes before trusting it. Report per language. Report per
patient, not per token. Read the top-five rate as well as the top-one. Measure specificity, because
that is where utility is lost.

**What this means for multimodal sharing.** The text half is not solved, and its failures are
*structured* — by language, by identifier class, by document length — in ways an aggregate hides. A
release pipeline reporting one recall number over a mixed-language database is reporting the average
of results that differ by 40 points.

**Limitations.** The token budget was mis-set for non-Latin script and the multilingual numbers were
re-run because of it. The detection table scores truncated model replies while the conditions drop
them. The surrogate inventory depends on which detector found the spans. CARDIO:DE's identifiers are
constructed, so its detection gold is complete in a way no natural corpus is. Context and learned
linkage are computable on two corpora only. Enron's sweep covers 263 promising configurations rather
than all 1,743, chosen on the other corpora's scores. No corpus annotates public-figure status, so
the candidate-ranking attack cannot be stratified by it.

---

## 5. Conclusion — 0.5 p

Safe sharing of clinical databases needs both modalities anonymised, and AI is what makes either
possible at scale. For text, this study prices the three costs against one another for the first time
on the same documents: detection precision governs utility far more than the pseudonymisation policy
does; better detection protects against one attack family while exposing to another; and aggregate
recall understates what a patient is exposed to. The operating points and every number behind them
are released with the paper.

---

## Notes on placement

- **Repository URL cannot appear in the submission** — ACCV's double-blind rules ban external links.
  It goes in at camera-ready, which is where the release sentence in §5 becomes concrete.
- **Cut to the repository**: the full 2,151-source sweep, leakage tables, per-detector cost profile,
  per-family q-values, CARDIO:DE's population model. The reviewer cannot see any of it, so anything
  load-bearing must be in the eight pages.
- **Figures**: one design figure in §2, one cost/quality front in §3.1, one exposure-distribution
  figure in §3.3. Tables: corpora (§2.1), operating points (§3.1), utility statistics (§3.2),
  leakage by recall level (§3.3).
