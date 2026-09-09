# Experiment plan — the full specification

**This is the authoritative specification for the experiments.** `experiment_plan.md` carries the thesis and the
argument; this file carries what is to be run, on what, measured how, and with which statistics.
Read it before designing, running or reporting anything.

Last updated 2026-09-08. Every decision is attributed and dated; nothing here is a default.

---

## A. Standards — and one was revised this year

| | |
|---|---|
| **DIN EN ISO 25237:2026-06** | *Medizinische Informatik — Pseudonymisierung* (ISO/DIS 25237). `10.31030/3696721` — a **2026 revision** of the health pseudonymisation standard |
| DIN EN ISO 25237:2017-05 | the superseded edition, `10.31030/2555889`; BSI equivalent *Health informatics. Pseudonymization* `10.3403/30285709` |
| **ENISA 2021** | *Data Pseudonymisation: Advanced Techniques and Use Cases* — downloaded and read; the practical European reference |
| ENISA 2019 | *Pseudonymisation techniques and best practices* |
| ISO/IEC 20889 | privacy-enhancing de-identification terminology and technique classification — **not directly verified**, iso.org returns 403 to scripted access |
| GDPR Art. 4(5) | the legal definition pseudonymisation has to satisfy |

Publishing against a standard revised in **June 2026** is a good position for a workshop paper.

## B. ENISA's technique taxonomy — the source of axes A and B

Quoted/paraphrased from the 2021 report, §"pseudonymisation techniques":

| technique | ENISA's verdict | notes for us |
|---|---|---|
| **Counter** | simplest | the ordinal character "can still provide information on the order of the data" |
| **RNG + mapping table** | better protection than counter | AM's "random key table". *"Collisions, however, may be an issue, as well as scalability."* Table compromise reveals everything |
| **Cryptographic hash** | *"generally considered **weak** as a pseudonymisation technique, as it is prone to **brute force and dictionary attacks**"* | **exactly the short-name concern** — confirmed verbatim |
| **MAC / HMAC** | *"generally considered a **robust** pseudonymisation technique from a data protection point of view"* | keyed, so deterministic *and* attack-resistant → gives stability without storing a table. Recovery is a problem if originals are not kept |
| **Symmetric encryption** | *"robust"* | block cipher under a secret key |

**The key design tension for us.** Stability and resistance pull in different directions:

- A plain hash is stable and needs no table — and is broken by a dictionary of ~50k common surnames.
- **HMAC is stable, needs no table, and resists the dictionary attack** — but the whole corpus inverts the moment the key leaks.
- An **RNG mapping table** has no key to leak, but the table *is* the crown jewels, and ENISA flags collisions — a collision is precisely "person 1 confused with person 2".

None of that trade-off has been measured empirically on real text. That is the opening.

## C. What already exists — the pieces, never assembled

**Detection is solved and crowded.** REDACT (arXiv 2606.19881, 2026) — 25 languages, 9 scripts, 51
entity types, domain as a controlled axis, five detectors across rule/NER/LLM families. PIIBench
(2604.15776, 2026) — ten corpora unified, 48 types, eight systems. MultiGraSCCo (LREC 2026) —
multilingual *clinical*, ten languages. Plus MEDDOCAN (es), i2b2/n2c2 (en), CARDIO:DE and BRONCO
(de). **Do not build another detection benchmark.**

**Surrogate generation is thin.**
- *BRATsynthetic: Text De-identification using a Markov Chain Replacement Strategy for Surrogate
  Personal Identifiers*, arXiv 2210.16125 (2022), and the journal version *A Markov Chain Replacement
  Strategy for Surrogate Identifiers: Minimizing Re-Identification Risk*, Electronics 2025
  (`10.3390/electronics14193945`).

**Utility has two direct precedents.**
- *Utility Preservation of Clinical Text After De-Identification*, BioNLP 2022
  (`10.18653/v1/2022.bionlp-1.38`).
- *The Impact of De-identification on Downstream Named Entity Recognition in Clinical Text*,
  LOUHI 2020 (`10.18653/v1/2020.louhi-1.1`).

**Leakage / risk.**
- *DeIDClinic: A Risk-Aware Pseudonymization Framework*, arXiv 2410.01648 (2024).
- **TAB** (Computational Linguistics 2022, `10.1162/coli_a_00458`) — 1,268 ECHR court cases, and the
  only benchmark that marks which spans must be masked *to conceal identity* rather than to hit a
  category. English, legal.

**The thesis has a precedent worth citing rather than hiding:** *Automatic end-to-end
De-identification: Is high accuracy the only metric?* (arXiv 1901.10583, 2019).

## C.1 The gap, stated precisely

1. **Nobody treats the pseudonymisation function as the independent variable.** The field varies the
   *detector* and holds replacement fixed. ENISA gives five techniques and a qualitative verdict on
   each; no one has measured what each costs in utility and what each leaks, on real text.
2. **Detection, utility and leakage have never been run end to end on the same corpora.** The three
   literatures above use different languages, corpora and metrics, so the trade-off curve does not
   exist.
3. **Cross-document pseudonym stability is essentially unevaluated.** Benchmarks score span
   detection, not mapping integrity — collisions, drift across documents, or the same person
   receiving two pseudonyms. Note that searching for this is hard because "pseudonymity consistency"
   on arXiv returns almost entirely **blockchain** work; the term is taken. That is part of why the
   question is under-served.

## C.2 E-mail as a domain — yes, there are corpora

