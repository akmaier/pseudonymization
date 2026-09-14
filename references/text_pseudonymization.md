# References — text de-identification / pseudonymisation

Retrieved from Crossref, arXiv and ACL Anthology, 2026-09-05/06. Abstracts were read where the
entry says so; the rest are **title-level evidence** and must be opened before being relied on.

## Detection benchmarks — crowded, do not add to this

| year | id | work | note |
|---|---|---|---|
| 2026 | arXiv **2606.19881** | **REDACT: A Systematically Controlled Multilingual Benchmark for Personal Information Detection** | *abstract read.* 25 languages / 9 scripts, 13,427 records, 324,078 annotations, 51 entity types; nine controlled axes incl. **domain**; five detectors (Presidio, GLiNER, OpenAI Privacy Filter, GPT-4.1, Claude Sonnet 4.6); GDPR sensitivity tiers. Rule-based recall **0.07** on HIGH-sensitivity |
| 2026 | arXiv **2604.15776** | **PIIBench: A Unified Multi-Source Benchmark Corpus for PII Detection** | *abstract read.* Ten corpora unified; 2.37M sequences, 3.35M mentions, 48 canonical types; 80+ label variants normalised; eight systems |
| 2026 | arXiv **2608.02616** | **OpenAI Privacy Filter: A Cross-Lingual, Cross-Domain PII Evaluation Across 32 Benchmarks** | *abstract read.* 14 languages, 5 domains. **Person names F1 0.40**, addresses 0.49 vs e-mail 0.78, phone 0.76; collapses on non-Latin scripts (Arabic 0.04, Cyrillic 0.03) |
| 2026 | LREC / arXiv 2603.08879 | **MultiGraSCCo: A Multilingual Anonymization Benchmark with Annotations of Personal Identifiers** | *abstract read.* Ten languages, clinical, built by annotation-preserving machine translation with culturally adapted names; 2,500+ annotations |
| 2025 | arXiv 2510.07551 | RECAP — hybrid regex + LLM PII detection, 13 low-resource locales, 300+ entity types | *abstract read* |
| 2026 | arXiv 2605.09973 | GLiNER2-PII: a multilingual model for PII extraction | |
| 2020 | `10.1148/ryai.2020190137` | Evaluation of Automated Public De-Identification Tools on a Corpus of Radiology Reports | Radiology: AI |

## The anonymisation benchmark that is not clinical

| year | id | work |
|---|---|---|
| 2022 | `10.1162/coli_a_00458` / arXiv 2202.00443 | **TAB — The Text Anonymization Benchmark**. **read in full 2026-09-14** (see below). 1,268 **ECHR court cases**; annotates semantic category, identifier type, confidential attributes **and co-reference**, and marks which spans must be masked *to conceal identity* rather than to hit a category. The only resource supporting our **stability** metrics |
| 2025 | `10.21203/rs.3.rs-8309951/v1` | LGPD Benchmark — Brazilian **legal** text, personal-data pseudonymisation |

## Surrogate generation — thin

| year | id | work |
|---|---|---|
| 2022 | arXiv 2210.16125 | **BRATsynthetic**: text de-identification using a Markov chain replacement strategy for surrogate personal identifiers. *abstract read 2026-09-14.* Compares **Consistent**, **Random** and **Markov** replacement; reports document-level PHI leakage falling from 27.1 % to 0.1 % at 0.1 % FNER, and 94.2 % to 57.7 % at 5 % FNER, on the UAB corpus. This is the **policy axis measured under detector error** (HIPS), not cross-document linkage — adjacent to our axis B, not the same question |
| 2025 | `10.3390/electronics14193945` | A Markov Chain Replacement Strategy for Surrogate Identifiers: **Minimizing Re-Identification Risk** (journal version) |
| 2020 | `10.18653/v1/2020.clinicalnlp-1.23` | **PHICON** — improving generalisation of de-identification models via PHI substitution / data augmentation |
| 2026 | `10.1016/j.dib.2026.112586` | **ASQ-PHI** — adversarial *synthetic* benchmark for clinical de-identification and search utility |
| 2015 | Springer, *Medical Data Privacy Handbook* | **Stubbs, Uzuner, Kotfila, Goldstein & Szolovits — Challenges in synthesizing surrogate PHI in narrative EMRs.** **Title-level only — not opened.** Citation taken verbatim from Eder et al. (2019)'s bibliography, which treats it as the reference point for surrogate generation (letter-to-letter mappings per document, restrictions on character selection). The one obvious hole in this list |

