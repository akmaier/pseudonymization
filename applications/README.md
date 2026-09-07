# Corpus access applications

Four applications, all on the critical path — nothing else in the schedule absorbs their latency.
Drafts below are ready for AM to check, sign and send. **Nothing here has been sent.**

| corpus | to | status | who must act |
|---|---|---|---|
| **BRONCO150** | Prof. Dr. Ulf Leser, `leser@informatik.hu-berlin.de` | [draft ready](bronco150_dua.md) — **read the conflict note first** | AM signs + sends |
| **CARDIO:DE** | heiDATA, `data@uni-heidelberg.de` | [draft ready](cardiode_request.md); the DUA form itself still has to be fetched | AM signs + sends |
| **i2b2 / n2c2 2014** | DBMI Data Portal | [text ready](n2c2_request.md) | **AM only** — per-individual registration |
| **OntoNotes 5.0** | LDC | [blocked on one fact](ontonotes_ldc.md) | AM: is FAU an LDC member? |

## Applicant details used in every draft

Taken from the Pattern Recognition Lab's own materials; **confirm before sending**.

| field | value |
|---|---|
| Name | Prof. Dr.-Ing. Andreas Maier |
| Affiliation | Friedrich-Alexander-Universität Erlangen-Nürnberg, Pattern Recognition Lab |
| Position | Professor, Head of the Pattern Recognition Lab |
| E-mail | `andreas.maier@fau.de` |
| Institution website | `lme.tf.fau.de` |

**Open question for AM:** do the applications name **you alone**, or the full author list? It matters
— BRONCO clause 2 and the n2c2 portal both grant access **per individual**, so every co-author or
HiWi who touches those corpora needs their own signed agreement. Naming only you is simplest and can
be extended later; naming everyone front-loads the paperwork but avoids a blocked collaborator in
week three.

## The thing that matters more than the paperwork

**Three of the four DUAs restrict what we may do, not just who may hold the data.** BRONCO's terms are
in hand and explicit; CARDIO:DE's and n2c2's are expected to be similar. Two clauses bite:

- **No re-identification.** BRONCO clause 3: the Data User will *"not attempt to identify or
  re-identify individual persons, hospitals or doctors"*. Our leakage attacks A1–A4 are
  re-identification procedures — even though they target *our own pseudonyms* rather than the
  corpus. **On DUA corpora we should run the utility axis only**, and ask the provider explicitly
  before assuming otherwise.
- **No transmission to external services.** BRONCO clause 8: the corpus *"must not be transmitted
  electronically to other services not under administration of the Data User, such as online
  translation services"*. The NHR@FAU LLM gateway is such a service. **That rules out the LLM
  detector levels of axis D and attack A4 on BRONCO**, and probably on CARDIO:DE and n2c2 too.

Per `CLAUDE.md` §1 these cells are **reported as licence-blocked, not silently dropped**, and the
question is put to each provider in writing rather than decided by us. See the per-corpus drafts.

## Storage

AM, 2026-09-07: the cluster is exclusive to the group, so **data protection is not a concern**. The
DUA restrictions are a separate matter — they are contractual limits owed to the corpus providers,
not privacy law, and they survive the fact that the machine is private. BRONCO clause 4 requires a
**single copy under the Data User's own administration**, and clause 8 forbids sharing with anyone
who has not signed.

So, two locations:

| what | where |
|---|---|
| public corpora (Enron, TAB, CodEAlltag, MEDDOCAN, MedDeID, REDACT, PIIBench, E3C, AI4Privacy) | `/cluster/shared_dataset/pseudonymization-corpora/` — the group's shared dataset folder |
| DUA-bound corpora (BRONCO150, CARDIO:DE, n2c2, OntoNotes) | **not** the shared folder — a separate directory under AM's own administration, readable only by signatories |

## Deadlines created by signing

- **BRONCO clause 5:** the corpus must be **deleted twelve months after signing**, and Leser informed
  that deletion has happened. Extension requires re-signing. Put it in a calendar the day the
  agreement is signed.
- **BRONCO clause 11:** actual research activity must adhere to the stated purpose; a different kind
  of research requires a new agreement. This is why the purpose text below is written narrowly and
  honestly rather than broadly.