AM, 2026-09-06: **public data only**, no group data in this paper. That removes the Datenschutz
dependency and makes the whole study releasable. E-mail is a good second domain for exactly that
reason — the corpora are already public.

| corpus | notes |
|---|---|
| **CodEAlltag** | German e-mail corpus, built for **forensic linguistics** (2016). `10.1515/9783110464856-013` and *CodE Alltag: A German-Language E-Mail Corpus*. The corpus the German pseudonymisation work below runs on |
| **Enron** | the canonical public English e-mail corpus. See the ethics note below |
| Email-header corpus | *A Corpus of Email Headers with Personal Privacy Protection* (2017), `10.18178/jacn.2017.5.2.240` |
| Avocado (LDC) | ~licensed rather than free — **not verified here** |
| e-mail slices | AI4Privacy, PIIBench and REDACT all carry e-mail as a domain slice |

**The direct precedent, and our baseline.** *De-Identification of Emails: Pseudonymizing
Privacy-Sensitive Data in a German Email Corpus* — RANLP 2019, ACL Anthology **R19-1030**. Abstract,
verbatim: the task is decomposed into two steps — identify privacy-bearing named entities, then
replace them "by synthetically generated surrogates (e.g., a person originally named 'John Doe' is
renamed as 'Bill Powers')" — with "a system architecture for surrogate generation", evaluated on
**CodEAlltag**. That is our pipeline, in our second domain, in German, from 2019. It is a baseline
and a starting corpus, not a pre-emption: it does not vary the pseudonymisation function, and it
does not measure utility or leakage.

Also relevant: *Cloaked Classifiers: Pseudonymization Strategies on Sensitive Classification Tasks*,
PrivateNLP 2024 (`10.18653/v1/2024.privatenlp-1.13`) — pseudonymisation strategy crossed with a
downstream classification task, i.e. the utility axis already exists in miniature.

### The Enron problem, which we should turn into a point

*The Enron Corpus: Where the Email Bodies are Buried?* (arXiv 2001.10374, 2020) reports finding
**50,000 previously unreported instances of exposed PII** in Enron. The most-used public e-mail
corpus in the field is itself an unresolved privacy incident involving non-consenting individuals,
and it is cited routinely without comment. A TrustFMI audience will notice if we use it silently.
Better to say it out loud: it is evidence for the paper's own thesis about how the field evaluates
privacy.

### A third cross-lingual detection evaluation landed this year

*OpenAI Privacy Filter: A Cross-Lingual, Cross-Domain PII Evaluation Across 32 Benchmarks*
(arXiv 2608.02616, 2026) — 14 languages, 5 domains. It reinforces rather than blocks us, because of
*what* it found: **person names F1 = 0.40** and addresses 0.49, against e-mail addresses 0.78 and
phone 0.76; and collapse on non-Latin scripts (Arabic 0.04, Cyrillic 0.03).

That is the strongest single argument for our paper. **The entity class where pseudonym stability
matters most is the worst-detected one.** Everything downstream — surrogate assignment, cross-document
consistency, collision rate, leakage — is built on a 0.40-F1 foundation, and nobody has measured what
that does end to end.

## D. The thesis

ENISA states the tension and never measures it (2021 report, §2, on pseudonymisation **policies**):

> *"fully-randomised pseudonymisation offers the best protection level but prevents any comparison
> between databases. Document-randomised and deterministic functions provide utility but allow
> linkability between records."*

**Stability is not free.** The requirement that person 1 never collapses into person 2 — and that the
same person keeps the same pseudonym across a corpus — *forces* the deterministic policy, which is
the one the standard says permits linkage. Nobody has quantified the price.

**Claim.** Across languages and domains, the *policy* (deterministic / document-randomised /
fully-randomised) dominates both residual risk and utility loss, while the *cryptographic technique*
— the axis practitioners actually agonise over — is close to irrelevant under a deterministic policy,
because the effective attack is distributional, not cryptanalytic.

## E. Hypotheses (falsifiable, and the paper is interesting either way)

- **H1** Under a deterministic policy, A2 succeeds regardless of technique — hash and HMAC leak
  comparably. *Consequence: the field optimises the wrong axis.*
  **Measured 2026-09-07 and split in two** (`experiments/RESULTS_enron_vs_tab.md`):
  **H1a** the frequency signal survives *completely and identically* across all five techniques —
  Spearman ρ = 1.000 on both TAB and Enron, every technique the same. **H1b** whether that signal
  *identifies* anyone is a property of the corpus's frequency skew, not of the function: A2 top-1 is
  0.013 on TAB, whose entities are mentioned once or twice, and **0.201 on Enron**, whose people
  recur across thousands of messages. The practitioner's question is not which hash was used but how
  often the corpus's people recur.
- **H2** Detector recall dominates total leakage: a missed name leaks fully whatever the function.
  Measurable by comparing each detector — including the ensemble — against the gold-span oracle.
  If the ensemble closes most of the gap to the oracle, detection ceases to be the bottleneck and
  the policy axis becomes the whole story; if it does not, detection recall is the headline.
- **H3** Document-randomised policy cuts A2/A3 sharply at modest utility cost for tasks that do not
  need cross-document linkage, and catastrophic cost for those that do (patient timelines,
  coreference).
- **H4** Realistic and attribute-matched surrogates buy utility and cost privacy — they preserve
  gender, locale and frequency, which is exactly what A2 and A4 consume. Tested with frozen models
  throughout, so the surrogate form is compared at fixed model weights and no training confound
  enters.

