# Experiment plan — the full specification

**This is the authoritative specification for the experiments.** `PLAN.md` carries the thesis and the
argument; this file carries what is to be run, on what, measured how, and with which statistics.
Read it before designing, running or reporting anything.

Last updated 2026-09-08. Every decision is attributed and dated; nothing here is a default.

---

## 0. The one rule above the design

**No agent may change the scope or the number of experiments to save time, money, tokens or
wall-clock.** The budget is sufficient (AM, 2026-09-06). If a cell is genuinely impossible — corpus
unobtainable, licence refused, service down — **stop and report it**, naming the cell and the
obstacle. Do not substitute, do not silently narrow, do not run "a representative subset".

Sampling is *not* an exception to this: sampling rates are a **declared experimental parameter**
(§5), chosen for statistical and structural reasons and recorded with every result — never chosen to
make a run finish.

---

## 1. Factors

| axis | levels | notes |
|---|---|---|
| **key normaliser** | N0 raw · N1 casefold · **N2 + strip titles/punctuation (default)** · N3 + drop initials · N4 last token only | Chosen from data: on TAB these trace a monotone collision–fragmentation frontier *before any cryptography*. Run as a reported sub-axis |
| **A. policy** | deterministic · document-randomised · fully-randomised | ENISA's three. Implemented purely as a **scoping rule** on the entity key |
| **B. technique** | counter · RNG+mapping table (**both** with- and without-replacement) · SHA-256 hash · HMAC-SHA256 · **AES-SIV** | AES-SIV is the deterministic encryption level; FF1 is **cited, not run** — its format preservation is a surrogate-form property and would confound B with C |
| **C. surrogate form** | opaque tag · realistic · attribute-matched (gender/locale/frequency) | Realistic and attribute-matched draw from the gazetteers in §6 |
| **D. detector pool** | Presidio (rule) · GLiNER (zero-shot) · `obi/deid_roberta_i2b2` (public fine-tuned de-ID) · CodEAlltag `privacy_tagger` (domain, German e-mail) · ≥2 gateway LLMs · **gold spans (oracle)** | **No detector is trained by us.** One fine-tuned on a corpus's own split has seen the entities we then protect, inflating its recall and confounding everything downstream |
| **D′. combination rule** | *span-level:* union · vote(k) · intersection · weighted vote · cascade — *token-level:* per-token BIO voting (ROVER analogue) | Swept over **subsets** of the pool, with `require=` pinning so **LLMs-only** and **LLMs + ≥1 classical** are compared on equal footing |
| **E. corpus** | see §4 | Roles differ: full vs utility-only |
| **F. identifier provenance** | real · realistic-surrogate · placeholder-masked · PHI-inserted · fully-synthetic | A **control axis**, not a filter. Every 2026 detection benchmark is fully synthetic, so the T1→T5 contrast measures how much a benchmark's construction flatters its own privacy numbers |
| **sampling rate** | 0.01 · 0.05 · 0.10 · 0.25 · 1.0 where affordable | **Size is a reported parameter** (AM, 2026-09-08), not something to balance away |

**Why the factorial is affordable.** A, B and C compose rather than multiply: the policy is a scoping
rule, the technique a keyed map to an integer, the surrogate form a rendering of that integer. Three
small interfaces, not forty-five pipelines.

---

## 2. Measurements

### 2.1 Detection

P/R/F1 per entity type, **PERSON and LOCATION reported separately** because those carry the stability
requirement. Recall is the privacy metric, precision the utility metric.

### 2.2 Stability — three numbers, never one

Functions of the mapping plus co-reference gold. **Each must be read against the policy in force**,
because what is a defect under one policy is the definition of another:

| metric | definition | deterministic | document-randomised | fully-randomised |
|---|---|---|---|---|
| **collision** | distinct gold entities sharing a pseudonym within a scope | defect | defect | meaningless |
| **fragmentation** | one gold entity, several pseudonyms inside one scope | defect | defect | by design |
| **drift** | one gold entity, different pseudonyms across scopes | defect | **by design** | by design |

Reporting a single "fragmentation rate" across policies is a category error. The policy is recorded
alongside every number.

### 2.3 Utility — frozen models, task-based, no single scalar

**No training anywhere in the study** (AM, 2026-09-08). Not an economy: a TrustFMI audience prompts a
foundation model over a corpus rather than fine-tuning an encoder on one, so **degradation at fixed
weights** is the measurement that matches the deployment pattern.

