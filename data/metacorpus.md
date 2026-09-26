# Corpus list

**What each corpus *is*.** What each corpus is *for* — its role in the design, which measurements it
carries, and how it is sampled — is in [`experiment_plan.md`](../experiment_plan.md) §4 and §5, and
only there. This file specifies nothing.

Rewritten 2026-09-09 (AM): it had grown into a second requirements document, complete with a
"T1–T5 identifier provenance" tier taxonomy that was an agent's construction and was struck. The
requirements it carried — the unified record schema, the entity-type taxonomy, the build-recipe
distribution, the sampling schemes — were merged into `experiment_plan.md` before this rewrite.

---

## In the design

| corpus | languages | domain | size on disk | annotates | licence |
|---|---|---|---|---|---|
| **TAB / ECHR** | en | legal judgments | 77 MB, 3 split JSONs | 8 entity types, DIRECT/QUASI/NO_MASK, **co-reference chains**, 30-label ECHR articles in `meta.articles` | MIT |
| **OntoNotes 5.0** | en · zh · ar | news · broadcast · magazine · telephone · web · pivot | 890 MB, packed | 18 NE types, **co-reference** | LDC (FAU licensed LDC2013T19 since 2020-02-06; covers the whole group) |
| **Enron** | en | corporate e-mail | 423 MB tarball, 443,254,787 B byte-exact | nothing — spans are derived from message headers by our adapter; ~184-employee org chart exists as a public auxiliary record | public (FERC release) |
| **CodEAlltag** | de | e-mail (`pS`, donated) · usenet (`pXL`, 7 topic segments) | 6.6 GB — ~1.4 M individual message files, so any recursive scan is slow | **no spans in the release**; topic = the `pXL` partition; per-document formality scores ship separately | CC-BY-SA-4.0 |
| **CARDIO:DE** 🔒 | de | cardiology discharge letters | 459 MB | medication IE (9 classes), section types (14), medication relations; Becker token-level extension (Diagnosis/Therapy/Medical_Finding) | DUA, **per individual user** |

**CodEAlltag, the two parts.** `pS` is 800 **donated private e-mails** — the only part that was
manually annotated before substitution, and the annotations are not in the release. `pXL` is
~1,469,000 **Usenet postings** in mail format, *"extracted from Usenet newsgroups and underwent
merely rudimentary data cleansing"*, pseudonymised **automatically**. All seven segments are German;
the segment name is the topic, not the language — **GERMAN means e-mails about the German language
itself**, the `de.etc.sprache.*` newsgroups.

| segment | topic, verbatim from the release | messages |
|---|---|---:|
| EVENTS | *"topics related to events of the day"* | ~246,000 |
| GERMAN | *"topics related to the German language"* | ~241,000 |
| TEENS | *"topics of interest for teenagers"* | ~239,000 |
| PHILOSOPHY | *"philosophical issues"* | ~209,000 |
| MOVIES | *"discussing movies"* | ~206,000 |
| FINANCE | *"financial issues, including stock exchange news"* | ~174,000 |
| TRAVELS | *"travel and tourism"* | ~154,000 |

The release states a **documented gender bias**: *"likely to contain a gender bias since taggers
recognized more mentions of male given names."* No surrogate inventory or gazetteer is published.

**Enron artefacts of the release**: 5,112 files carry the synthetic address `no.address@enron.com`;
attachments were stripped, leaving `<<>>` stubs; some messages were removed at the request of
affected employees.

**CARDIO:DE storage.** Not in the shared folder. The grant covers AM alone — Heidelberg confirmed one
countersigned agreement per person — so it lives under the restricted DUA root (`PSEUDONYMKIT_DUA`), mode
`700`. Laptop copies were deleted after transfer; the agreement names the chair's cluster as the
storage infrastructure. **500 letters split 400 / 100, and only the 400 carry annotations** —
*"Annotations of CARDIO:DE100 are kept internally as held-out data for future shared task
purposes."*

Everything else public sits in the group shared dataset folder, fetched by
[`scripts/fetch_corpora.sh`](../scripts/fetch_corpora.sh), which is idempotent.

## Wanted, not on disk

| corpus | state |
|---|---|
| **BRONCO150** | de, oncology discharge, ICD-10/OPS/ATC coding. Application sent 2026-09-07, no reply. Its clause 5 requires deletion by **2027-09-07** with Leser informed |
| **n2c2 2014** | en, clinical, longitudinal — 1,304 records over 296 patients, Track 1 and Track 2 annotate the same records. ⛔ Registration closed, "temporarily unavailable". No route |

## On disk, not in the design

Fetched before the corpus set was settled; still on the cluster.

| corpus | languages | size | licence |
|---|---|---|---|
| MEDDOCAN | es | 78 MB | CC-BY-4.0 |
| MedDeID | nl | 13 MB | CC-BY-4.0 |
| REDACT | 25 langs / 9 scripts | 7.5 MB repo (the 213 MB benchmark itself is behind Git-LFS) | CC-BY-SA-4.0 |
| AI4Privacy | 6 langs | 767 MB | custom: academic free, commercial separate |
| E3C | it, en, fr, es, eu | 924 MB | public via European Language Grid |
| PIIBench | multi | 6.1 MB | **ships no corpus** — pipeline and taxonomy only |

Two facts about these that were established on inspection and are easy to rediscover the hard way:

- **AI4Privacy's FinPII-80k is not in the public release.** `ai4privacy/pii-masking-300k` holds 18
  files, all OpenPII. There is no financial split to download.
- **PIIBench ships no corpus**, only `run_data_pipeline.py` and `src/`. It contributes the
  80+ → 48 canonical label mapping; a corpus slice only if rebuilt from its ten sources.

## Storage

`/cluster` was at 95 % on 2026-09-06. The OntoNotes tarball is left packed; unpacking is a build
step, not acquisition. Check free space before expanding it.
