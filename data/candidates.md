# Corpus candidates

Everything considered, **including corpora beyond the current plan**, so nothing has to be
rediscovered. Public-data-only is a project decision (AM, 2026-09-06). Access column is the first
thing to check — several are DUA-bound or licensed, and none is committed to this repo.

## In the plan

### Clinical

| corpus | language | access | note |
|---|---|---|---|
| **CARDIO:DE** | de | distributable | `10.1038/s41597-023-02128-9`. German **cardiology routine doctor's letters**. Two-pass de-identification, PHI → semantic placeholders, date shifting, age shifted by random > 300, lab-value outliers removed by z-score. *Paper read.* One of only two distributable German clinical corpora |
| **BRONCO150** | de | **DUA** (Ulf Leser, HU Berlin) | 150 German oncology discharge summaries, Charité + Tübingen; scrambled sentences, manually anonymised with both DPOs' approval; annotated to ICD10 / OPS / ATC → **ready-made downstream utility task**. *DUA read* |
| **MEDDOCAN** | es | public | the Spanish clinical de-identification shared task: corpus, guidelines, evaluation |
| **i2b2 / n2c2** (2006, 2014, 2016) | en | licensed, registration | the field standard; every paper benchmarks against it |
| **E3C** | en, it, el, pl, sk, sl | public | European Clinical Case Corpus; train splits held for six languages |
| **MedDeID** | nl | public (Zenodo) | `10.5281/zenodo.21992866`, Aug 2026: 6,493 synthetic docs + 300-doc physician-reviewed benchmark + bilingual guidelines |

### Legal

| corpus | language | access | note |
|---|---|---|---|
| **TAB / ECHR** | en | public | 1,268 European Court of Human Rights judgments. **Annotates co-reference and confidential attributes** — the only resource that supports the stability metrics in `PLAN.md` |
| LGPD Benchmark | pt-BR | check | Brazilian legal text, personal-data pseudonymisation |

### E-mail

| corpus | language | access | note |
|---|---|---|---|
| **CodEAlltag** | de | check | German e-mail corpus built for **forensic linguistics** (2016). The corpus of the R19-1030 pseudonymisation baseline |
| **Enron** | en | public | ~500k messages. **See the open question below before using** |
| Email-header corpus | en | check | *A Corpus of Email Headers with Personal Privacy Protection* (2017) |
| Avocado (LDC2015T03) | en | **licensed** | ~900k messages — *not verified* |

### General / synthetic / financial

| corpus | language | access | note |
|---|---|---|---|
| **AI4Privacy** (pii-masking-200k/300k) | multi | public | synthetic multilingual PII; used as a benchmark by the OPF evaluation |
| **PIIBench** | multi | public | ten corpora unified, 48 canonical types — usable as a *source of slices*, including a **financial** one |
| **REDACT** | 25 langs | public | 51 entity types, nine controlled generation axes |

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

## Open question — Enron

*The Enron Corpus: Where the Email Bodies are Buried?* (arXiv 2001.10374, 2020) reports **50,000
previously unreported instances of exposed PII** in the corpus. It is the field's most-used public
e-mail dataset, contains real data about non-consenting individuals, and is cited routinely without
comment.

Two defensible positions, and the paper must pick one **explicitly**:

1. **Use it and say so** — the most-used public e-mail corpus being an unresolved privacy incident is
   itself evidence for the paper's thesis about how the field evaluates privacy.
2. **Exclude it** — and lose the largest English e-mail corpus, with the exclusion stated as a
   finding rather than a gap.

Drifting into silent use is the one option that is not available at a trustworthy-ML venue.
