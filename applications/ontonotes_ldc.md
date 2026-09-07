# OntoNotes 5.0 (LDC2013T19) — already licensed, no application needed

> ## ✅ RESOLVED 2026-09-07 — the corpus was already in FAU's LDC account
>
> Signed in, `catalog.ldc.upenn.edu/organization/downloads` lists **LDC2013T19, OntoNotes Release
> 5.0, invoice date 2020-02-06** as available for download. It was licensed six years ago; no
> agreement had to be signed and no fee was payable.
>
> | | |
> |---|---|
> | file | `ontonotes-release-5.0_LDC2013T19` |
> | size | **890 MB** |
> | MD5 | `d9c9b6a8063f8274b5c6e135021aa070` |
>
> Downloaded and transferred to the cluster alongside the other public corpora. The LDC non-member
> agreement (`applications/forms/LDC_nonmember_agreement_blank.pdf`) is therefore **not needed** and
> was never sent.
>
> **Also already licensed to FAU**, seen on the same page and noted in case they are ever wanted:
> CHiME3, CSR-I (WSJ0), WSJCAM0, TIMIT, CALLHOME Mandarin/Spanish/Japanese, CELEX2, Buckwalter
> Arabic Morphological Analyzer. So FAU does hold LDC licences even without a current membership —
> which means **Avocado (LDC2015T03)** would be obtainable by the same route if the e-mail domain
> ever needs a second English corpus.

---

## Licence terms that still bind

*LDC User Agreement for Non-Members*, one page, read in full 2026-09-07. The least restrictive of the
four corpora:

| | |
|---|---|
| permitted use | non-commercial linguistic education, research and technology development |
| redistribution | only within **User's Research Group** — so the group's shared dataset folder is fine |
| publication | limited excerpts may appear in articles and reports |
| citation | required |
| **re-identification** | **no clause** |
| **third-party services** | **no clause** |
| deletion | **no deadline** |

The only constraint is no redistribution outside the group, which the build-recipe distribution model
(`metacorpus.md` §6) already satisfies: we ship converters and a manifest, never corpus text.

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