## F. Enron is in — decided, with safeguards

**AM, 2026-09-07: Enron is included, and the ethics point is made explicitly in the paper.**

The reasoning, recorded because the paper has to state it: excluding Enron protects nobody. The
corpus stays public, the field keeps citing it silently, and the people in it are no safer. What
exclusion would cost is concrete — it is the only public e-mail corpus with real names in a natural
frequency distribution, the same people recurring across thousands of messages, a genuine downstream
task, and a real public auxiliary record to link against. E-mail is a required domain (AM,
2026-09-06), and no other English e-mail corpus supplies those four.

The attack target is **our own pipeline output**, not the corpus. We pseudonymise Enron ourselves and
then invert *our* pseudonyms; recovering a name that has sat on a public web server for twenty years
discloses nothing new. Marginal harm is what matters, and it is close to zero — provided the
following hold, which cost the study nothing:

1. **No real name from the corpus appears anywhere** in the paper, figures, tables, appendices or
   released artefacts. Attacks are reported as aggregate rates only.
2. **No released artefact re-exposes PII** — no mapping tables, no worked inversions, no example
   documents reproduced verbatim.
3. **A4 is scored against the corpus surface form**, not against external knowledge of the person,
   and is **stratified by public-figure status**.
4. **The 2020 audit is cited** (arXiv 2001.10374, 50,000 previously unreported PII instances) and the
   position is stated in the paper rather than left implicit.
5. **One written check with the FAU DPO.** Public US data processed in the EU for research is routine
   under GDPR Art. 89, but "it is public" is not itself a lawful basis. Ask once, in writing, cite
   the answer.

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
| **sampling rate** | 0.01 · 0.05 · 0.10 · 0.25 · 1.0 where affordable | **Size is a reported parameter** (AM, 2026-09-08), not something to balance away |

### 1.1 Why the corpora are one assembly, and why the oracle level exists

**On the meta corpus (axis E) and provenance (axis F).** AM, 2026-09-06: rather than pick corpora
one at a time, assemble a **single balanced meta corpus** spanning tasks and languages in one unified
schema, so the study's questions are answered in one pass and the cells become comparable across
languages for the first time. Two criteria came with the decision — *"PHI-inserted is not great. Same
for synthetic. Pseudonymised is ok, we can revert with rule-based approaches"*, and **task coverage
beyond medical, e-mail included**.

That makes **identifier provenance an axis in its own right (F)**, not a filter. A1 and A2 consume
the *name-frequency distribution*, so a corpus whose identifiers were generated or inserted cannot
support a claim about them. Real and realistic-surrogate corpora carry the primary result;
PHI-inserted and fully synthetic ones become the **control** that measures how much a benchmark's own
construction distorts apparent privacy — which every 2026 detection benchmark needs, since all of
them are fully synthetic.

Three consequences already fixed by the data (see `data/candidates.md`): only **TAB** and
**OntoNotes** annotate co-reference; only **i2b2 2014** (longitudinal, 296 patients) and **Enron**
(mailbox identity) support *cross-document* stability; **E3C** has no PII layer at all and so cannot
supply the gold-span oracle. **BRONCO150 is sentence-scrambled**, so the document-randomised policy
level is undefined on it.

The **gold-spans** level of D is essential: it separates *detector* error from *pseudonymisation*
error, which no prior work does. Everything downstream is otherwise confounded by a 0.40-F1 name
detector.

### 1.2 The ensemble, and why the pool and the rule are separate axes

**On the ensemble (axes D and D′).** In the group's own testing an ensemble outperformed every
single detector — but **that ensemble combined large language models only** (AM, 2026-09-07). Whether
classical detectors still add anything once several LLMs are in the ensemble is an open question, and
AM has asked for it to be answered rather than assumed. It is a large number of runs and it is the
way to find the best combination.

So the detector axis splits in two: a **pool** of detectors, and a **combination rule**, swept over
**subsets** of the pool. Three contrasts are compared on equal footing, by pinning the required
members of each subset:

| contrast | subsets |
|---|---|
| single detectors | every pool member alone |
| **LLMs only** | subsets drawn from the LLM members only — the in-house baseline |
| **hybrid** | every LLM-only subset plus at least one classical detector |

The hypothesis worth stating: a **high-precision rule-based recogniser for structured identifiers**
(IBAN, phone, e-mail, record numbers) should add most where LLMs are weakest, and a fine-tuned NER
should add least where the LLMs already agree. If the hybrid never beats LLMs-only, that is a clean
negative result about where the field should spend its effort.

Two further design points matter and should themselves be reported:

- **Combination rule.** Union-of-spans maximises recall — the privacy-relevant direction — at the
  cost of precision, and therefore of utility, because every false positive pseudonymises a token
  that carried meaning. Majority vote trades the other way. Report **union and vote separately**;
  the recall/precision asymmetry between them is exactly the privacy/utility trade-off the paper is
  about, appearing a second time at the detector level.
- **The ensemble is the practical recall ceiling**, and the **gold-span oracle** is the true ceiling.
  The gap between them measures what better detection could still buy; the gap between single
  detectors and the ensemble measures what ensembling already buys. Both belong in the results.

Concretely, the pool carries at least: Presidio (rule-based), one fine-tuned multilingual NER,
GLiNER (zero-shot), the CodEAlltag `privacy_tagger` on the German e-mail arm, two or more distinct
LLMs individually, and gold spans; the rules carry at least union, majority vote and weighted vote.