## Evaluating anonymisation — criteria and information loss

| year | id | work |
|---|---|---|
| 2021 | arXiv **2103.09263** | **No Intruder, no Validity: Evaluation Criteria for Privacy-Preserving Text Anonymization.** *abstract read.* Proposes **TILD** — **T**echnical performance, **I**nformation **L**oss, and human ability to **D**e-anonymise. The direct precedent for this study's evaluation design, and independent support for the trained-attacker stance: an anonymisation evaluation without an adversary is not an evaluation |
| 2024 | ACL, arXiv **2401.16475** | **InfoLossQA: Characterizing and Recovering Information Loss in Text Simplification.** *abstract read.* Measures information loss as **question–answer pairs** answerable from the original but not the transformed text. The method AM proposed as a surrogate task — but applied to **simplification**, not anonymisation. Applying it to pseudonymisation appears to be open |
| 2026 | arXiv 2511.15364 | Anonymization and Information Loss — *title-level* |

## Utility after de-identification

| year | id | work |
|---|---|---|
| 2022 | `10.18653/v1/2022.bionlp-1.38` | **Utility Preservation of Clinical Text After De-Identification** |
| 2020 | `10.18653/v1/2020.louhi-1.1` | The Impact of De-identification on Downstream **Named Entity Recognition** in Clinical Text |
| 2024 | `10.18653/v1/2024.privatenlp-1.13` | **Cloaked Classifiers**: pseudonymization strategies on sensitive classification tasks |
| 2024 | `10.1038/s41598-024-81170-y` | De-identification is not enough: de-identified vs **synthetic** clinical notes |

## Leakage / risk / attacks

| year | id | work |
|---|---|---|
| 2024 | arXiv 2410.01648 | **DeIDClinic** — a risk-aware pseudonymisation framework for clinical text |
| 2019 | arXiv 1901.10583 | **Automatic end-to-end De-identification: Is high accuracy the only metric?** — the thesis precedent; cite, don't hide |
| 2026 | arXiv 2601.12407 | De-Anonymization at Scale via Tournament-Style Attribution |
| 2026 | arXiv 2602.20580 | Personal Information Parroting in Language Models |
| 2025 | arXiv 2512.03310 | Randomized Masked Finetuning — mitigating PII memorisation in LLMs |
| 2026 | arXiv 2608.21727 | Reinforcement Learning on Benign Facts Amplifies Leakage of Memorized Private Data |

## E-mail domain

| year | id | work |
|---|---|---|
| 2019 | ACL Anthology **R19-1030** | Eder, Krieg-Holz & Hahn. **De-Identification of Emails: Pseudonymizing Privacy-Sensitive Data in a German Email Corpus.** **read in full 2026-09-14** (see below). Two steps — detect privacy-bearing entities, then replace with *"synthetically generated surrogates (e.g. a person originally named 'John Doe' is renamed as 'Bill Powers')"* — with "a system architecture for surrogate generation", evaluated on **CodEAlltag**. **Our direct baseline** |
| 2020 | arXiv 2001.10374 | **The Enron Corpus: Where the Email Bodies are Buried?** *abstract read.* Reports **50,000 previously unreported instances of exposed PII** in Enron |
| 2017 | `10.18178/jacn.2017.5.2.240` | A Corpus of Email Headers with Personal Privacy Protection |

## Reviews and scoping

| year | id | work |
|---|---|---|
| 2026 | `10.3390/j9030022` | Clinical Text De-Identification **Beyond PHI Detection**: A Scoping Review — start here for the gap map |
| 2026 | `10.1186/s13326-026-00362-9` | Towards reliable **Spanish** clinical text de-identification |
| 2026 | `10.63317/2xrg7fmndfhy` | **Differentially Private** De-identification of **Dutch** Clinical Notes |
| 2026 | `10.18653/v1/2026.bionlp-1.11` | Post Hoc Agentic Refinement for Multilingual Clinical Text De-identification |
| 2026 | `10.1016/j.jeph.2026.203495` | Performance of pseudonymisation methods applied to hospital documents |

---

