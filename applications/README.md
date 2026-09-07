# Corpus access applications

Four applications, all on the critical path — nothing else in the schedule absorbs their latency.
Drafts below are ready for AM to check, sign and send. **Nothing here has been sent.**

| corpus | to | status | who must act |
|---|---|---|---|
| **BRONCO150** | Prof. Dr. Ulf Leser, `leser@informatik.hu-berlin.de` | [draft ready](bronco150_dua.md) | AM signs + sends |
| **CARDIO:DE** | **`christoph.dieterich@uni-heidelberg.de`** (study director) | [complete](cardiode_request.md) — DUA downloaded + MD5-verified, all fields filled | AM signs + sends |
| **i2b2 / n2c2 2014** | DBMI Data Portal | [text ready](n2c2_request.md) | **AM only** — per-individual registration |
| **OntoNotes 5.0** | `ldc@ldc.upenn.edu` | [complete](ontonotes_ldc.md) — **fee verified $0.00**; one signature covers the whole chair | AM signs + e-mails |

## PDFs on disk — for signing

`applications/forms/` (**gitignored**, local only). Absolute path:
`~/Documents/code/pseudonymization/applications/forms/`

| file | what it is |
|---|---|
| `BRONCO150_DUA_blank.pdf` | the official form, 3 pp — sign page 3 |
| `BRONCO150_fill_sheet.pdf` | the values to enter, purpose text, covering e-mail |
| `CARDIODE_DUA_blank.pdf` | the official agreement, 4 pp — fields on page 4 (MD5 verified against heiDATA) |
| `CARDIODE_fill_sheet.pdf` | values, group + project description, infrastructure block, covering e-mail |
| `LDC_nonmember_agreement_blank.pdf` | the LDC non-member agreement, 1 p |
| `LDC_OntoNotes_fill_sheet.pdf` | fields, ordering steps, corpus summary |
| `n2c2_portal_text.pdf` | nothing to sign — the research summary to paste into the portal |

The blanks came from `www2.informatik.hu-berlin.de/~leser/bronco/`, heiDATA `doi:10.11588/DATA/AFYQDY`
and `catalog.ldc.upenn.edu/license/ldc-non-members-agreement.pdf`. Not committed: they are other
people's documents and the repo is meant to be released.

## Applicant details used in every draft

Taken from the Pattern Recognition Lab's own materials; **confirm before sending**.

| field | value |
|---|---|
| Name | Prof. Dr.-Ing. habil. Andreas Maier |
| Affiliation | Friedrich-Alexander-Universität Erlangen-Nürnberg, Pattern Recognition Lab |
| Position | Chair, Computer Science 5 (Pattern Recognition) |
| E-mail | `andreas.maier@fau.de` |
| Institution website | `lme.tf.fau.de` |

**Decided (AM, 2026-09-07):** AM applies **in his own name, for the lab**. See "Applying for the
lab" below for what that does and does not cover.

## Two clauses, both cleared by AM (2026-09-07)

Both agreements were read in full. Each has a no-re-identification clause and a no-third-party
clause; neither blocks the study.

| | AM's ruling |
|---|---|
| BRONCO 3 · CARDIO:DE 1.4 — no attempt to identify individuals | *"De-ID means to find the true identity of the patients. We are not doing that."* The attacks invert **pseudonyms we generate ourselves**. CARDIO:DE 1.4 is explicit: identifying individuals *"based on the Data received"* |
| BRONCO 8 · CARDIO:DE 2.2 — no third parties / outside services | *"Our data stays in house. We don't use third party APIs."* The LLM endpoint is NHR@FAU, the university's own HPC centre |

**No cells are licence-blocked.** Both points are still stated plainly in the covering letters, so
the providers see what we intend rather than discovering it later.

## Applying for the lab — what the agreements actually allow

AM, 2026-09-07: *"I need to apply in my name for my entire lab."* That works for the **request**;
it does not remove the per-person signature, and both texts are explicit:

> BRONCO **2.** Usage of BRONCO150 is granted to **individual Data Users only**. All prospective Data
> Users must fill out this data usage agreement **individually**.
>
> CARDIO:DE **1.2** Access to data is granted to **individual Recipients only**. Any Recipients or
> User must fill out this data usage agreement **individually**.

So the shape is:

- **AM is the applicant and Data User**, and — for CARDIO:DE — also the person signing as responsible
  for the infrastructure. The **group description** is where the lab is represented; CARDIO:DE asks
  for one explicitly, which fits a lab-level application well.
- **Anyone else who actually processes the corpus signs their own copy.** Not a formality we can
  route around: it is one sentence in each agreement.
- Both covering letters therefore **ask the question directly** — whether staff working under AM's
  responsibility on the named infrastructure are covered by his signature, or whether each needs a
  separate agreement, which we would then supply. That gets an authoritative answer instead of an
  assumption, and costs one paragraph.

The same is true of **n2c2**: the DBMI portal grants access per registered individual, and there is
no lab-level route at all. Every person who touches it registers and is approved separately.

## Storage

AM, 2026-09-07: the cluster is exclusive to the group and processing stays in house, so data
protection is not a concern. What remains is narrower and purely contractual: BRONCO clause 4 wants a
**single copy under the Data User's own administration**, and both agreements restrict access to
people who have signed. That argues for keeping the DUA corpora out of the world-readable shared
folder — not because of privacy law, but because the agreements say who may read them.

So, two locations:

| what | where |
|---|---|
| public corpora (Enron, TAB, CodEAlltag, MEDDOCAN, MedDeID, REDACT, PIIBench, E3C, AI4Privacy) | `/cluster/shared_dataset/pseudonymization-corpora/` — the group's shared dataset folder |
| OntoNotes | the shared folder is fine — the LDC agreement permits use across the whole research group |
| DUA-bound corpora (BRONCO150, CARDIO:DE, n2c2, OntoNotes) | **not** the shared folder — a separate directory under AM's own administration, readable only by signatories |

## Deadlines created by signing

- **BRONCO clause 5:** the corpus must be **deleted twelve months after signing**, and Leser informed
  that deletion has happened. Extension requires re-signing. Put it in a calendar the day the
  agreement is signed.
- **CARDIO:DE clause 8.1:** term is **5 years**, extendable — far more generous. Clause 6.3: on
  completion the data is returned or deleted, and a further project needs a new application.
- **BRONCO clause 11:** actual research activity must adhere to the stated purpose; a different kind
  of research requires a new agreement. This is why the purpose text below is written narrowly and
  honestly rather than broadly.