---

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
| **A3** | structural linkage (fixed cosine over entity profiles); on Enron the **~184-employee org chart** is the public auxiliary record to link against | all | Rank-1 / Rank-5 / mAP |
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

### 2.5 The reasoning behind the measurements, as first recorded

Kept verbatim from the earlier plan. It states *why* each measurement is the one chosen, which §2.1
to §2.4 above do not, and it carries citations that exist nowhere else.

### Measurements

**1. Detection** — P/R/F1 per entity type, reported separately for PERSON and LOCATION since those
carry the stability requirement. Recall is the privacy metric, precision the utility metric.

**2. Stability** — the axis nobody reports:
- **collision rate** — distinct real entities sharing a pseudonym ("person 1 confused with person 2")
- **fragmentation rate** — one real entity receiving several pseudonyms (*Dr. Weber*, *Weber*,
  *F. Weber* → three), which is the more common failure and hurts utility more
- both require coreference-resolved gold, which is why **TAB matters** — it annotates co-reference
  and confidential attributes, not just categories

**3. Utility — measured with frozen models, no training** (AM, 2026-09-08).

The instrument is inference, not fine-tuning. The reason is not cost: **a TrustFMI audience does not
fine-tune an encoder on a de-identified corpus, it prompts a foundation model over one**, so the
question that matters is how much pseudonymisation degrades a *frozen* model. Every signal below is
obtained by running an existing model over the original and the pseudonymised text and comparing.

| signal | method | cost |
|---|---|---|
| legal task | ECHR **article classification**, zero-shot, gold labels ship in TAB `meta.articles` | free gateway |
| e-mail task | Enron **folder classification** (Klimt & Yang 2004), zero-shot | free gateway |
| clinical task *(if the DUA corpora arrive)* | ICD-10/OPS/ATC coding, medication IE, zero-shot | free gateway |
| **co-reference** | frozen resolver over original vs pseudonymised, scored against gold chains | CPU/small GPU |
| NER | frozen multilingual NER, agreement between the two versions | CPU/small GPU |
| semantic drift | embedding displacement, `multilingual-e5-large` — one model across all six languages | free gateway |
| fluency | LM perplexity shift, one frozen LM across all cells | small GPU |

**Co-reference is the sharpest of these** and was previously buried as a proxy. Fragmentation *is*
chain breakage: a resolver's CoNLL F1 on pseudonymised text measures the utility cost of exactly the
failure the stability metrics count, on the same documents. It ties measurement 2 to measurement 3
directly, which no prior work does.

**What this gives up, stated plainly:** whether a model *retrained* on pseudonymised text recovers
its performance. If it does, the field's assumption that de-identification costs utility is a
domain-shift artefact rather than information loss. That is a real question and it is the one thing
here that requires training by definition; it is out of scope for this paper and belongs in the
future-work section rather than being quietly dropped.

**One confound to control.** A frozen LLM may recognise an ECHR case or an Enron thread from its
training data and answer from memory rather than from the text in front of it. Task scores would then
measure memorisation, not utility. Mitigation: **stratify by memorisation**, reusing A4's
public-figure split, and report a no-context control. The same confound is a *result* for A4 and a
*bias* for utility, and it must not be handled in only one of the two places.

**4. Leakage** — four attacks of increasing knowledge:
- **A1 dictionary / brute force.** Enumerate a candidate name list (census surnames, gazetteers),
  apply the pseudonymisation function, match. Directly tests the hash-vs-HMAC question, reported as
  inversion rate against name frequency and name length. *Prediction: hash inverts almost completely
  for short frequent names; HMAC resists.*
- **A2 frequency analysis.** No inversion needed — under a deterministic policy the pseudonym
  frequency distribution mirrors the real one, so the most frequent pseudonym is the most frequent
  name. **This attack is indifferent to the cryptographic technique.** If it succeeds, it shows the
  crypto axis is the wrong thing to optimise.
- **A3 linkage.** Link pseudonymised documents to each other, and to an auxiliary public record, via
  co-occurrence structure.
- **A5 relational re-identification** (AM, 2026-09-08) — the one place a *trained* model is worth
  building. A learned embedding of the facts and relations around an entity, linking a pseudonymised
  entity to a known one; the text analogue of Packhäuser et al., *Deep learning-based patient
  re-identification …* (Sci Rep 2022, `10.1038/s41598-022-19045-3`), which showed that images
  believed de-identified are not. Attacks what pseudonymisation cannot remove: the name is replaced,
  the profile is not. Paired with A3 so the **A5 − A3 gap measures what learning buys the adversary**.
  Rank-1 / Rank-5 / mAP on entity-disjoint splits, on Enron. *Prediction: strong under deterministic,
  weaker under document-randomised, fails under fully-randomised, and flat across all five
  techniques.* Corollary if it holds: **the stability requirement is itself the vulnerability**.
- **A4 LLM re-identification.** Give a modern LLM the pseudonymised document and ask who it is,
  with and without auxiliary context. This is the threat model of 2026 and the one the workshop cares
  about. **Scored as recovery of the surface form already present in the corpus**, never as inference
  of new facts about an individual — see the Enron safeguards below. **Stratified by public-figure
  status**, because a corpus subject the model has memorised and one it has not are different
  experiments; that split also tests *Personal Information Parroting in Language Models*
  (arXiv 2602.20580) directly.

