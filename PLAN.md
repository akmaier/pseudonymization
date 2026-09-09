# The argument — thesis, gap, hypotheses, related work

**What is to be run lives in [`experiment_plan.md`](experiment_plan.md), and only there.** That file
is the authority on factors, levels, metrics, statistics, corpora and compute. This one carries the
*argument*: why the study exists, what the literature has and has not done, what we claim, and which
hypotheses could falsify it.

The two were previously duplicated, and the duplication is what let an "axis F / identifier
provenance" factor and a T1–T5 tier taxonomy grow here on top of a remark that was a
**corpus-selection criterion, not a factor** (AM, 2026-09-06: *"PHI inserted is not great. Same for
synthetic. Pseudonymised is ok"*). Both were struck on 2026-09-08. The factor design has therefore
been removed from this file rather than restated: **do not reintroduce it here.**

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

## What is run, and where it is specified

The factor design (policy × technique × surrogate form, the key normaliser, the detector pool and its
combination rules), the corpora and their roles, the three stability metrics, the task-based utility
protocol, the five attacks, the statistical protocol and the sampling schemes are **all specified in
[`experiment_plan.md`](experiment_plan.md)**. They are deliberately not repeated here.

One design commitment belongs to the argument rather than to the specification, and so is stated
here:

**Frozen defenders, trained attackers.** The defence is measured as it is deployed — no model is
fine-tuned by us, because a detector trained on a corpus's own split has already seen the entities we
then protect. The attacker, by contrast, is made as strong as we can make it: A5 is the study's only
trained model. A leakage number is only meaningful against the best adversary available, and the
A5 − A3 gap is what learning buys that adversary.

## Enron is in — decided, with safeguards

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

## Hypotheses (falsifiable, and the paper is interesting either way)

- **H1** Under a deterministic policy, A2 succeeds regardless of technique — hash and HMAC leak
  comparably. *Consequence: the field optimises the wrong axis.* Split in two once measured:
  - **H1a — the frequency signal is technique-independent.** *Supported.* It survives completely and
    identically across all five techniques, on both corpora tested. This is a property of the mapping
    read against co-reference gold, so no corpus-provenance finding touches it.
  - **H1b — whether that signal *identifies* anyone is a property of the corpus, not the function.**
    *Needs re-derivation before it goes in the paper.* The direction held on the first measurement,
    but the provenance audit showed the mechanism was not the one claimed: what looked like two
    natural frequency skews is document genre on one side and an artefact of our own header-derived
    annotation on the other. The claim may well survive restatement on repaired gold; it may not.

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

## What the corpora can and cannot carry

A provenance audit read each release's own de-identification specification and checked it against the
data. Three consequences are arguments the paper has to make; the measurements behind them are in
[`experiment_plan.md`](experiment_plan.md) §9 and are not restated here.

**No corpus is simultaneously identifier-real and surface-real.** The corpora with the most untouched
identifiers have the most processed text, and the one with the most natural text has the most
processed identifiers. Every result in this study is therefore measured at some remove from
deployment, and the paper should say which remove rather than imply none.

**Two corpora were already pseudonymised, to a degree that voids their leakage cells.** Where the
prior de-identification collapsed an identifier class onto a handful of constants, there is nothing
for a dictionary or a frequency attack to consume, and a linkage attack inverts rather than fails —
it links everything to everything. Per `experiment_plan.md` §0 those cells are reported as
impossible, named with their obstacle, and never substituted by a proxy.

**"Real names in a natural frequency distribution" is one sentence doing two jobs.** All three
tier-one corpora carry real names; none carries an unqualified natural frequency distribution. The
*shape* of the distribution survives in all three; the *head* survives in none, for a different
reason in each. Results that depend on the head — A1's frequency banding above all — must say so.

## Deliverables

Released code, the full factorial results, and the **stability–leakage frontier** per language and
domain — the curve a practitioner actually needs and which currently does not exist. No new corpus,
no new detector: the contribution is the axis nobody varied.

## Open questions

- Is the full A×B×C×D×D′×E factorial affordable, or do we fix a sensible default per axis and vary one
  at a time around it? Compute is available; annotation-limited corpora may not support every cell.
  **This remains AM's to decide and no agent may settle it** by default, by omission, or by starting
  small. (Axis F was struck on 2026-09-08 and is not part of the design.)
- **The study has no scorable German detection cell**, so it cannot presently make a German detection
  claim at all. That is an acquisition problem, not a reason to drop the language — what exists and
  what would fill it is in `experiment_plan.md` §10.
- Does the **2026 revision of ISO 25237** change any recommendation we would make? Somebody needs a
  copy — it is not open access.
- Ensemble composition: which LLMs, and is the combination rule fixed across languages or tuned per
  language? Tuning per language risks overfitting the benchmark.
