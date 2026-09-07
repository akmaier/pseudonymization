# CARDIO:DE — data request

**To:** heiDATA, `data@uni-heidelberg.de` · approved by the study director, **Christoph Dieterich**
**Stated lead time:** at least one week. **Send early.**

**Still needed:** the signed DUA form itself. It is `DUA_en.pdf` (229 KB) on the heiDATA dataset page
(`doi:10.11588/DATA/AFYQDY`, Terms → Terms of Use). The page is behind an Anubis bot-check that
blocks scripted fetching, so it has to be downloaded from a browser.

**Corpus, as listed on heiDATA 2026-09-07 — now V1.1.2, newer than our notes:**

| file | size |
|---|---|
| `cardiode.zip` | 21.8 MB |
| `cardiode_1.1.2_extension_becker.zip` | 19.2 MB — community annotations, Becker et al. |
| `cardiode_dependencies_inception.zip` | 6.1 KB |
| `DUA_en.pdf` | 229 KB — the agreement |

500 German cardiology routine doctor's letters, manually de-identified, **temporal information
deliberately preserved**. Gold annotation layers:

- **medication information** — ActiveIng, Dosage, Drug, Duration, Form, Frequency, Reason, Route,
  Strength
- **CDA-compliant section classes** — Abschluss, Anamnese, Anrede, Diagnosen, AufnahmeMedikation,
  Befunde, EchoBefunde, AktuellDiagnosen, EntlassMedikation, KuBefunde, Labor, Mix,
  AllergienUnverträglichkeitenRisiken, Zusammenfassung
- **V1.1.2 extension**: token-level Diagnostic, Diagnosis, Drug, Medical_Finding, Therapy

That is **two downstream tasks, not one** — medication information extraction and section
classification — which is better than the "German clinical NER" our corpus table currently claims.
Both are updated in `data/metacorpus.md`.

---

## Group description

> The **Pattern Recognition Lab** at Friedrich-Alexander-Universität Erlangen-Nürnberg
> (`lme.tf.fau.de`) is a research group in the Department of Computer Science working on machine
> learning for medical data, headed by Prof. Dr.-Ing. Andreas Maier.
>
> - Requester: **Prof. Dr.-Ing. Andreas Maier**
> - Position: Professor, Head of the Pattern Recognition Lab
> - Affiliation: Friedrich-Alexander-Universität Erlangen-Nürnberg, Pattern Recognition Lab,
>   Martensstraße 3, 91058 Erlangen, Germany
> - E-mail: `andreas.maier@fau.de`
> - Institution website: `lme.tf.fau.de`

## Project description

> **End-to-end evaluation of text pseudonymisation: detection, utility and leakage.**
>
> Current work on clinical de-identification varies the *detector* and holds the replacement step
> fixed. We invert that. Taking the technique and policy taxonomies of ENISA (2021) and
> DIN EN ISO 25237, we treat the **pseudonymisation function and policy** as the independent
> variable — deterministic versus document-randomised versus fully randomised, crossed with counter,
> RNG-with-mapping-table, hash, HMAC and symmetric encryption, and with three surrogate forms
> (opaque tag, realistic surrogate, attribute-matched surrogate).
>
> For each combination we measure three things on the same documents: detection quality, **utility**
> — downstream task performance on pseudonymised text — and residual leakage. The distinctive
> requirement we study is **pseudonym stability**: one person must keep one pseudonym across a corpus
> and must never collapse into another person.
>
> **CARDIO:DE would serve the utility axis in German.** Its medication-information and section-class
> annotation layers give us two downstream tasks on real clinical routine text, which we would
> evaluate on pseudonymised versus unmodified documents in two regimes (train and test both
> pseudonymised; train on original, test on pseudonymised). Because CARDIO:DE is already
> de-identified with semantic placeholders, it also lets us measure what placeholder-style masking
> costs relative to realistic surrogates — a comparison for which we know of no published figures.
>
> The study uses **public data only**; no clinical data from Erlangen is involved. Results are
> aggregate performance figures. We will not attempt to identify or re-identify any person,
> physician or institution, and we will not transfer the corpus to any third party. Code and
> aggregate results will be released; no corpus text will be redistributed.
>
> Target venue: TrustFMI workshop at ACCV 2026.

## Covering e-mail

> **Subject:** CARDIO:DE data request — Pattern Recognition Lab, FAU Erlangen-Nürnberg
>
> Sehr geehrte Damen und Herren, sehr geehrter Herr Prof. Dieterich,
>
> hiermit beantragen wir Zugang zu CARDIO:DE. Anbei die unterschriebene Data Usage Agreement sowie
> Gruppen- und Projektbeschreibung.
>
> Wir untersuchen, wie sich Verfahren und Politik der Pseudonymisierung (nach ENISA und
> ISO 25237) auf Erkennung, Nutzbarkeit und Restrisiko klinischer Texte auswirken. CARDIO:DE würden
> wir für die Nutzbarkeitsmessung im Deutschen verwenden — Medikationsextraktion und
> Abschnittsklassifikation auf pseudonymisiertem gegenüber unverändertem Text.
>
> Eine Rückfrage: Wir verwenden für einen Teil der Studie einen LLM-Endpunkt des NHR@FAU
> (universitär betrieben, kein kommerzieller Dienst). Falls die Nutzungsbedingungen eine
> Verarbeitung außerhalb der eigenen Administration ausschließen, würden wir CARDIO:DE davon
> ausnehmen. Wir wären für eine kurze Klarstellung dankbar.
>
> Mit freundlichen Grüßen
> Andreas Maier

---

## Checklist

- [ ] Download `DUA_en.pdf` from the heiDATA page (browser needed — Anubis blocks scripts)
- [ ] Read it for re-identification and third-party clauses, as with BRONCO
- [ ] Sign, scan
- [ ] Send with group + project description to `data@uni-heidelberg.de`
- [ ] Storage: **not** the shared folder if the DUA restricts access to signatories