---

## 3. Statistics and reporting

- Per-document score vectors are the primary artefact; summaries are derived from them.
- Every result row carries: cell configuration, seed, **sampling scheme + rate**, corpus version,
  detector, prompt version, library versions, commit hash.
- Bootstrap CIs over documents where a CI is wanted.
- Results are parquet/JSONL artefacts on disk, never numbers in prose.

## 3.1 The unified record schema

One format, one converter per source, nothing else changes downstream. Merged verbatim from
`data/metacorpus.md` on 2026-09-09, where it was the only place a record shape was ever specified.

```jsonc
{
  "doc_id":      "tab/001-12345",
  "corpus":      "tab",
  "language":    "en",
  "script":      "Latn",
  "domain":      "legal",
  "genre":       "court_judgment",
  "provenance":  "real",            // real | surrogate | placeholder | inserted | synthetic
  "split":       "train",
  "text":        "...",
  "subject_id":  "patient_0042",    // cross-document identity where it exists; null otherwise
  "task":        {"name": "echr_violation", "label": ["Art.6", "Art.13"]},
  "spans": [
    {"start": 143, "end": 154,
     "text":       "John Weber",
     "type":       "PERSON",        // harmonised taxonomy
     "type_src":   "NOMBRE_SUJETO_ASISTENCIA",
     "entity_id":  "e17",           // co-reference chain; null where unannotated
     "identifier_class": "DIRECT"}  // DIRECT | QUASI | NO_MASK, where annotated
  ]
}
```

**Do not invent the taxonomy.** PIIBench already normalises 80+ label variants into 48 canonical
types across ten corpora; adopt its mapping and record every deviation. Sources to harmonise:
MEDDOCAN 29 types · i2b2 18 PHI classes · CodEAlltag's hierarchy (ACTOR{ORG, PERSON{FAMILY,
GIVEN{FEMALE, MALE}}, USER}, DATE, FID{PASS, UFID}, LOC{STREET, STREETNO, CITY, ZIP}, ADD{EMAIL,
PHONE, URL}) · TAB's semantic categories · OntoNotes 18 NE types · REDACT 51 types.

`entity_id` and `subject_id` are what make the stability metrics computable; every converter must
either populate them or declare them null, and a corpus with both null cannot enter a stability cell.

---


---

## 4. Corpora and their roles

A corpus enters the **full** design only if detection, stability **and** utility can be measured on
the same documents — which is the gap `experiment_plan.md` §C.1 claims nobody has closed.

| corpus | detection | stability | utility | role |
|---|---|---|---|---|
| **TAB / ECHR** (en, legal) | ✅ 8 types, DIRECT/QUASI | ✅ co-reference | ✅ 30-label articles | **full** |
| **OntoNotes** (en, zh, ar; 5 genres) | ✅ 18 NE types | ✅ co-reference | ✅ co-reference + NER | **full** |
| **Enron** (en, e-mail) | ⚠ structural, header-derived | ✅ cross-document identity | ✅ folder · intent · formality | **full** |
| **CARDIO:DE** (de, clinical) | ⚠ DATETIME only — 18,148 `<[Pseudo] …>` date markers, no name layer | ❌ | ✅ medication IE · section classes | utility **+ leakage** (AM, 2026-09-08) |
| **CodEAlltag** (de, e-mail) | ❌ none released | ❌ | ✅ formality · 7-way topic (the pXL partition *is* the label) | utility only |
| **BRONCO150** (de, clinical) | ✅ ICD/OPS/ATC | ❌ sentence-scrambled | ✅ coding | utility only — **not yet received** |
| MEDDOCAN · MedDeID · REDACT · AI4Privacy | ✅ | ❌ | ❌ | **OUT** (AM, 2026-09-08) — no utility task, so no cell where a method's effect is attributable |
| E3C | ❌ no PII layer | ❌ | ❌ | **OUT** (AM, 2026-09-08) |

**The synthetic members are out** (AM, 2026-09-08): *"Let's only use data that has some utility."*
Attributing an effect to a method requires detection, stability **and** utility on the same
documents, and MEDDOCAN, MedDeID, REDACT, AI4Privacy and E3C carry no utility task. **Only TAB,
OntoNotes and Enron carry all three.**

**What the identifiers are, stated once and not made into an axis.** TAB, OntoNotes and Enron carry
**real names in a natural frequency distribution**. CodEAlltag carries **realistic surrogates** — its
README: privacy-sensitive spans were annotated manually, then *"substituting them with realistic
surrogates automatically"*. CARDIO:DE carries **shifted dates and no name layer**.

This matters for exactly two attacks. **A1 and A2 both consume the name-frequency distribution**, so
their numbers transfer only where that distribution is natural — TAB, OntoNotes, Enron. On CodEAlltag
they are weaker evidence, and on CARDIO:DE they do not apply at all. That is a stated limit on where
those results hold. It is **not** an experimental factor and there are no cells for it.

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
| detection · utility · within-document stability · **A2** | ~~`stratified`~~ | every subject represented in proportion; frequency *ranks* survive thinning |
| **A3 · A5 · drift** | **`subject`** or `time` | profile completeness is the signal; document sampling starves it |

### Enron uses one scheme: `subject` @ 0.10 (AM, 2026-09-08)

The per-measurement assignment above was the design, and it is **superseded for Enron**. Two schemes
are two different document sets, so detection would have to cover their **union** — and Enron is
already 86 % of the detection budget (§7.4.1). One scheme, and it is `subject`:

