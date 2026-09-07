# BRONCO150 — Data Usage Agreement

**Form:** `bronco_data_usage_agreement_210427.pdf`, from
`www2.informatik.hu-berlin.de/~leser/bronco/` · **Send to:** Prof. Dr. Ulf Leser,
`leser@informatik.hu-berlin.de`, Wissensmanagement für Bioinformatik, Institut für Informatik,
Humboldt-Universität zu Berlin.

The form is three pages; only page 3 has fields. Fill, sign, scan, e-mail with the covering note.

---

## The two clauses, and AM's reading of them (2026-09-07)

Verbatim from the agreement:

> **3.** The Data User agrees that he/she will (i) not attempt to re-build original discharge
> summaries or parts thereof from BRONCO150 and (ii) **not attempt to identify or re-identify
> individual persons, hospitals or doctors from BRONCO150.**

> **8.** The Data User will not disclose, disseminate, or otherwise share BRONCO150 to or with any
> other person or entity, including any subcontractor, for any purpose. BRONCO150 **must not be
> transmitted electronically to other services not under administration of the Data User**, such as
> online translation services.

**AM, 2026-09-07 — both are satisfied, and the study runs in full on this corpus:**

- **Clause 3.** *"De-ID means to find the true identity of the patients. We are not doing that."* Our
  leakage attacks invert **pseudonyms we generate ourselves**; at no point is the true identity of a
  patient, physician or hospital sought or recoverable. The clause prohibits identifying people from
  BRONCO150 — which is not what the attacks do.
- **Clause 8.** *"Our data stays in house. We don't use third party APIs."* Processing runs on the
  lab's own cluster; the LLM endpoint is operated by **NHR@FAU**, the university's own national HPC
  centre, not a commercial online service of the kind the clause names.

So **no cells are licence-blocked on BRONCO** — the earlier note in this file has been superseded.
The purpose text below is written to describe that accurately, because clause 11 binds actual
research activity to the description and a different kind of research needs a new agreement.

What still limits BRONCO is the corpus itself, not the licence: it is **sentence-scrambled**, so
there is no document, which leaves the document-randomised policy level undefined, cross-document
stability unmeasurable and A3 linkage without co-occurrence structure to exploit. It carries the
**utility** axis (ICD-10 / OPS / ATC) and the within-sentence parts of detection and leakage.

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
> taxonomies of ENISA and ISO 25237 — affects the usefulness of clinical text and the residual risk
> it carries. On BRONCO150 we replace annotated entities using different surrogate methods, re-train
> and evaluate ICD-10 / OPS / ATC classification against the unmodified corpus, and measure how well
> each method resists inversion of **the pseudonyms we ourselves generate**. No attempt is made to
> identify or re-identify any patient, physician or hospital. All processing is in-house on
> university infrastructure. Only aggregate figures are published.

*(93 words.)* Written to cover the whole of what we will actually do: clause 11 binds research
activity to this description.

---

## Covering e-mail

> **Subject:** BRONCO150 — Data Usage Agreement, Lehrstuhl für Mustererkennung, FAU Erlangen-Nürnberg
>
> Sehr geehrter Herr Prof. Leser,
>
> anbei die unterschriebene Data Usage Agreement für BRONCO150. Wir untersuchen am Lehrstuhl für
> Mustererkennung der FAU Erlangen-Nürnberg, wie sich die Wahl des Pseudonymisierungsverfahrens und
> der Pseudonymisierungspolitik (Terminologie nach ENISA 2021 und DIN EN ISO 25237) auf Erkennung,
> Nutzbarkeit und Restrisiko klinischer Texte auswirkt. BRONCO150 setzen wir für die
> ICD-10-/OPS-/ATC-Klassifikation auf pseudonymisiertem gegenüber unverändertem Text ein sowie für
> die Frage, wie gut die jeweiligen Verfahren die **von uns selbst erzeugten** Pseudonyme schützen.
>
> Zur Klarstellung im Sinne von Ziffer 3 und Ziffer 8: Es wird zu keinem Zeitpunkt versucht,
> Patientinnen, Patienten, Ärztinnen, Ärzte oder Kliniken zu identifizieren; untersucht werden
> ausschließlich die von uns generierten Pseudonyme. Die Verarbeitung erfolgt vollständig auf
> lehrstuhleigener bzw. universitärer Infrastruktur; kommerzielle oder externe Online-Dienste werden
> nicht genutzt.
>
> Eine organisatorische Rückfrage zu Ziffer 2: Ich beantrage den Zugang als Lehrstuhlinhaber für die
> Arbeit meiner Gruppe. Sind Mitarbeitende, die unter meiner Verantwortung und auf der genannten
> Infrastruktur arbeiten, durch meine Unterschrift abgedeckt, oder benötigt jede Person eine eigene
> unterzeichnete Vereinbarung? Im letzteren Fall reichen wir diese gerne nach.
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