**The unit of analysis is the document.** For each condition, keep the **vector of per-document
scores** — that is the primary artefact. Report **mean, SD, n** per condition per task. **No deltas,
no ratio, no composite scalar across tasks** (AM, 2026-09-08): a single number loses the information
and makes interpretation harder.

| task | corpus | per-document score |
|---|---|---|
| co-reference | TAB, OntoNotes | CoNLL F1 for that document |
| ECHR article classification (30 labels, multi-label) | TAB | per-case micro-F1 |
| medication IE | CARDIO:DE | span F1 per letter |
| section classification | CARDIO:DE | per-letter accuracy |
| folder classification | Enron | correct / incorrect |
| intent / speech act | Enron | correct / incorrect |
| formality | Enron, CodEAlltag | Spearman ρ per batch, or per-document error |
| NER agreement | all | span F1 between original and pseudonymised output |

**Always report the original-text score beside every condition.** If the frozen model is near chance
on the original, that task's numbers are uninterpretable and are excluded **with the reason stated**,
never silently averaged away.

**Statistics.** Conditions run on the same documents, so the scores are **paired**:

- **Wilcoxon signed-rank** for continuous scores — F1 is bounded and skewed, so a t-test's normality
  assumption is unsafe.
- **McNemar** for binary correctness (folder, section, intent).
- **Effect size beside every p-value** — median paired difference or rank-biserial. With n ≈ 1,268
  almost anything reaches p < 0.05, so significance without magnitude misleads.
- **Benjamini–Hochberg** across the comparison family. Dozens of conditions per task produce
  spurious significance by construction otherwise.

Two task-independent proxies — LM perplexity shift and embedding drift — are **sanity signals only**.
They always show that something changed and never show whether anything useful was lost.

**Out of scope, and said so:** whether a model *retrained* on pseudonymised text recovers. If it does,
the field's assumed utility cost is domain shift rather than information loss. It requires training
by definition and belongs in future work.

**Confound: memorisation.** A frozen LLM may recognise an ECHR case or an Enron thread and answer
from memory rather than from the text. Control with the same public-figure stratification A4 uses,
plus a no-context condition.

### 2.4 Leakage — five attacks

| | attack | applies to | scored as |
|---|---|---|---|
| **A1** | dictionary / brute force | **unkeyed techniques only** | inversion rate vs **name frequency** and **name length** |
| **A2** | frequency analysis | **all five techniques** | top-1 / top-5, Spearman ρ; rank alignment is the optimal 1-D assignment, so no Hungarian solver is needed |
| **A3** | structural linkage (fixed cosine over entity profiles) | all | Rank-1 / Rank-5 / mAP |
| **A4** | LLM re-identification | all | **ranked candidate list** — see below |
| **A5** | learned relational re-identification | all | Rank-1 / Rank-5 / mAP |

**A1 refuses to score keyed techniques and non-deterministic policies, and says why.** Without the
key there is nothing for the attacker to compute; reporting "HMAC resisted the dictionary attack"
would be a category error rather than a finding.

**A4 protocol (AM, 2026-09-08): ranked candidate list.** Present the pseudonymised document plus *N*
candidate identities including the true one; score **Rank-1 / Rank-5 / mAP**. Three reasons: it is
directly comparable with A3 and A5, the output is bounded, and the model never free-generates claims
about real people — which is what the Enron safeguards were written to prevent. Run with and without
auxiliary context, and **stratified by public-figure status**, which doubles as a memorisation test
against *Personal Information Parroting in Language Models* (arXiv 2602.20580).

**A5 is the only trained model in the study.** The asymmetry is deliberate and belongs in the paper:
**frozen defenders, trained attackers** — the defence is measured as deployed, the attack is made as
strong as we can make it, because a leakage number is only meaningful against the best available
adversary. The **A5 − A3 gap measures what learning buys the adversary**.

**Two disjointness requirements, both mandatory:**

1. **Entity-disjoint** train/test for A5 — an attacker scored on the entities it trained on measures
   memorisation, not attack strength.
2. **Document-disjoint** gallery/query for A3 and A5 — otherwise the attacker's knowledge and the
   released corpus are the same documents, differing only in replaced spans, and the attack matches
   a corpus against itself. **This was violated in the first run and inflated Rank-1 by 0.29.**

---

## 3. Statistics and reporting

