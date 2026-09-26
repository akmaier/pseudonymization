# Corpus candidates

> **⚠ SUPERSEDED — historical record only.**
> **[`experiment_plan.md`](../experiment_plan.md) is the sole authority** (AM, 2026-09-08). Where this file disagrees
> with it, this file is wrong. It is kept because it records how decisions were reached, not because
> anything here is still binding. In particular the **"axis F / identifier provenance"** factor and
> the **T1–T5 tier taxonomy** below were an agent's constructions on top of AM's remark of
> 2026-09-06 — *"PHI inserted is not great. Same for synthetic. Pseudonymised is ok"* — which was a
> **corpus-selection criterion, not a factor**. Both were struck on 2026-09-08. Do not reintroduce
> them, and do not plan from this file.

Everything considered, **including corpora beyond the current plan**, so nothing has to be
rediscovered. Public-data-only is a project decision (AM, 2026-09-06). Access column is the first
thing to check — several are DUA-bound or licensed, and none is committed to this repo.

**Verification pass 2026-09-06.** Rows marked *verified* were checked against the corpus paper,
repository or record page on that date. Everything else remains title-level.

---

## What the corpora do and do not support

Three facts emerged from the verification pass that constrain `experiment_plan.md` and should be settled before
any download.

**1. Only TAB and OntoNotes annotate co-reference.** The stability metrics — collision rate and fragmentation
rate — are functions of the *mapping*, and scoring them needs co-reference-resolved gold: you must
know that *Dr. Weber*, *Weber* and *F. Weber* are one person. TAB annotates `entity_id` co-reference
explicitly. MEDDOCAN, CARDIO:DE, BRONCO150, E3C and MedDeID annotate spans and types only. So
`experiment_plan.md` §2/2 is measurable on **TAB alone**, unless we resolve co-reference ourselves on
the others — which would be a new annotation effort, not a run.

**2. BRONCO150 is sentence-scrambled.** *"The original documents were scrambled at the sentence level
to make reconstruction of individual reports impossible."* There is therefore no document and no
document order in BRONCO. Consequences: the **document-randomised policy level (axis A) is undefined**
on it, cross-document stability cannot be measured, and A3 linkage has no co-occurrence structure to
exploit. BRONCO remains excellent for **utility** — it is normalised to ICD-10 / OPS / ATC, i.e. a
ready-made downstream task — but it cannot carry the stability or linkage axes.

**3. Almost every public corpus is already synthetic or already pseudonymised.** This is the big one.

| corpus | what the identifiers actually are |
|---|---|
| MEDDOCAN | *"a **synthetic** corpus of clinical cases enriched with PHI expressions"* — published SciELO case reports, PHI **inserted** by health documentalists |
| CARDIO:DE | real letters, but PHI already **replaced by semantic placeholders**, dates shifted, ages shifted |
| MedDeID | fully synthetic — *"contain no real patient notes or personal information"* |
| REDACT | fully synthetic, LLM-generated — *"no real personal data. Every identifier is fabricated"* |
| AI4Privacy | synthetic, human-in-the-loop validated |
| CodEAlltag | real donated e-mail, but **already pseudonymised**: spans manually annotated, then automatically substituted with *realistic surrogates* |
| TAB | **real** — ECHR judgments are public records naming real people |
| Enron | **real**, non-consenting, and unremediated |

This matters directly for the leakage attacks. **A1 (dictionary) and A2 (frequency analysis) both
consume the *name-frequency distribution*.** A2 in particular works because, under a deterministic
policy, pseudonym frequency mirrors real-name frequency. Inserted or generated identifiers do not
carry a natural surname distribution, so a successful A2 on MEDDOCAN or REDACT proves less than a
successful A2 on natural text.

**This decided the Enron question (AM, 2026-09-07 — Enron is in): Enron and TAB are the only two
public corpora in the plan with real, naturally distributed personal names.** Excluding Enron would
have left the frequency attack testable on English legal text and essentially nowhere else.

**4. E3C carries no PII annotation at all.** Its layers annotate clinical entities (SNOMED-CT,
ICD-10) and temporal information/factuality — not personal identifiers. E3C can supply multilingual
clinical *text*, but it cannot supply the gold-span oracle level of axis D.

---

## In the plan

### Clinical

