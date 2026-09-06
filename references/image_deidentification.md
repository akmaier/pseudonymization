# References — image de-identification (X-ray, MRI, CT, DICOM)

Collected for the **companion paper** on defacing and re-identification, which is not the subject of
`PLAN.md`. Kept here so the ground is not lost. Retrieved 2026-09-05/06; abstracts were **not**
retrievable from Crossref or PubMed for several of the CT entries, which are marked.

## The group's own anchor — chest X-ray

| year | id | work |
|---|---|---|
| 2022 | **`10.1038/s41598-022-19045-3`** | **Deep learning-based patient re-identification is able to exploit the biometric nature of medical chest X-ray data** — *Packhäuser, Gündel, Münster, Syben, Christlein, **Maier***, Scientific Reports. *Authors verified via Crossref.* The paper AM cited in the thread as the reason defacing is insufficient once deep learning is in play. Chest radiographs are biometrically identifying |
| 2024 | `10.1109/sibgrapi62404.2024.10716264` | Graph Feature Embeddings for Patient Re-Identification from Chest X-Ray Images |

## Defacing does not prevent re-identification — MRI, and this is settled

| year | id | work |
|---|---|---|
| 2020 | `10.1056/nejmc1915674` | **Identification from MRI with Face-Recognition Software** — NEJM. The origin point |
| 2025 | `10.1016/j.compbiomed.2025.111112` | Pitfalls of defacing whole-head MRI: **re-identification risk with diffusion models** and compromised research potential |
| 2026 | `10.1109/isbi61048.2026.11516026` | **Beyond the Mask: The Illusion of Privacy in Defaced Brain MRI** — ISBI |

## CT — thin, and one entry may pre-empt the companion paper

| year | id | work |
|---|---|---|
| 2020 | `10.1148/radiol.2020192617` | **Facial De-identification of Head CT Scans** — Radiology. *abstract not retrievable* |
| 2026 | `10.1007/s10278-026-01858-7` | **De-identification Strategy and Re-identification Risks for Facial Computed Tomography Images via Deep Learning** — J Imaging Informatics in Medicine. ⚠ **from the title this may already be the companion paper. Open it before starting.** *abstract not retrievable from Crossref or PubMed* |
| 2025 | `10.2139/ssrn.5203533` | the SSRN preprint of the above, for **Head** CT |

Supporting the CT threat model: forensic **facial soft-tissue-thickness reconstruction from CT** is
a mature field — `10.4103/jfsm.jfsm_35_23` (2025), `10.4103/jomfp.jomfp_20_19` (2019),
`10.5958/0974-0848.2019.00078.2` (2019). CT arguably makes the attacker's job easier than MRI:
surface rendering is routine and the skull is directly imaged.

## Defacing tools, quality control and the cost to analysis

| year | id | work |
|---|---|---|
| 2026 | `10.1186/s12880-026-02207-4` | DefaceQA — automated quality assessment of brain MRI defacing software |
| 2024 | `10.1007/s10334-024-01170-x` | PyFaceWipe — a defacing tool for almost any MRI contrast |
| 2024 | `10.3233/shti240493` | Quality Assessment of Brain MRI Defacing Using Machine Learning |
| 2022 | `10.1016/j.compbiomed.2022.106211` | Application of a CNN to the quality control of MRI defacing — *abstract read*; motivated by 235,000 clinical-trial scans |
| 2021 | `10.3389/fpsyt.2021.617997` | **Multisite Comparison of MRI Defacing Software Across Multiple Cohorts** |
| 2023 | `10.1117/1.jmi.10.6.064001` | Reproducibility evaluation of the effects of MRI defacing on brain segmentation |
| 2022 | `10.1117/12.2613175` | Effects of defacing whole head MRI on neuroanalysis |
| 2024 | `10.1101/2024.10.11.617777` | Defacing **biases** visual quality assessments of structural MRI |
| 2025 | `10.1101/2025.03.11.642561` | Effect of MRI Defacing on EEG Forward and Inverse Modeling |

## DICOM level — metadata and pixel data

| year | id | work |
|---|---|---|
| 2021 | `10.1038/s41597-021-00967-y` | A DICOM dataset for evaluation of medical image de-identification — Scientific Data |
| 2025 | `10.3233/shti251411` | An Open Data and Methods Framework for Comparative Evaluation of DICOM De-Identification Tools |
| 2025 | `10.3233/shti250978` | DICOM PII De-Identification and Reversible Data Hiding |

DICOM PS3.15 Annex E (Basic Application Level Confidentiality Profile) is the governing standard for
image de-identification — *not verified here*.