- Per-document score vectors are the primary artefact; summaries are derived from them.
- Every result row carries: cell configuration, seed, **sampling scheme + rate**, corpus version,
  detector, prompt version, library versions, commit hash.
- Bootstrap CIs over documents where a CI is wanted.
- Results are parquet/JSONL artefacts on disk, never numbers in prose.

---

## 4. Corpora and their roles

A corpus enters the **full** design only if detection, stability **and** utility can be measured on
the same documents — which is the gap `PLAN.md` §2 claims nobody has closed.

| corpus | detection | stability | utility | role |
|---|---|---|---|---|
| **TAB / ECHR** (en, legal) | ✅ 8 types, DIRECT/QUASI | ✅ co-reference | ✅ 30-label articles | **full** |
| **OntoNotes** (en, zh, ar; 5 genres) | ✅ 18 NE types | ✅ co-reference | ✅ co-reference + NER | **full** |
| **Enron** (en, e-mail) | ⚠ structural, header-derived | ✅ cross-document identity | ✅ folder · intent · formality | **full** |
| **CARDIO:DE** (de, clinical) | ⚠ see §7 | ❌ | ✅ medication IE · section classes | utility **+ leakage** (AM, 2026-09-08) |
| **CodEAlltag** (de, e-mail) | ❌ none released | ❌ | ✅ formality · 7-way topic | utility only |
| **BRONCO150** (de, clinical) | ✅ ICD/OPS/ATC | ❌ sentence-scrambled | ✅ coding | utility only — **not yet received** |
| MEDDOCAN · MedDeID · REDACT · AI4Privacy | ✅ | ❌ | ❌ | **detection + leakage only**, as the T4/T5 control arm for axis F |
| E3C | ❌ no PII layer | ❌ | ❌ | out |

**Restriction is per measurement, not per corpus**: utility is scored only where a task exists;
detection and leakage still run on the synthetic members, which cost no annotation effort and are the
only thing keeping axis F's control arm alive.

**Access status.** TAB, Enron, OntoNotes, CodEAlltag, MEDDOCAN, MedDeID, REDACT, AI4Privacy, E3C,
PIIBench are on the cluster in `/cluster/shared_dataset/pseudonymization-corpora`. **CARDIO:DE is
restricted to AM alone** — `/cluster/maier/dua-restricted/cardiode`, mode 700; every additional
person needs their own countersigned agreement before touching corpus, derived files or cluster copy.
**BRONCO150** is unanswered; its clause 5 requires deletion by **2027-09-07** with Leser informed.
**n2c2 2014** is blocked — registration closed, "temporarily unavailable".

---

## 5. Sampling — there is no single fair sample

The sampling unit decides which structure survives, and the measurements depend on different
structures. Measured at rate 0.2 on a synthetic corpus:

| scheme | documents | entities kept | profile retained per entity |
|---|---:|---:|---:|
| `document` | 80 | 20 | 20 % |
| `stratified` | 80 | 20 | 20 % |
| **`subject`** | 80 | **6** | **67 %** |
| `time` | 80 | 20 | 20 % |

**No scheme keeps a profile whole except taking everything.** They rank; they do not solve.

| measurement | scheme | why |
|---|---|---|
| detection · utility · within-document stability · **A2** | **`stratified`** | every subject represented in proportion; frequency *ranks* survive thinning |
| **A3 · A5 · drift** | **`subject`** or **`time`** | profile completeness is the signal; document sampling starves it |

Scheme, rate and seed are stamped into `Corpus.name` and every document's metadata. **No result may
be quoted without its sampling provenance.**

**Size sweep.** Run identical cells at 0.01/0.05/0.10/0.25 and report which measurements are stable.
Prediction: A2 robust to rate, A3/A5 not.

---

## 6. Models and resources — none trained except A5

| role | model |
|---|---|
| rule-based detector | Presidio + spaCy backbone |
| zero-shot NER | `urchade/gliner_multi-v2.1`, `urchade/gliner_multi_pii-v1` |
| public fine-tuned de-ID | `obi/deid_roberta_i2b2`, `StanfordAIMI/stanford-deidentifier-base` |
| multilingual NER | `Davlan/xlm-roberta-large-ner-hrl` |
| domain-specific | CodEAlltag `privacy_tagger` (flair) |
| co-reference | `biu-nlp/lingmess-coref` |
| embeddings | `intfloat/multilingual-e5-large` |
| perplexity | `Qwen/Qwen2.5-0.5B` |
| LLM detectors, A4, zero-shot tasks | NHR@FAU gateway — `gpt-oss-120b`, `Qwen/Qwen3.6-35B-A3B-FP8`, `RedHatAI/gemma-4-31B-it-FP8-block`, `RedHatAI/Mistral-Small-3.2-24B-…`, `GaleneAI/Magistral-Small-…` |