| corpus | language | access | note |
|---|---|---|---|
| **MEDDOCAN** | es | **public, CC-BY-4.0** *(verified)* | 1,000 Spanish clinical case studies, **29 entity types**; train 500 / dev 250 / test 250, plus a 3,501-doc background set. BRAT + i2b2 XML. IAA 98 %. PHI is **inserted, not real** (see above). No co-reference. `meddocan.zip`, 11.7 MB, Zenodo `10.5281/zenodo.4279323` |
| **CARDIO:DE** | de | ✅ **on disk 2026-09-08 — AM only**, one agreement per person; the restricted DUA root (`PSEUDONYMKIT_DUA`), mode 700 | `10.1038/s41597-023-02128-9`. **500** German cardiology routine doctor's letters, Heidelberg — but split 400 main / 100 held-out, and **only the 400 carry annotations** (the held-out annotations are retained by Heidelberg for a future shared task). Two-pass de-identification, PHI → semantic placeholders, date shifting, age shifted by random > 300, lab-value outliers removed by z-score. *Paper read.* One of only two distributable German clinical corpora |
| **BRONCO150** | de | **DUA** (Ulf Leser, HU Berlin) *(verified)* | 150 German oncology discharge summaries (HCC / melanoma), Charité + Tübingen. **11,434 sentences, 89,942 tokens, 11,124 entity + 3,118 attribute annotations**; normalised to **ICD-10 / OPS / ATC** → ready-made downstream utility task. **Sentence-scrambled** — see finding 2 |
| **MedDeID** | nl | **public, CC-BY-4.0** *(verified)* | Zenodo `10.5281/zenodo.21992866`. **6,493 synthetic development docs + 300 physician-reviewed benchmark docs**, ProductionLabels_v1 schema, nested sub-annotations on the benchmark, bilingual NL/EN guidelines. 12.0 MB zip, JSONL. Fully synthetic |
| **E3C** | it, en, fr, es, eu (+ el, pl, sk, sl semi-automatic) | **public, via European Language Grid** *(verified)* | European Clinical Case Corpus. Layer 1 ≈ 25 K tokens/language fully manual. Annotates **clinical entities + temporal/factuality — no PII layer** (finding 4) |
| **i2b2 / n2c2** (2006, 2014, 2016) | en | ⛔ **registration CLOSED, "temporarily unavailable"** (portal, 2026-09-07) | The field standard. 2014 set: 1,304 records from 296 diabetic patients (Partners Healthcare RPDR). Now hosted on the DBMI Data Portal, not i2b2.org |

### Legal

| corpus | language | access | note |
|---|---|---|---|
| **TAB / ECHR** | en | **public, MIT licence, direct clone** *(verified)* | 1,268 English ECHR judgments. Annotates semantic category, **identifier type (DIRECT / QUASI / NO_MASK)**, confidential attributes **and co-reference (`entity_id`)**. Standoff JSON with train/dev/test splits and a `quality_checked` flag. **The only corpus that supports the stability metrics** — and one of only two with real names |
| LGPD Benchmark | pt-BR | check | Brazilian legal text, personal-data pseudonymisation |

### E-mail

| corpus | language | access | note |
|---|---|---|---|
| **CodEAlltag** | de | **public, CC-BY-SA-4.0, GitHub** *(verified)* | German e-mail. `CodEAlltag_pS` = **800 pseudonymised donated e-mails**, plain text; `pXL_*` = seven **topical** segments from Usenet (EVENTS, GERMAN = *about the German language*, TEENS, PHILOSOPHY, MOVIES, FINANCE, TRAVELS), ~1.47 M mails, **automatically** pseudonymised, documented gender bias. **Checked 2026-09-06: the release ships NO annotations** — 800 `.txt` files and nothing else. Separate repos add **formality scores** and the authors' MIT-licensed **`privacy_tagger`**. See `metacorpus.md` §5 |
| **Enron** | en | **public, CMU** *(verified)* | ~500 k messages from ~150 mostly senior staff, 1998–2002, released by FERC. `enron_mail_20150507.tar.gz`, **443 MB** (~1.7 GB unpacked). Per-user maildirs → folder-classification task + cross-message identity; ~184-employee org chart as the A3 auxiliary. Redaction was request-driven only. **In, with safeguards** (AM, 2026-09-07) |
| Email-header corpus | en | check | *A Corpus of Email Headers with Personal Privacy Protection* (2017) |
| Avocado (LDC2015T03) | en | **licensed** | ~900 k messages — *not verified* |

### General / synthetic / financial

| corpus | language | access | note |
|---|---|---|---|
| **AI4Privacy** (pii-masking-200k/300k) | 6 langs, 8 jurisdictions | **public on HF; academic use free, commercial licence separate** *(verified)* | 300k = OpenPII-220k + **FinPII-80k** (the financial slice). ~220 k examples, 30.4 M tokens, 27 PII classes (+~20 finance/insurance). Synthetic |
| **REDACT** | 25 langs / 9 scripts | **public, CC-BY-SA-4.0** *(verified)* | `github.com/guneeshvats/REDACT-PII-Benchmark`. 13,427 records, 324,078 annotations, 51 entity types, nine controlled generation axes, GDPR sensitivity tiers. **Fully synthetic, LLM-generated** |
| **PIIBench** | multi | check release *(not verified)* | Ten English sources unified; 2,369,883 sequences, 3.35 M mentions, 48 canonical types. Usable as a source of slices — **repository not located yet** |

