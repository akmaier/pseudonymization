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
| **D. Detector** | rule-based (Presidio) · fine-tuned NER (XLM-R / GLiNER) · single LLM · **ensemble across LLMs + baselines** · **gold spans** (oracle) |
| **E. Corpus** | clinical: MEDDOCAN (es), CARDIO:DE (de), BRONCO (de), E3C (multi), MedDeID (nl), i2b2/n2c2 (en) · legal: TAB/ECHR (en) · e-mail: CodEAlltag (de), Enron (en) · general/financial: PIIBench slice |

The **gold-spans** level of D is essential: it separates *detector* error from *pseudonymisation*
error, which no prior work does. Everything downstream is otherwise confounded by a 0.40-F1 name
detector.

**On the ensemble (axis D).** In the group's own testing an **ensemble across several LLMs combined
with the baseline detectors** outperformed every single detector, so it is not an afterthought — it is
the strongest realistic system and belongs in every cell where a detector is varied. Two design
points matter and should themselves be reported:

- **Combination rule.** Union-of-spans maximises recall — the privacy-relevant direction — at the
  cost of precision, and therefore of utility, because every false positive pseudonymises a token
  that carried meaning. Majority vote trades the other way. Report **union and vote separately**;
  the recall/precision asymmetry between them is exactly the privacy/utility trade-off the paper is
  about, appearing a second time at the detector level.
- **The ensemble is the practical recall ceiling**, and the **gold-span oracle** is the true ceiling.
  The gap between them measures what better detection could still buy; the gap between single
  detectors and the ensemble measures what ensembling already buys. Both belong in the results.

Concretely, axis D should carry at least: Presidio (rule-based), one fine-tuned multilingual NER, two
or more distinct LLMs individually, the ensemble in both union and vote form, and gold spans.

### Measurements

**1. Detection** — P/R/F1 per entity type, reported separately for PERSON and LOCATION since those
carry the stability requirement. Recall is the privacy metric, precision the utility metric.

**2. Stability** — the axis nobody reports:
- **collision rate** — distinct real entities sharing a pseudonym ("person 1 confused with person 2")
- **fragmentation rate** — one real entity receiving several pseudonyms (*Dr. Weber*, *Weber*,
  *F. Weber* → three), which is the more common failure and hurts utility more
- both require coreference-resolved gold, which is why **TAB matters** — it annotates co-reference
  and confidential attributes, not just categories

**3. Utility** — train and evaluate downstream on pseudonymised text, in two regimes:
train-on-pseudonymised/test-on-pseudonymised (deployment) and train-on-original/test-on-pseudonymised
(transfer). Tasks per domain: clinical NER and ICD/OPS coding (BRONCO is annotated for exactly this);
legal outcome classification (TAB/ECHR); e-mail thread/intent classification; plus corpus-level LM
perplexity shift and embedding drift as task-independent proxies.

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
- **A4 LLM re-identification.** Give a modern LLM the pseudonymised document and ask who it is,
  with and without auxiliary context. This is the threat model of 2026 and the one the workshop cares
  about.

### Hypotheses (falsifiable, and the paper is interesting either way)

- **H1** Under a deterministic policy, A2 succeeds regardless of technique — hash and HMAC leak
  comparably. *Consequence: the field optimises the wrong axis.*
- **H2** Detector recall dominates total leakage: a missed name leaks fully whatever the function.
  Measurable by comparing each detector — including the ensemble — against the gold-span oracle.
  If the ensemble closes most of the gap to the oracle, detection ceases to be the bottleneck and
  the policy axis becomes the whole story; if it does not, detection recall is the headline.
- **H3** Document-randomised policy cuts A2/A3 sharply at modest utility cost for tasks that do not
  need cross-document linkage, and catastrophic cost for those that do (patient timelines,
  coreference).
- **H4** Realistic and attribute-matched surrogates buy utility and cost privacy — they preserve
  gender, locale and frequency, which is exactly what A2 and A4 consume.

### Deliverables

Released code, the full factorial results, and the **stability–leakage frontier** per language and
domain — the curve a practitioner actually needs and which currently does not exist. No new corpus,
no new detector: the contribution is the axis nobody varied.

## Open questions

- Is the full A×B×C×D×E factorial affordable, or do we fix a sensible default per axis and vary one
  at a time around it? Compute is available; annotation-limited corpora may not support every cell.
- Which E3C languages carry enough PII density to be worth including?
- **Enron**: use it and make the ethics point explicitly, or exclude it and lose the largest English
  e-mail corpus? See `data/candidates.md`. This must be a stated decision, not a drift.
- Does the **2026 revision of ISO 25237** change any recommendation we would make? Somebody needs a
  copy — it is not open access.
- Ensemble composition: which LLMs, and is the combination rule fixed across languages or tuned per
  language? Tuning per language risks overfitting the benchmark.
