# BRONCO150 — Data Usage Agreement

**Form:** `bronco_data_usage_agreement_210427.pdf`, from
`www2.informatik.hu-berlin.de/~leser/bronco/` · **Send to:** Prof. Dr. Ulf Leser,
`leser@informatik.hu-berlin.de`, Wissensmanagement für Bioinformatik, Institut für Informatik,
Humboldt-Universität zu Berlin.

The form is three pages; only page 3 has fields. Fill, sign, scan, e-mail with the covering note.

---

## ⚠ Read before signing — two clauses constrain the study

Verbatim from the agreement:

> **3.** The Data User agrees that he/she will (i) not attempt to re-build original discharge
> summaries or parts thereof from BRONCO150 and (ii) **not attempt to identify or re-identify
> individual persons, hospitals or doctors from BRONCO150.**

> **8.** The Data User will not disclose, disseminate, or otherwise share BRONCO150 to or with any
> other person or entity, including any subcontractor, for any purpose. BRONCO150 **must not be
> transmitted electronically to other services not under administration of the Data User**, such as
> online translation services.

**What this costs us on BRONCO:**

| axis | effect |
|---|---|
| Utility (§Measurements 3) | ✅ unaffected — ICD-10 / OPS / ATC coding is exactly what the corpus is for |
| Detection, rule-based and local NER (axis D) | ✅ runs locally, unaffected |
| **LLM detectors + ensemble (axis D)** | ❌ clause 8 — the NHR@FAU gateway is an external service |
| **Leakage A1–A4 (§Measurements 4)** | ❌ clause 3 — these are re-identification procedures |
| Stability (§Measurements 2) | already unavailable: BRONCO is sentence-scrambled |

BRONCO therefore enters the study as a **utility corpus**, which is coherent — it is T3 provenance
(placeholder-masked) and sentence-scrambled, so it was never going to carry leakage or stability.

**Two questions to put to Prof. Leser in the covering mail**, rather than deciding them ourselves:

1. Whether clause 3 is engaged when the attack targets **pseudonyms we generate ourselves** and no
   attempt is made to recover anything about a real person.
2. Whether clause 8 permits processing via a **university-operated** LLM endpoint (NHR@FAU, the
   national HPC centre), which is not a commercial third party but is also not under our own
   administration.

Until he answers, assume **no** to both.

---

## Page 3 — fields

```
Name:         Prof. Dr.-Ing. Andreas Maier
Affiliation:  Friedrich-Alexander-Universität Erlangen-Nürnberg,
              Pattern Recognition Lab, Department of Computer Science
Position:     Professor, Head of the Pattern Recognition Lab
Email:        andreas.maier@fau.de
```

## Research purpose (the form allows < 100 words)

> We study how the choice of pseudonymisation function and policy — the technique and policy
> taxonomies of ENISA and ISO 25237 — affects the usefulness of clinical text. BRONCO150 will be used
> **solely to measure downstream task performance**: we replace the annotated entities using
> different surrogate-generation methods and then re-train and evaluate ICD-10 / OPS / ATC
> classification on the resulting text, against the unmodified corpus as baseline. No attempt will be
> made to identify or re-identify any person, hospital or physician, and no BRONCO150 text will be
> transmitted to any external service. Only aggregate performance figures will be published.

*(94 words.)* It is written narrowly on purpose: clause 11 binds actual research activity to this
description, and a different kind of research requires a new agreement.

---

## Covering e-mail

> **Subject:** BRONCO150 — Data Usage Agreement, Pattern Recognition Lab, FAU Erlangen-Nürnberg
>
> Sehr geehrter Herr Prof. Leser,
>
> anbei die unterschriebene Data Usage Agreement für BRONCO150. Wir untersuchen an der FAU
> Erlangen-Nürnberg, wie sich die Wahl des Pseudonymisierungsverfahrens und der Pseudonymisierungs-
> politik (Terminologie nach ENISA und ISO 25237) auf die Verwendbarkeit klinischer Texte auswirkt.
> BRONCO150 möchten wir ausschließlich für die Messung nachgelagerter Aufgaben verwenden — die
> ICD-10-/OPS-/ATC-Klassifikation auf pseudonymisiertem gegenüber unverändertem Text.
>
> Zwei Punkte möchten wir vorab klären, um Ziffer 3 und Ziffer 8 nicht zu verletzen:
>
> 1. Unsere Studie umfasst grundsätzlich auch Angriffe auf die *von uns selbst erzeugten* Pseudonyme
>    (Wörterbuch- und Frequenzanalyse), um zu messen, wie gut ein Verfahren schützt. Auf BRONCO150
>    würden wir darauf verzichten, sofern Sie dies unter Ziffer 3 fassen. Wir bitten um Ihre
>    Einschätzung.
> 2. Für andere Korpora nutzen wir einen LLM-Endpunkt des NHR@FAU (universitär betrieben, kein
>    kommerzieller Dienst). Wir gehen davon aus, dass dies unter Ziffer 8 fällt, und würden
>    BRONCO150 daher **nicht** über diesen Endpunkt verarbeiten. Auch hier wären wir für eine
>    Klarstellung dankbar.
>
> Ohne Ihre Rückmeldung behandeln wir beide Punkte als untersagt.
>
> Mit freundlichen Grüßen
> Andreas Maier

---

## Obligations created by signing

- **Delete after twelve months** and inform Prof. Leser that deletion has happened (clause 5).
- **Single copy**, on machines under AM's own administration, protected from access by anyone who has
  not signed (clause 4) → **not** `/cluster/shared_dataset`.
- **Every additional user signs their own agreement** (clause 2).
- **Cite** Kittner, Lamping, Rieke, Götze, Bajwa, Jelas, Rüter, Hautow, Sänger, Habibi, Zettwitz,
  de Bortoli, Ostermann, Ševa, Starlinger, Kohlbacher, Malek, Keilholz, Leser (2021), *"Annotation
  and initial evaluation of a large annotated German oncological corpus"*, JAMIA Open 4(2), ooab025
  (clause 13).
- Non-commercial research only, within a certified research organisation (clause 1).