## What the two full-text sources actually specify for surrogate rendering

Both opened 2026-09-14. This section records what the papers say, not what this study will do.

### Eder, Krieg-Holz & Hahn (2019) — the only end-to-end surrogate system for German

Category set: a hierarchy under **SocialActor** (ORG, PERSON → FAMILY / GIVEN → FEMALE, MALE;
USER), **Date**, **FormalIdentifier** (PASS, UFID), **Location** (STREET, STREETNO, CITY, ZIP) and
**Address** (EMAIL, PHONE incl. fax, URL).

- **Identifier-like categories are randomised within character class.** EMAIL, PHONE/fax, URL, PASS,
  UFID, USER and ZIP share one rule: every digit is replaced by a random digit, every alphabetic
  character by a random letter of the same case and alphabet, and other characters such as `@` and
  punctuation are left as they are. For URLs the subdomain `www` and the schemes `http`, `https`,
  `ftp`, `file`, `mailto` are preserved. They note that, unlike Stubbs et al. (2015b), they imposed
  no further restriction on character selection, so surrogates "may have an unrealistic appearance".
- **Dates are shifted, not removed and not left alone.** A time shift is drawn **separately for each
  text**, up to 365 days forward or backward, which preserves ordering inside a document while
  breaking it across documents. Language-specific date formats are preserved; month names are
  swapped for month names, keeping standard-variety distinctions (*Januar* vs Austrian *Jänner*) and
  abbreviations (*Jan.*).
- **Ages and professions are deliberately excluded**, on the stated grounds that their use case is
  less sensitive and that ages and professions occur far more often in clinical reports than in
  email. Unspecific dates (*Christmas*, *next week*) and generic geography (landmarks, rivers, lakes)
  are also left untagged, as contributing little to re-identification.
- **Gender is preserved by construction** — FEMALE and MALE are separate leaf categories with
  separate name lists, extracted with their nicknames.
- **Grammaticality is treated as a measurable outcome, not an assumption.** Human annotators score
  each pseudonymised email 1–5 on grammaticality — defined as agreement in *number, gender and case*
  between the surrogate and the constituents around it — and separately on semantic acceptability.
  German genitive inflection is handled via spaCy for GIVEN, FAMILY, CITY and ORG.
- **Where grammaticality and privacy conflict, they chose privacy**: lacking gender- and
  number-specific CITY repositories, they say they would rather tolerate mistakes than a potential
  information leak.
- Surrogate selection is by per-document **letter-to-letter mapping** (after Stubbs et al. 2015b),
  optionally constrained so first letters map to letters of similar frequency, to avoid mapping a
  common initial onto a rare one.
- Coreference is maintained by replacing repeated mentions with the same surrogate, across case
  variants and a language-specific normalised form. Misspellings are deliberately **not** matched:
  Levenshtein matching would merge genuinely different names (*Lena* / *Lina*).

### Pilán et al. (2022) — TAB defines the categories but does not render them

Verbatim category definitions, which are the source of the harmonised taxonomy:

- **CODE** — numbers and identification codes, such as social security numbers, phone numbers,
  passport numbers or license plates.
- **DEM** — demographic attributes of a person, such as native language, descent, heritage,
  ethnicity, **job titles, ranks, education, physical descriptions, diagnosis, birthmarks, ages**.
- **DATETIME** — a specific date, time or duration.
- **QUANTITY** — a meaningful quantity, e.g. percentages or monetary values.
- **MISC** — every other type of personal information associated with an individual.

Two consequences worth recording:

1. **DEM is far wider than proper nouns.** TAB states the inventory is not restricted to proper
   nouns and that demographic entities are often common nouns or adjectives. Its inclusion of
   *diagnosis* means the category is not comparable across our corpora: CARDIO:DE's annotation
   contributes only TITLE and SALUTE to DEMOGRAPHIC, OntoNotes only NORP, Enron nothing.
2. **TAB performs no replacement.** Spans marked as direct or quasi-identifiers are replaced by `*`.
   The paper states that current methods are "typically limited to term suppression or, at most, to
   replacing sensitive terms by their semantic categories (such as replacing \"John Doe\" with
   \"[PERSON]\")" — i.e. this study's condition C — and lists privacy-preserving replacement as
   **future work**, noting that many replacement combinations are equally valid for privacy but
   differ in utility.