- **Profile completeness cannot be recovered any other way.** 67 % retained per entity against
  `stratified`'s 20 %, measured. A3 and A5 are starved by the alternative; nothing is starved by
  this one.
- **A2 tolerates it.** Inside a kept mailbox the frequency distribution is *complete*, so pseudonym
  frequency still mirrors real-name frequency. What is lost is statistical power — fewer entities —
  not the effect, and §5 predicts A2 is robust to rate anyway.
- **Detection and utility do not care which documents**, only how many.
- With one scheme, detection, stability, utility and leakage land on **the same documents**, which is
  the property §4 claims for Enron in the first place.

**How it is built** (`experiments/build_enron.py`): Enron cannot be materialised in full anywhere —
the head node has too little memory, and a full pass on an 18 GB laptop was **killed by memory
pressure** while constructing the 517,401 documents. So the sample is a **stream filter** applied
before documents are built: one pass over every message builds the identity table (names only —
11,124 of them in 30 s), whole mailboxes are drawn with `sampling.by_subject`'s rule and seed, and a
second pass builds documents for those mailboxes using the **full** table. Cross-document identity is
therefore complete even for mailboxes outside the sample.

The result is written as JSONL (`pseudonymkit.serialisation`) and shipped to the cluster. That
serialisation exists **only** for Enron; every other corpus is read from its release by its adapter.

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

### 7.1 What the first detection run got wrong — recorded, not hidden

The array submitted on 2026-09-08 was **9 Slurm tasks, one per (corpus, model), each a serial HTTP
client**: one request in flight, 2.3–25.6 s per document. It therefore held **all 8 of the
association's `MaxJobs` slots** with allocations of 2 CPUs and 16 GB apiece that were blocked in
`recv()` and doing no computation — and it blocked AM's own job. AM stopped it after 28 minutes
(2026-09-08); **the cache preserved all 1,599 completed documents with 0 errors**, and the work
resumes from there.

Two planning errors, both to be fixed before anything is resubmitted:

1. **Parallelism in the wrong layer.** Slurm allocations were used to obtain concurrency against a
   *network service*. One allocation with an internal thread pool of *W* workers gives the same
   concurrency in one eighth of the footprint, and leaves the cluster free for GPU work.
2. **No accounting of the detection surface.** The array covered **3 of the ~10 corpora** and **one
   of axis D's six detector levels**, with no table of what the whole of detection costs — so there
   was no way to say whether the run was on schedule for 2026-09-25. §7.5 is that table's
   precondition list.

### 7.2 Resource classes — they are not interchangeable

| work | bound by | GPU | job shape |
|---|---|---|---|
| gateway LLM detection (axis D, LLM levels) | network latency | no | **1–2 jobs**, internal thread pool |
| A4 LLM re-identification | network latency | no | as above |
| classical detection — Presidio, GLiNER, `obi/deid_roberta_i2b2`, `privacy_tagger` | GPU | **yes** | short batched jobs, **pin the card** |
| gold spans (oracle level) | nothing | no | free; it is adapter output |
| pseudonymisation, stability, A1–A3, A5 | CPU | no | minutes |

Mixing the first class into Slurm tasks is what §7.1 got wrong. The third class has **not been
written yet** and is the real gap in axis D.

### 7.3 Measured LLM throughput — seconds per document, serial

From the 1,599 cached records of the cancelled run. These are the numbers any schedule must use;
they are not estimates.

| corpus | `gpt-oss-120b` | `Qwen3.6-35B-A3B` | `gemma-4-31B` |
|---|---:|---:|---:|
| TAB (ECHR judgments, long) | 22.4 | 20.2 | 18.5 |
| Enron (e-mail, short) | 25.6 | 19.7 | 13.7 † |
| CodEAlltag (e-mail, short) | 8.2 | 15.4 | 2.3 |

† one document only; not yet a rate.

Document **length**, not model size, dominates: `gemma-4-31B` ran CodEAlltag at 2.3 s and TAB at
18.5 s. Any schedule must be per (corpus, model), never a single global rate.

### 7.4 The detection surface, sized — 2026-09-08

Counted from the releases on the cluster. **Only the corpora AM kept** (§4): the synthetic members
are out, so they are not in this table and cost nothing.

| corpus | documents | language(s) | note |
|---|---:|---|---|
| TAB / ECHR | 1,268 | en | 274 model-runs already cached |
| **OntoNotes en** | 3,637 | en | 2,384 also carry `.coref` |
| **OntoNotes zh** | 1,911 | zh | 1,729 with `.coref` |
| **OntoNotes ar** | 446 | ar | 447 with `.coref` |
| **Enron @ 0.10** | **≈ 51,700** | en | the rate AM set (`data/metacorpus.md` §14) |
| CodEAlltag_S | 800 | de | 1,156 model-runs already cached; utility only |
| CodEAlltag_XL | ~1,469,000 across 7 topics | de | utility only, **must be sampled** |
| CARDIO:DE 400 | 400 | de | 🔒 AM only; utility + leakage |
| BRONCO150 | 150 | de | not yet received |

**OntoNotes co-reference is not uniform and the plan must not assume it is.** English newswire has
2,102 `.name` files but only 922 `.coref`; English `pt` (pivot text) has 260 `.coref` and **no**
`.name` at all. Stability on OntoNotes is scored on the ~4,560 documents carrying both layers, and
**that** number is reported, never the corpus total.

