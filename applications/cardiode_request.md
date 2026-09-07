# CARDIO:DE — data request

**Send to: `christoph.dieterich@uni-heidelberg.de`** — the study director, directly. *(Correction: an
earlier note in this repo said `data@uni-heidelberg.de`; the heiDATA terms of use say the request
goes to the study director.)*

**Agreement:** *CARDIO.de Data Transfer Agreement*, `DUA_en.pdf`, 4 pages — downloaded 2026-09-07,
MD5 `9b3f59448c6360573fe2d24463c69c08`, verified. Local copy: `~/Downloads/DUA_en.pdf`.

**Stated lead time:** at least one week. **Term: 5 years** from signature (clause 8.1).

Parties: University Hospital Heidelberg AdöR, executing institution Medical Clinic — Internal
Medicine III, project manager Prof. Dr. rer. nat. Christoph Dieterich.

---

## What the terms of use require, verbatim

> **The corpus must be formally requested following three steps:** 1. Sending a data request mail to
> the study director (christoph.dieterich@uni-heidelberg.de) including a signed DUA … 2. including a
> group description and a project description … 3. After a positive decision … the data requestor
> will receive detailed instructions how to download the corpus via heiDATA.
>
> The data request needs to contain the following information: 1. A signed DUA, **signed by each data
> user individually**. 2. A group description including the requestor's (data user's) name,
> affiliation, position and email address and website of the institution. 3. A project description of
> the research purpose (**max. 150 words**). 4. **Name, affiliation, position, email address and
> signature of the responsible person to administer and manage the infrastructure on which CARDIO:de
> will be stored.**

## Clauses that matter for our design

| clause | text | effect on us |
|---|---|---|
| **1.2** | *"Access to data is granted to individual Recipients only. Any Recipients or User must fill out this data usage agreement individually."* | **each lab member who processes the data signs their own copy** — see below |
| **1.4** | *"Under no circumstances may the Recipient attempt to identify specific individuals **based on the Data received**."* | ✅ satisfied — we attack pseudonyms **we generate**, never the identity of a patient |
| **2.2** | no disclosure to third parties without prior written consent | ✅ satisfied — processing is in-house on FAU infrastructure |
| **3.3** | Heidelberg may request a copy of derived data/variables | keep derived artefacts retrievable |
| **4.1** | publication permitted; must cite the CARDIO:DE publication | — |
| **6.3** | on completion, all Data returned or deleted per instruction; a further project needs a **new application** | scope the project description to cover the whole study |
| **8.1** | term **5 years**, extendable | far more generous than BRONCO's 12 months |

Clause 1.4 is narrower than BRONCO's equivalent — it prohibits identifying *specific individuals
based on the Data*, which is exactly the thing we are not doing.

---

## Page 4 — Recipient (data user)

```
Name:         Prof. Dr.-Ing. Andreas Maier
Affiliation:  Friedrich-Alexander-Universität Erlangen-Nürnberg,
              Pattern Recognition Lab, Department of Computer Science
Position:     Professor, Head of the Pattern Recognition Lab
Email:        andreas.maier@fau.de
Website:      lme.tf.fau.de
Date:         ____________
```

**Group description:**

> The Pattern Recognition Lab at Friedrich-Alexander-Universität Erlangen-Nürnberg is a research group
> in the Department of Computer Science, headed by Prof. Dr.-Ing. Andreas Maier, working on machine
> learning and pattern recognition for medical data — medical imaging, clinical text and speech. The
> lab hosts approximately [N] researchers and doctoral candidates. Data are processed exclusively on
> the lab's own compute cluster, administered within the group.

## Project description (max. 150 words)