---

## Access routes — what to do, and the lead time

**Group 1 — no permission, download today.** Total footprint is small: MEDDOCAN 11.7 MB, MedDeID
12.0 MB, TAB a single JSON. Disk pressure on the cluster is not a constraint for these.

| corpus | route |
|---|---|
| TAB / ECHR | clone `NorskRegnesentral/text-anonymization-benchmark` |
| MEDDOCAN | Zenodo `10.5281/zenodo.4279323` (`meddocan.zip`); guidelines at `10.5281/zenodo.4279338`; scripts at `PlanTL-GOB-ES/SPACCC_MEDDOCAN` |
| MedDeID | Zenodo `10.5281/zenodo.21992866` |
| CodEAlltag | clone the `codealltag` GitHub organisation (`CodEAlltag_pS`, `CodEAlltag_pXL_*`) |
| REDACT | clone `guneeshvats/REDACT-PII-Benchmark` |
| AI4Privacy | HuggingFace `ai4privacy/pii-masking-300k` — academic use; note the commercial clause |
| E3C | European Language Grid, corpus 2.0.0 |
| PIIBench | release location still to be found |
| Enron | public — **blocked on the ethics decision, not on access** |

**Group 2 — applications, and these set the schedule.** Send on the same day; they run in parallel.

| corpus | who / where | what they need | stated lead time |
|---|---|---|---|
| **CARDIO:DE** | `data@uni-heidelberg.de`, approved by study director Christoph Dieterich | signed DUA form + **group description** (name, affiliation, position, institution e-mail and website) + **project description** | **≥ 1 week** |
| **BRONCO150** | Prof. Ulf Leser, HU Berlin | the DUA form from the BRONCO page, signed; academic German clinical NLP use | not stated |
| **i2b2 / n2c2** | DBMI Data Portal, `portal.dbmi.hms.harvard.edu` | account, Rules of Conduct, DUA, **human approval; each user applies individually** | not stated |
| Avocado | LDC licence | institutional LDC membership or purchase | not stated |

---

## Beyond the current plan — recorded, not adopted

| corpus / source | why it might matter |
|---|---|
| Chinese: **CBLUE**, **CCKS-2019**, **Yidu-S4K** | non-Latin script; the OPF evaluation shows detectors collapse on non-Latin (Cyrillic 0.03, Arabic 0.04), so a CJK slice is where H1/H2 would be stressed hardest |
| Korean: HuggingFace `irene93/deidentification-chat-ko` | instruction-style de-identification data |
| Japanese | artifacts gathered in the earlier survey; not yet identified to a named corpus |
| Brazilian Portuguese PHI/PII corpora | |
| Swedish: Dalianis / **Stockholm EPR Corpus** | and *Building a De-identification System for Real Swedish Clinical Text Using Pseudonymised Clinical Text* (2019) |
| Danish / Nordic: Laursen et al. (SDU) | auto-annotated training data for DL de-identification |
| French: **DEFT** shared-task data | |
| Icelandic / Norwegian / Danish **Dynaword** | general-language, for out-of-domain contrast |
| **ASQ-PHI** (`10.1016/j.dib.2026.112586`) | adversarial *synthetic* clinical benchmark — closest thing to the "inject synthetic identifiers" method |
| **SPY** medical benchmark, **Kiji** (non-English) | named in the OPF evaluation; provenance not yet checked |
| **CARMEN-I** (Zenodo, es/en) | anonymisation protocol for clinical reports; surfaced during the 2026-09-06 verification pass, not yet assessed |

---

## Decided — Enron is in (AM, 2026-09-07)

**Enron is included, and the ethics point is made explicitly in the paper.** This closes the repo's
oldest open question. The full reasoning and the five binding safeguards are in `experiment_plan.md`
§"Enron is in — decided, with safeguards"; the short form:

- Excluding it protects nobody — the corpus stays public and the field keeps using it silently.
- It is the only public e-mail corpus with **real names in natural frequency**, **the same people
  recurring across thousands of messages**, **a downstream task**, and **a public auxiliary record**
  to link against. E-mail is a required domain, so exclusion would have meant licensing Avocado
  (LDC2015T03) or having no English e-mail at all.
- The attacks target **our own pseudonyms**, not the corpus, so the marginal disclosure is ~zero.
- Safeguards: no real name published anywhere · no artefact that re-exposes PII · A4 scored against
  the corpus surface form and stratified by public-figure status · the 2020 audit
  (arXiv 2001.10374, 50,000 unreported PII instances) cited and the position stated · one written
  FAU DPO check.

*The most-used public e-mail corpus in the field being an unresolved privacy incident is itself
evidence for this paper's thesis about how the field evaluates privacy.* That is the point the paper
makes, rather than the silence that is standard practice.