### 7.4.1 What that costs — and where the cost actually sits

Detection is needed on the three **full** corpora (axis D/D′ is scored there) and on CodEAlltag and
CARDIO:DE (no gold, so detection is the *input* to pseudonymisation rather than something scored).
Three gateway models, at the measured rates of §7.3:

| corpus | documents | calls | serial hours | share |
|---|---:|---:|---:|---:|
| TAB | 1,268 | 3,804 | 21 | 2.8 % |
| OntoNotes (en+zh+ar) | 5,994 | 17,982 | 75 | 10.0 % |
| CodEAlltag_S | 800 | 2,400 | 5 | 0.7 % |
| CARDIO:DE | 400 | 1,200 | 3 | 0.4 % |
| **Enron @ 0.10** | **51,700** | **155,100** | **≈ 646** | **86.1 %** |
| **total** | **60,162** | **180,486** | **≈ 750** | |

**Enron is 86 % of the entire detection budget**, and everything else together is 104 serial hours.
Two consequences:

1. **Everything except Enron is affordable today.** 104 h serial is ~7 h at *W* = 16, in one
   allocation. That is a night's work and needs no decision from anyone.
2. **The Enron rate is the schedule.** §5 already prescribes a **size sweep** — 0.01 / 0.05 / 0.10 /
   0.25 — with the explicit prediction that A2 is robust to rate and A3/A5 are not. Running the
   sweep *upward* (0.01 → 0.10) is the plan's own design, not a reduction of it: at 0.01 Enron is
   5,170 documents and 65 serial hours, and each higher rate is a further experimental point rather
   than a repetition. **AM decides where that sweep stops**; no agent may settle it (§0).

| shape | 104 h (all but Enron) | +Enron @0.01 | +Enron @0.10 |
|---|---|---|---|
| serial, as submitted on 2026-09-08 | impossible — past the 24 h limit | impossible | impossible |
| one allocation, *W* = 16 | **6.5 h** | 10.6 h | 47 h (needs checkpoint + resubmit) |
| one allocation, *W* = 32 | 3.3 h | 5.3 h | 23 h |

**The runner rewrite in §7.5 is not an optimisation.** Serially, even the 104-hour remainder cannot
finish inside a 24 h wall clock.

### 7.5 Preconditions before any detection job is resubmitted

1. **`DetectorCache.append` must take a lock.** It is currently correct only because there is one
   writer per file; a thread pool breaks that assumption and would interleave JSONL records.
2. **Load each corpus once per job**, not once per (corpus, model). Enron currently costs a full
   1.3 GB decompression per task.
3. **Size the whole detection surface first** — OntoNotes (en/zh/ar), CARDIO:DE 400, MEDDOCAN,
   MedDeID, REDACT, AI4Privacy, PIIBench — and put document counts and estimated hours in a table
   here. Submitting before that table exists is what §7.1 describes.
4. **Write the classical-detector job.** Four of axis D's six levels have no code and no job.
5. **Ask AM before submitting.** The cluster is shared with the group and with AM's own work.

### 7.6 Standing cluster rules

- **Everything resumes.** A killed job re-reads the cache and skips what is recorded; documents that
  errored are retried rather than frozen into the results. This is what made §7.1 cost nothing.
- **Slurm limits:** assoc `MaxJobs` = 8; QOS `miti` = 4 concurrent, `turbo` = **10 concurrent, 100
  submitted**, 24 h wall clock. Throttle arrays with `%8` — and prefer *not* to need an array.
- **The head node is not for jobs.** A 20,000-message load was OOM-killed there; the same load runs
  in 100 s inside an allocation.
- **`mkdir -p results/slurm` inside every job script.** Slurm redirects stdout *before* the script
  runs; a missing directory fails the job with no log at all.
- `/cluster` is at 95 %. Text corpora are small; do not write model checkpoints.

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

**Corpus facts established 2026-09-08, from the releases themselves:**

| finding | consequence |
|---|---|
| **CARDIO:DE marks every de-identified date in place** — `<[Pseudo] 12/03/2019>`, 18,148 occurrences in 500 letters, and the marker wraps **nothing but dates** | the corpus gains a real, narrow **DATETIME gold layer**; the adapter emits it |
| **CARDIO:DE has almost no semantic placeholders** — 178 `<NONE>`, one `<TIME>`, one `<ORG>` in 5.9 M characters | it is **not** placeholder-masked for persons, as this repo's notes previously assumed. How names were handled is **not stated in the release README** — open item, §10 |
| **CARDIO:DE's CAS text and `.txt` are not byte-identical** — same length, agreeing everywhere except that each newline is a space in `sofaString` (XML attribute-value normalisation) | offsets coincide; the adapter keeps the `.txt` and asserts the invariant per letter, dropping and counting any that fail |
| **CARDIO:DE100 carries no annotations** — the CAS files exist but hold no `custom:` layers | the heldout split supports neither utility task; the adapter defaults to CARDIO:DE400 |
| **CodEAlltag_S carries realistic surrogates** — its README: privacy-sensitive spans were annotated manually, then *"substituting them with realistic surrogates automatically"* | read from the release, not inferred; bounds where A1/A2 transfer (§4) |
| **The CodEAlltag formality scores were Git-LFS pointers**, not data — the cluster has no `git-lfs` | fetched over `media.githubusercontent.com`; all eight document-level files now present. The adapter refuses to read a stub as "no scores" |