> We evaluate text pseudonymisation end to end: detection, utility and residual risk. Research on
> clinical de-identification varies the *detector* and holds the replacement step fixed; we invert
> that and treat the **pseudonymisation function and policy** as the independent variable, using the
> technique and policy taxonomies of ENISA (2021) and DIN EN ISO 25237 — deterministic,
> document-randomised and fully randomised policies, crossed with counter, mapping table, hash, HMAC
> and symmetric encryption, and three surrogate forms.
>
> CARDIO:DE serves the **utility** measurement in German. Using its medication-information and
> section-class annotation layers as downstream tasks, we compare task performance on pseudonymised
> against unmodified text, in two regimes. No attempt is made to identify any individual; the study
> operates on surrogates we generate ourselves. Processing is in-house on FAU infrastructure. Only
> aggregate figures are published, and no corpus text is redistributed.

*(146 words.)*

## Responsible person for the infrastructure

```
Name:         ____________   ← AM: yourself, or the i5 cluster administrator?
Affiliation:  Friedrich-Alexander-Universität Erlangen-Nürnberg, Pattern Recognition Lab
Position:     ____________
Email:        ____________
Date:         ____________
Signature:    ____________
```

**Decide this before sending.** The form says *"e.g. research unit leader"*, so AM signing both blocks
is normal — but if the lab cluster is administered by i5 IT rather than the lab, name that person.

---

## Covering e-mail

> **Subject:** CARDIO:DE data request — Pattern Recognition Lab, FAU Erlangen-Nürnberg
>
> Sehr geehrter Herr Prof. Dieterich,
>
> hiermit beantrage ich Zugang zu CARDIO:DE. Anbei die unterschriebene Data Transfer Agreement mit
> Gruppen- und Projektbeschreibung sowie den Angaben zur verantwortlichen Person für die
> Infrastruktur.
>
> Wir untersuchen am Lehrstuhl für Mustererkennung der FAU Erlangen-Nürnberg, wie sich Verfahren und
> Politik der Pseudonymisierung (Terminologie nach ENISA 2021 und DIN EN ISO 25237) auf Erkennung,
> Nutzbarkeit und Restrisiko von Texten auswirken. CARDIO:DE möchten wir für die Nutzbarkeitsmessung
> im Deutschen einsetzen: Medikationsextraktion und Abschnittsklassifikation auf pseudonymisiertem
> gegenüber unverändertem Text. Die Verarbeitung erfolgt ausschließlich auf dem lehrstuhleigenen
> Rechencluster; eine Weitergabe an Dritte findet nicht statt. Ein Versuch, Personen zu
> identifizieren, ist nicht Gegenstand der Studie — untersucht werden ausschließlich die von uns
> selbst erzeugten Pseudonyme.
>
> Eine organisatorische Rückfrage zu Ziffer 1.2: Ich beantrage den Zugang als Leiter des Lehrstuhls
> für die Arbeit meiner Gruppe. Sind Mitarbeitende, die unter meiner Verantwortung und auf der
> genannten Infrastruktur arbeiten, durch meine Unterschrift abgedeckt, oder benötigt jede Person
> eine eigene unterzeichnete Vereinbarung? Im letzteren Fall reichen wir die weiteren Vereinbarungen
> gerne nach.
>
> Mit freundlichen Grüßen
> Andreas Maier

---

## Corpus contents (heiDATA, V1.1.2, 2026-09-07)

500 German cardiology routine doctor's letters, Heidelberg University Hospital, manually
de-identified, **temporal information deliberately preserved**.

- **medication information** — ActiveIng, Dosage, Drug, Duration, Form, Frequency, Reason, Route,
  Strength
- **CDA-compliant section classes** — 14 types (Abschluss, Anamnese, Anrede, Diagnosen,
  AufnahmeMedikation, Befunde, EchoBefunde, AktuellDiagnosen, EntlassMedikation, KuBefunde, Labor,
  Mix, AllergienUnverträglichkeitenRisiken, Zusammenfassung)
- **V1.1.2 extension** (Becker et al., `10.1016/j.ijmedinf.2025.106009`) — token-level Diagnostic,
  Diagnosis, Drug, Medical_Finding, Therapy

Files: `cardiode.zip` 22.8 MB · `cardiode_1.1.2_extension_becker.zip` 20.1 MB (both **restricted**) ·
`cardiode_dependencies_inception.zip` 6.3 KB · `DUA_en.pdf` · two READMEs.