**DeepSeek is excluded** — the gateway backend is down (AM, 2026-09-08).

**Gazetteers** (frequency- and attribute-bearing; an unweighted list can test neither H4 nor A1's
banding): US Census 2010 surnames (162,253, public domain) · UCI Gender-by-Name (147,269, CC-BY,
source of the gender attribute) · GeoNames `cities15000` (34,135, CC-BY).

---

## 7. Compute and job planning

- **Detection is the only slow step.** It writes through a **resumable cache** keyed by
  `(corpus, detector, doc_id)`; every ensemble afterwards is a post-hoc read, so the hybrid sweep —
  hundreds of subset × rule combinations — costs **zero** model calls once the pool is cached.
- **Everything must resume.** A killed job re-reads the cache and skips what is recorded; documents
  that errored are retried rather than frozen into the results.
- **Slurm limits:** assoc `MaxJobs` = 8; QOS `miti` = 4 concurrent, `turbo` = **10 concurrent, 100
  submitted**, 24 h wall clock. Use `--qos=turbo` and throttle arrays with `%8`.
- **The head node is not for jobs.** A 20,000-message load was OOM-killed there; the same load runs
  in 100 s inside an allocation.
- **`mkdir -p results/slurm` inside every job script.** Slurm redirects stdout *before* the script
  runs; a missing directory fails the job with no log at all.
- LLM work needs **no GPU** — it runs on the gateway, so those jobs are network-bound and share nodes.
- `/cluster` is at 95 %. Text corpora are small; do not write model checkpoints.

---

## 8. Deliverables

Released **code**, the **full factorial results**, and the **stability–leakage–utility frontier** per
language and domain — reported **one panel per task**, since a single utility scalar was rejected.

**Distribution is a build recipe, not a dataset.** Members span MIT, CC-BY, CC-BY-SA (copyleft), a
custom academic licence, three DUAs and the LDC licence; ShareAlike plus three DUAs cannot coexist in
one redistributable artefact. Ship converters, a manifest with checksums, and a local builder.

---

## 9. Results so far

| finding | status |
|---|---|
| **H1a** — the frequency signal survives **identically across all five techniques**; Spearman ρ = 1.000 on TAB and Enron, spread across techniques 0.000–0.008 in every run | measured |
| **H1b** — whether that signal *identifies* anyone depends on the **corpus's frequency skew**, not the function: A2 top-1 0.013 on TAB, **0.201 on Enron** | measured |
| **Normaliser frontier** — N0 → N4 trades fragmentation 11.8 % → 1.4 % against collisions 0.00 % → 9.02 %, before any cryptography | measured |
| **PERSON and LOC fail in opposite directions** — PERSON by fragmenting (11.8 % multi-form), LOC by colliding (0.7 %) | measured |
| **Cross-document drift is 8× within-document fragmentation** (0.147 vs 0.018 on Enron) | measured |
| **A1** — hashing inverts **0.758** of very common names and **0.000** of names absent from the dictionary: it protects exactly the names that do not identify people | measured |
| **A3/A5 policy collapse** — Rank-1 0.673 → 0.014 → 0.003 across deterministic / document / fully-randomised | measured (after fixing leakage) |
| **Learning buys most where the signal is weak** — A5/A3 ratio 1.04× deterministic, **5.1×** document-randomised, **21×** fully-randomised | measured |
| **Full randomisation is not a complete defence** — A5 still reaches Rank-1 0.064 against a 948-entity gallery, ~60× chance | measured |

**Unresolved:** the fair A3-vs-A5 comparison on identical galleries (A5's entity-disjoint split gives
it a smaller gallery, so the deterministic 1.04× sits inside that confound).

---

## 10. Open items

1. **BRONCO150** — no reply from Prof. Leser since 2026-09-07.
2. **n2c2 2014** — registration closed; ask DBMI when it reopens. Its loss removes clinical
   cross-document stability and the only cell where detection and utility shared documents.
3. **The fair A3/A5 comparison** — A3 restricted to A5's held-out entities and gallery.
4. **Paper scoping** — which panels fit eight pages.
