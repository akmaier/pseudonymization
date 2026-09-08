# Experiment plan — end-to-end evaluation of text pseudonymisation

**Scope set by AM, 2026-09-06:** multilingual, multi-domain, multi-method; evaluate **detection,
utility and leakage** end to end. Compute is not a constraint. The distinctive requirement is
**pseudonym stability** — person 1 must never collapse into person 2, and the same for locations.

## Yes, there are standards — and one was revised this year

| | |
|---|---|
| **DIN EN ISO 25237:2026-06** | *Medizinische Informatik — Pseudonymisierung* (ISO/DIS 25237). `10.31030/3696721` — a **2026 revision** of the health pseudonymisation standard |
| DIN EN ISO 25237:2017-05 | the superseded edition, `10.31030/2555889`; BSI equivalent *Health informatics. Pseudonymization* `10.3403/30285709` |
| **ENISA 2021** | *Data Pseudonymisation: Advanced Techniques and Use Cases* — downloaded and read; the practical European reference |
| ENISA 2019 | *Pseudonymisation techniques and best practices* |
| ISO/IEC 20889 | privacy-enhancing de-identification terminology and technique classification — **not directly verified**, iso.org returns 403 to scripted access |
| GDPR Art. 4(5) | the legal definition pseudonymisation has to satisfy |

Publishing against a standard revised in **June 2026** is a good position for a workshop paper.

## ENISA's technique taxonomy — this is the method axis

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

## What already exists — the pieces, never assembled

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

## The gap, stated precisely

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

## E-mail as a domain — yes, there are corpora

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

## The thesis

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

## Experiment plan

### Factors

| axis | levels |
|---|---|
| **A. Policy** (ENISA) | deterministic · document-randomised · fully-randomised |
| **B. Technique** (ENISA) | counter · RNG + mapping table · cryptographic hash · HMAC · symmetric encryption |
| **C. Surrogate form** | opaque tag (`[PERSON_1]`) · realistic surrogate (*John Doe → Bill Powers*) · attribute-matched surrogate (gender/locale preserved) |
| **D. Detector pool** | rule-based (Presidio) · **publicly released** fine-tuned de-ID NER (`obi/deid_roberta_i2b2`, `StanfordAIMI/stanford-deidentifier-base`) · zero-shot NER (GLiNER) · domain-specific (CodEAlltag `privacy_tagger`) · ≥2 individual LLMs · **gold spans** (oracle). **No detector is trained by us** — a detector fine-tuned on a corpus's own split has seen the entities we then protect, which inflates its recall and confounds everything downstream |
| **D′. Combination rule** | *span-level:* union · majority vote (k) · intersection · weighted vote · cascade · *token-level (ROVER-style):* per-token BIO voting — all swept over **subsets** of the pool |
| **E. Corpus** | the **meta corpus** — one balanced assembly across language, domain, task and provenance, in a single schema. Members: legal TAB/ECHR (en) · e-mail Enron (en), CodEAlltag (de) · multi-genre OntoNotes (en, **zh**, **ar**) · clinical i2b2/n2c2 2014 (en, longitudinal), CARDIO:DE (de), BRONCO150 (de), MEDDOCAN (es), MedDeID (nl), E3C (multi) · general/financial AI4Privacy, PIIBench slice, REDACT. See [`data/metacorpus.md`](data/metacorpus.md) |
| **F. Identifier provenance** | real · realistic-surrogate · placeholder-masked · PHI-inserted · fully synthetic |

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

### Enron is in — decided, with safeguards

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

### Hypotheses (falsifiable, and the paper is interesting either way)

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

### Deliverables

Released code, the full factorial results, and the **stability–leakage frontier** per language and
domain — the curve a practitioner actually needs and which currently does not exist. No new corpus,
no new detector: the contribution is the axis nobody varied.

## Open questions

- **Balance implies capping.** Enron has ~500 k messages, TAB has 1,268 documents. A balanced meta
  corpus means sampling the large members — a *design* decision, explicitly not the cost saving that
  `CLAUDE.md` §1 forbids. The rule (per-corpus cap? equal token budget per language?) has to be
  written down by AM before any sampling happens.
- Is the full A×B×C×D×D′×E×F factorial affordable, or do we fix a sensible default per axis and vary one
  at a time around it? Compute is available; annotation-limited corpora may not support every cell.
- Which E3C languages carry enough PII density to be worth including?
- Does the **2026 revision of ISO 25237** change any recommendation we would make? Somebody needs a
  copy — it is not open access.
- Ensemble composition: which LLMs, and is the combination rule fixed across languages or tuned per
  language? Tuning per language risks overfitting the benchmark.
