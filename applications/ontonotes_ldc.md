# OntoNotes 5.0 (LDC2013T19) — LDC, non-member route

**AM, 2026-09-07: FAU is not an LDC member.** So this goes through the non-member route, which is
short: create an account, sign one agreement, order, download.

**Delivery is Web Download only** — no physical media, so no shipping to arrange.

---

## The agreement — and it is the least restrictive of the four

*LDC User Agreement for Non-Members* (`catalog.ldc.upenn.edu/license/ldc-non-members-agreement.pdf`),
a single page. Read in full 2026-09-07.

**It covers a research group under one signature.** The agreement defines *User* as a named
individual at an affiliation, and *User's Research Group* as a specific department or area within
the university — then restricts redistribution only to people **outside** that group:

> Unless explicitly permitted herein, User shall not otherwise publish, retransmit, disclose,
> display, copy, reproduce or redistribute the LDC Databases to others **outside of User's Research
> Group**.

That is exactly the lab-level application AM asked for, and it is the opposite of BRONCO clause 2 and
CARDIO:DE clause 1.2, which both require every user to sign individually. **One signature covers the
Pattern Recognition Lab.**

Other terms:

| | |
|---|---|
| permitted use | *"non-commercial linguistic education, research and technology development"* |
| publication | limited excerpts may appear in articles and reports describing the results |
| commercial use | requires joining LDC as a For-Profit Member and paying applicable fees — not our case |
| citation | required in scholarly publications |
| warranty | none; provided "AS IS" |
| **re-identification** | **no clause** — unlike BRONCO 3 and CARDIO:DE 1.4 |
| **third-party services** | **no clause** — unlike BRONCO 8 and CARDIO:DE 2.2 |
| deletion | **no deletion deadline** — unlike BRONCO's 12 months |

So OntoNotes carries no design constraints at all beyond "do not redistribute outside the lab", which
the build-recipe distribution model (`metacorpus.md` §6) already satisfies — we ship converters and a
manifest, never corpus text.

## Signature block

Signed **for the organization**, so a title is required — AM as chair holder fits:

```
For the organization: Friedrich-Alexander-Universität Erlangen-Nürnberg,
                      Pattern Recognition Lab (Computer Science 5)
Signature:            ____________
Date:                 ____________
Name:                 Andreas Maier
Title:                Chair, Computer Science 5 (Pattern Recognition)

User (individual):    Andreas Maier
Affiliation:          Friedrich-Alexander-Universität Erlangen-Nürnberg
User's research group: Pattern Recognition Lab (Computer Science 5)

EXHIBIT A — CORPORA RECEIVED
1  OntoNotes Release 5.0, LDC2013T19
```

Return by e-mail to `ldc@ldc.upenn.edu` (or fax +1 215 573 2175).

## Fee — verified 2026-09-07, logged in

**$0.00.** The catalogue's Fees box, visible once signed in, reads:

| category | fee |
|---|---|
| 2013 Member | $0.00 |
| **Non-Member** | **$0.00** |
| Reduced-License | $0.00 |
| Extra Copy | $0.00 |

Available Media: **Web Download**. So OntoNotes costs nothing and there is nothing to ship — the
earlier "unverified" caveat is resolved.

## How it is actually obtained — by e-mail, not a web order

There is **no cart or checkout button** on the catalogue page for this corpus. The page carries the
fee table and a link to the *LDC User Agreement for Non-Members*, and nothing else. The route is the
same shape as BRONCO and CARDIO:DE:

1. Sign `applications/forms/LDC_nonmember_agreement_blank.pdf`, with **Exhibit A line 1 =
   "OntoNotes Release 5.0, LDC2013T19"**.
2. E-mail the signed agreement to **`ldc@ldc.upenn.edu`** (fax +1 215 573 2175 is the alternative).
3. LDC enables the web download on the account.

Field values are in `applications/forms/LDC_OntoNotes_fill_sheet.pdf`.

## What it contributes

The only member of the meta corpus that supplies all three of these at once:

- **real names** in natural distribution (tier T1);
- **co-reference annotation** — one of only two corpora in the set that has it, the other being TAB;
- **non-Latin scripts with real names**.

Contents per LDC, ~2.9 M words total:

| language | words | genres |
|---|---:|---|
| English | 1.445 M | news · broadcast news · broadcast conversation · web · telephone |
| **Mandarin Chinese** | 1.0 M | news · broadcast news · broadcast conversation · web · telephone · pivot texts |
| **Arabic** | 0.3 M | **news only** |

Annotation layers: Penn-Treebank-style syntax, PropBank predicate-argument structure, word sense,
ontology links, and **co-reference**. English NER portion: 3,637 documents, 18 entity types.

**Note for the balance rule:** Arabic is a quarter the size of Chinese and news-only, so the
non-Latin arm of the meta corpus is lopsided before any sampling. That is a fact for AM's capping
decision, not something to fix silently.
