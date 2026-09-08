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
| 2022 | `10.1162/coli_a_00458` / arXiv 2202.00443 | **TAB — The Text Anonymization Benchmark**. *abstract read.* 1,268 **ECHR court cases**; annotates semantic category, identifier type, confidential attributes **and co-reference**, and marks which spans must be masked *to conceal identity* rather than to hit a category. The only resource supporting our **stability** metrics |
| 2025 | `10.21203/rs.3.rs-8309951/v1` | LGPD Benchmark — Brazilian **legal** text, personal-data pseudonymisation |

## Surrogate generation — thin

| year | id | work |
|---|---|---|
| 2022 | arXiv 2210.16125 | **BRATsynthetic**: text de-identification using a Markov chain replacement strategy for surrogate personal identifiers |
| 2025 | `10.3390/electronics14193945` | A Markov Chain Replacement Strategy for Surrogate Identifiers: **Minimizing Re-Identification Risk** (journal version) |
| 2020 | `10.18653/v1/2020.clinicalnlp-1.23` | **PHICON** — improving generalisation of de-identification models via PHI substitution / data augmentation |
| 2026 | `10.1016/j.dib.2026.112586` | **ASQ-PHI** — adversarial *synthetic* benchmark for clinical de-identification and search utility |

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
| 2019 | ACL Anthology **R19-1030** | **De-Identification of Emails: Pseudonymizing Privacy-Sensitive Data in a German Email Corpus.** *abstract read.* Two steps — detect privacy-bearing entities, then replace with *"synthetically generated surrogates (e.g. a person originally named 'John Doe' is renamed as 'Bill Powers')"* — with "a system architecture for surrogate generation", evaluated on **CodEAlltag**. **Our direct baseline** |
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
