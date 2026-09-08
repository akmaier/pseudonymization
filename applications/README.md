# Corpus access applications

Four corpora needed access. **Two are sent, one is blocked, one turned out to need nothing.** All were on the critical path — nothing else in the schedule absorbs their latency.
Drafts below are ready for AM to check, sign and send. **Nothing here has been sent.**

| corpus | to | status | who must act |
|---|---|---|---|
| **BRONCO150** | Prof. Dr. Ulf Leser, `leser@informatik.hu-berlin.de` | sent 2026-09-07, **no reply yet** | wait; ⏰ delete by **2027-09-07** |
| **CARDIO:DE** | `christoph.dieterich@uni-heidelberg.de` | ✅ **ON DISK 2026-09-08**, checksums verified. ⚠ **single-user: AM only** | done |
| **i2b2 / n2c2 2014** | DBMI Data Portal | ⛔ **[BLOCKED](n2c2_request.md)** — registration closed, datasets "temporarily unavailable" | AM: e-mail DBMI to ask when it reopens |
| **OntoNotes 5.0** | — | ✅ **[no application needed](ontonotes_ldc.md)** — already licensed to FAU since 2020-02-06, downloaded 2026-09-07 | done |

## PDFs on disk — for signing

`applications/forms/` (**gitignored**, local only). Absolute path:
`~/Documents/code/pseudonymization/applications/forms/`

| file | what it is |
|---|---|
| **`BRONCO150_DUA_FILLED.pdf`** | **filled** — name, affiliation, position, e-mail and the 93-word purpose typed onto page 3. **Print, sign, scan.** |
| **`CARDIODE_DUA_FILLED.pdf`** | **filled** — Recipient named on page 1; page 4 carries both blocks, the group description and the 146-word project description, plus Sven Grünke as co-administrator. **Print, sign, scan.** |
| `BRONCO150_DUA_blank.pdf` | the untouched original, for reference |
| `CARDIODE_DUA_blank.pdf` | the untouched original (MD5-verified against heiDATA) |
| `LDC_nonmember_agreement_blank.pdf` | LDC non-member agreement, 1 p — fields are few, fill by hand or type |
| `LDC_OntoNotes_fill_sheet.pdf` | fields, ordering steps, corpus summary |
| `BRONCO150_fill_sheet.pdf` · `CARDIODE_fill_sheet.pdf` | the same values as plain text, plus the covering e-mails to paste |
| `n2c2_portal_text.pdf` | nothing to sign — the research summary to paste into the portal |

**Left blank on purpose:** every signature, and both `Date:` fields on CARDIO:DE page 4 — the date
should be the day it is actually signed, and BRONCO's twelve-month deletion clock (clause 5) runs
from it.

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

## ⏰ Standing obligations, once granted

| corpus | obligation | when |
|---|---|---|
| **BRONCO150** | **delete the corpus and inform Prof. Leser** that deletion has happened (clause 5) | by **2027-09-07** — twelve months from the signature date |
| **CARDIO:DE** | term runs 5 years (clause 8.1); return or delete on completion (clause 6.3); a further project needs a new application | from 2026-09-07 |
| **CARDIO:DE** | **one countersigned agreement per person.** The grant covers **AM alone** | now |

## The per-person question was answered: yes (2026-09-08)

Both covering letters asked whether staff working under AM's responsibility are covered by his
signature. **Heidelberg answered no** — every user needs their own countersigned document. AM then
narrowed the request to himself, and that is what was approved.

So the earlier plan of "AM applies for the lab" holds for the *request* and not for *access*:
each additional person needs their own agreement sent and countersigned before touching the corpus,
derived files, or the cluster copy. BRONCO's reply will probably say the same, since its clause 2 is
worded identically.

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
| **CARDIO:DE** | **`/cluster/maier/dua-restricted/cardiode`, mode `700`** — created 2026-09-08. The shared folder is group-readable and would breach the single-user grant |
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