**Provenance audit, 2026-09-09** — five corpora, each read against its own specification and then
checked against the data, each audit adversarially challenged:

| finding | consequence |
|---|---|
| **CARDIO:DE person tokens are the de-identifier's own IOB output**, shaped `<letter>-<CLASS>`: 22,531 tokens, 89 types, **11 distinct strings in the person slot** across 400 letters; the rarest still occurs in 386 of them, and one string fills the patient slot in 384 | **A1 and A2 are impossible here**, not weak — no dictionary to look up, no distribution to match. A naive cross-document linker links all 400 letters to each other and returns a spuriously perfect rate. Reported as impossible per §0, never substituted |
| **62–83 % of every model's CARDIO:DE spans land inside a `<[Pseudo] …>` marker**; 95.7–98.9 % of PERSON spans land on a tag | CARDIO:DE PERSON detection measures artefact-spotting. The one supportable cell is DATETIME against the marker layer (F1 0.678–0.888), a valid within-corpus model ranking and an invalid cross-corpus F1 |
| **CARDIO:DE dates**: admission years span 2019–2519; 70 of 400 letters state ages of 280–459; the per-document offset is constant (age reproduced in 400/400) | within-document intervals and orderings are intact and usable; absolute dates and any model-judged plausibility are not |
| **CodEAlltag surrogates were drawn frequency-independent by construction** — measured surname Zipf slope **−0.335** against a natural ≈ −1; given names near-uniform from a closed list of 975; **0 `.de`, 0 `.com`, 0 real freemail** among all 56 pS e-mail addresses | A2 is weakened rather than void — the given-name head is at natural concentration, the surname head flattened ~7× |
| **Enron gold is 44.3 % artefact**: `Mail`, `mail`, `info`, `eren` admitted as person entities; 26.6 % of gold spans matched mid-word (`Mail` inside `JavaMail`) because grounding uses `str.find` without a word boundary | fixable in the adapter at **zero detector cost** — gold is recomputed at scoring time. No Enron P/R/F1 may be quoted before it is |
| **Enron surface**: 45.7 % of characters are RFC-822 headers, 51.4 % of gold PERSON mentions sit in the header block, 58.0 % of long-body character mass is duplicate, 13.0 % of documents have an empty body | the head of Enron's name distribution is mailbox owners stamped mechanically into every message |
| **TAB**: applicants named verbatim in 1,242/1,268; court-anonymised cases excluded at selection. But the applicant's surname occurs **once** in 69.2 % of judgments while *"the applicant"* occurs a median of 17 times, and 79.6 % of PERSON mentions are agents, judges and counsel | A2 on TAB scores mostly non-protected persons unless scored against the applicant |
| **OntoNotes was not de-identified at all** — exhaustive documentation grep and a 5,994-document pattern scan both return zero. Surname Zipf −0.925 against a US-Census −0.918 | but Spearman ρ with census frequency is 0.263: a newswire-celebrity distribution, real but not population-representative |
| **No corpus is both identifier-real and surface-real.** OntoNotes is Penn-Treebank tokenised throughout, Chinese space-segmented, Arabic 82.6 % diacritised; Enron is real identifiers inside a processed archive dump | a limitation to state, not a reason to withdraw anything |
| **H1b's stated mechanism is not the measured one** | see §10 |

**Unresolved:** the fair A3-vs-A5 comparison on identical galleries (A5's entity-disjoint split gives
it a smaller gallery, so the deterministic 1.04× sits inside that confound).

---

## 10. Open items

1. **BRONCO150** — no reply from Prof. Leser since 2026-09-07.
2. **n2c2 2014** — registration closed; ask DBMI when it reopens. Its loss removes clinical
   cross-document stability and the only cell where detection and utility shared documents.
3. **The fair A3/A5 comparison** — A3 restricted to A5's held-out entities and gallery.
4. **CARDIO:DE person-name handling** — dates are marked in place, names are not, and the release
   README does not say what was done to them. Read it out of Richter-Pechanski et al., *Sci Data*
   10, 207 (2023) before making any claim about the corpus's identifiers.
5. **Where the Enron size sweep stops** — Enron at rate 0.10 is 86 % of the whole detection budget
   (§7.4.1). The sweep 0.01 → 0.25 is the plan's own design; its upper end is AM's to set.
6. **Four of axis D's six detector levels have no code** — Presidio, GLiNER, `obi/deid_roberta_i2b2`
   and `privacy_tagger` are GPU work and are unwritten (§7.2).
7. **Paper scoping** — which panels fit eight pages.
8. Is the full A×B×C×D×D′×E×F factorial affordable, or do we fix a sensible default per axis and vary one
   at a time around it? Compute is available; annotation-limited corpora may not support every cell.
9. Which E3C languages carry enough PII density to be worth including?
10. Does the **2026 revision of ISO 25237** change any recommendation we would make? Somebody needs a
   copy — it is not open access.
11. **Ask Eder / Krieg-Holz / Hahn for CodEAlltag's annotated S+d subset.** The release ships the
    800 donated e-mails without the manual span annotations that were made before substitution. If
    the authors will share them, CodEAlltag gains gold spans — and it is one of only two routes to a
    scorable German detection cell, the other being BRONCO150. Carried over from
    `data/metacorpus.md` §7, which was rewritten as a corpus list on 2026-09-09.
12. Ensemble composition: which LLMs, and is the combination rule fixed across languages or tuned per
   language? Tuning per language risks overfitting the benchmark.
