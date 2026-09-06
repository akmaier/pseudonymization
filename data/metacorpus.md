# The meta corpus

**Decision by AM, 2026-09-06.** Rather than pick corpora one at a time, assemble a **single balanced
meta corpus** spanning tasks and languages, in one unified format. It answers the study's questions
in one pass instead of corpus by corpus, and it makes the cells of `PLAN.md` §Factors comparable
across languages and domains for the first time.

Two criteria set by AM in the same decision:

1. **Identifier provenance matters.** *"PHI-inserted is not great. Same for synthetic. Pseudonymised
   is ok — we can revert with rule-based approaches."*
2. **Task coverage, not just medical.** Every domain in the meta corpus must carry a real downstream
   task, e-mail included, so the utility axis is measurable outside the clinic.

---

## 1. Identifier provenance — the tiering AM's criterion implies

Why it matters: **A1 (dictionary) and A2 (frequency analysis) both consume the name-frequency
distribution.** A2 works precisely because, under a deterministic policy, pseudonym frequency mirrors
real-name frequency. A corpus whose identifiers were generated or inserted has no natural surname
distribution, so a result on it does not transfer.

| tier | provenance | why it is or is not usable | corpora |
|---|---|---|---|
| **T1** | **real names, natural distribution** | the only tier where A1/A2 results mean what they claim | TAB/ECHR · Enron · OntoNotes |
| **T2** | **realistic surrogates, consistently substituted** | natural *placement* and near-natural distribution. Rule-based span recovery works only where the surrogate inventory is published — it is for i2b2, **not** for CodEAlltag (§5) | i2b2/n2c2 2014 · CodEAlltag |
| **T3** | **placeholder-masked** (`<NAME>`, `[Datum]`) | spans recoverable by rule, but the names are *gone* — the distribution is destroyed, and refilling them is insertion | CARDIO:DE · BRONCO150 |
| **T4** | **PHI inserted into text that never had it** | placement is artificial as well as the names; MEDDOCAN is explicitly *"a synthetic corpus of clinical cases enriched with PHI expressions"*, added to published SciELO case reports by health documentalists | MEDDOCAN |
| **T5** | **fully synthetic** | *"no real personal data. Every identifier is fabricated"* | MedDeID · REDACT · AI4Privacy |

**T4 and T5 are not dropped — they become a control.** Provenance enters the design as an explicit
factor (axis F). Running the same attacks across T1→T5 measures how much a benchmark's own
construction inflates or deflates apparent privacy, which is a second-order finding the field needs
and nobody has reported: every 2026 detection benchmark lives in T5.

---

## 2. Composition

Balanced on four things at once: **language · domain · downstream task · provenance tier**, with
**stability support** as the constraint that decides membership.

| corpus | lang | script | domain / genre | task for the utility axis | stability support | tier |
|---|---|---|---|---|---|---|
| **TAB / ECHR** | en | Latin | legal judgments | **ECHR article classification, multi-label** — ships in `meta.articles`, 30 labels, no join needed (§5) | **co-reference** (`entity_id`), DIRECT/QUASI/NO_MASK | T1 |
| **Enron** | en | Latin | corporate e-mail | **folder classification** (Klimt & Yang 2004) | **cross-document**: sender/recipient identity from headers; org chart (~184 employees) as A3 auxiliary | T1 |
| **OntoNotes 5.0** | en, **zh**, **ar** | Latin, Han, Arabic | news · broadcast · weblog · telephone speech · usenet | **co-reference resolution + NER** (the task pseudonymisation most directly damages) | **co-reference**, 18 NE types | T1 |
| **i2b2 / n2c2 2014** | en | Latin | clinical, **longitudinal** | heart-disease **risk-factor extraction** (Track 2 — **confirmed same records**, §5) | **cross-document**: 1,304 records over **296 patients** | T2 |
| **CodEAlltag** | de | Latin | e-mail (donated) · usenet (XL) | **7-way topic classification** (XL segments) + **formality scores** (released separately) | **no gold spans in the release** (§5); consistent surrogates only | T2 |
| **CARDIO:DE** | de | Latin | cardiology letters | German clinical NER | placeholders give free gold spans; no names | T3 |
| **BRONCO150** | de | Latin | oncology discharge | **ICD-10 / OPS / ATC coding** | none — sentence-scrambled, no document | T3 |
| **MEDDOCAN** | es | Latin | clinical case reports | Spanish clinical NER | none (no co-reference) | T4 |
| **MedDeID** | nl | Latin | clinical (synthetic) | Dutch de-identification NER | none | T5 |
| **REDACT** | 25 langs / 9 scripts | many | mixed, 9 controlled axes | detection only | none | T5 |
| **AI4Privacy** | 6 langs | Latin+ | general + **finance** (FinPII-80k) | financial PII detection | none | T5 |
| **E3C** | it, en, fr, es, eu (+el, pl, sk, sl) | Latin, Greek | clinical cases | clinical entity + temporal extraction | **no PII layer at all** | — |

### What each axis buys

- **Languages:** en, de, es, nl, zh, ar as the balanced core, plus REDACT's 25 and E3C's 9 as the
  breadth tail. **zh and ar come from OntoNotes** and matter because the OPF evaluation reports
  detector collapse on non-Latin scripts (Arabic 0.04, Cyrillic 0.03) — that is where H1/H2 are
  stressed hardest, and until now we had no non-Latin corpus with real names.
- **Tasks:** legal outcome prediction · e-mail folder and topic classification · clinical
  risk-factor extraction · clinical coding · co-reference + NER · financial PII. Six task families,
  four domains, so utility is no longer a clinical-only claim.
- **Stability:** the metric `PLAN.md` calls essentially unevaluated needs entity identity across
  mentions or documents. Only four corpora supply it — **TAB** and **OntoNotes** (co-reference within
  document), **i2b2 2014** (the same patient across a longitudinal record) and **Enron** (the same
  person across a mailbox). Two of the four are e-mail and clinical, i.e. exactly the domains where
  cross-document linkage is the point.

---

## 3. Unified schema

The meta corpus is one format; each source gets a converter and nothing else changes downstream.

```jsonc
{
  "doc_id":      "tab/001-12345",
  "corpus":      "tab",
  "language":    "en",
  "script":      "Latn",
  "domain":      "legal",
  "genre":       "court_judgment",
  "provenance":  "real",            // real | surrogate | placeholder | inserted | synthetic
  "split":       "train",
  "text":        "...",
  "subject_id":  "patient_0042",    // cross-document identity where it exists; null otherwise
  "task":        {"name": "echr_violation", "label": ["Art.6", "Art.13"]},
  "spans": [
    {"start": 143, "end": 154,
     "text":       "John Weber",
     "type":       "PERSON",        // harmonised taxonomy
     "type_src":   "NOMBRE_SUJETO_ASISTENCIA",
     "entity_id":  "e17",           // co-reference chain; null where unannotated
     "identifier_class": "DIRECT"}  // DIRECT | QUASI | NO_MASK, where annotated
  ]
}
```

**Do not invent the taxonomy.** PIIBench already normalises 80+ label variants into 48 canonical
types across ten corpora; adopt its mapping and record every deviation. Sources to harmonise:
MEDDOCAN 29 types · i2b2 18 PHI classes · CodEAlltag's hierarchy (ACTOR{ORG, PERSON{FAMILY,
GIVEN{FEMALE, MALE}}, USER}, DATE, FID{PASS, UFID}, LOC{STREET, STREETNO, CITY, ZIP}, ADD{EMAIL,
PHONE, URL}) · TAB's semantic categories · OntoNotes 18 NE types · REDACT 51 types.

`entity_id` and `subject_id` are what make the stability metrics computable; every converter must
either populate them or declare them null, and a corpus with both null cannot enter a stability cell.

---

## 4. What the meta corpus answers that no single corpus can

| open question | how the meta corpus settles it |
|---|---|
| Is the full `A×B×C×D×E` factorial affordable? | one format means one harness; corpus stops being a cost multiplier on engineering and becomes a data dimension |
| Which languages carry enough PII density? | measurable directly once every corpus reports density in the same schema |
| Does the policy dominate the technique (H1)? | testable on T1 with real name distributions, and separately on T4/T5 — if the answer differs by tier, that is a finding about the field's benchmarks |
| Does detection recall dominate leakage (H2)? | the gold-span oracle is available on every member except E3C |
| Does document-randomisation cost cross-document tasks (H3)? | i2b2 (patient timelines) and Enron (threads) are the two corpora where it can actually hurt |

---

## 5. Check results (run 2026-09-06)

All four pre-acquisition checks were run. TAB and CodEAlltag were cloned and inspected directly;
i2b2 was settled from the corpus paper.

### ✅ TAB carries the legal task itself — no join needed

TAB's `meta` block already contains the ECHR articles, so the downstream task ships with the corpus:

| | |
|---|---|
| documents | **1,268** (1,014 train / dev / test), all with `meta.articles` and `meta.applicant` |
| task labels | **30 distinct articles**, multi-label; **752 of 1,268 documents carry more than one** |
| label skew | Art. 6 → 792 docs · Art. 41 → 578 · Art. 5 → 234 · Art. 29 → 200 · long tail to n=1 |
| spread | **17 respondent countries**, judgments **1975–2017** |
| `doc_id` | the **HUDOC ITEMID** (e.g. `001-90194`) — so a join to the Chalkidis/LexGLUE ECHR set (~11.5 k cases, same HUDOC source) is still available |
| annotators | 994 documents single-annotated; **274 have 2–10 annotators** → inter-annotator variation is measurable on the oracle itself |
| entity types | DATETIME 53,668 · ORG 40,695 · **PERSON 24,322** · **LOC 9,982** · DEM 8,683 · MISC 7,044 · CODE 6,471 · QUANTITY 4,141 |
| identifier class | QUASI 98,244 · NO_MASK 50,023 · **DIRECT 6,739** |
| co-reference | `entity_id` chains present per annotator |

**One caveat.** The README calls `meta.articles` the *"legal articles involved"* — that is ECtHR_A
semantics (allegedly violated), not ECtHR_B (actually violated). For an outcome-prediction task
rather than an issue-classification task, join on `doc_id` to the Chalkidis set. Either way the legal
task exists.

PERSON (24,322) and LOC (9,982) are exactly the two classes `PLAN.md` singles out as carrying the
stability requirement, and they are co-reference-chained. This is the strongest single member.

### ✅ i2b2 / n2c2 2014 — Track 1 and Track 2 are the same records

Confirmed from the corpus paper: the records *"were selected for use in Track 2 … identification of
risk factors for Coronary Artery Disease in diabetic patients"*, and *"the resulting annotations were
used both to de-identify the data and to set the gold standard for the de-identification track"*.

**1,304 records · 296 patients · 805,118 tokens**, real longitudinal clinical narratives, PHI replaced
by realistic surrogates (automatic, then manually corrected), double-annotated with arbitration.

That makes it the strongest clinical cell in the design: real longitudinal documents, gold PHI, and a
downstream clinical task **on identical documents** — the only member where the utility axis and the
detection axis cannot be confounded by using different data.

### ❌ CodEAlltag ships no annotations

`CodEAlltag_pS` contains `emails/`, `LICENSE`, `README.md` and nothing else: **800 plain `.txt` files,
zero annotation files** of any format. The manually annotated set described in the paper
(CodE Alltag<sub>S+d</sub>, 1,390 e-mails) is not what was released. So CodEAlltag is T2 text
**without gold spans** and cannot supply the oracle level of axis D.

What the release *does* give, found while checking (all CC-BY-SA-4.0 unless noted):

| repository | what it is |
|---|---|
| `CodEAlltag_pS` | 800 pseudonymised donated e-mails, plain text |
| `CodEAlltag_pXL_{EVENTS, FINANCE, GERMAN, MOVIES, PHILOSOPHY, TEENS, TRAVELS}` | seven topical segments, ~590 MB total → **7-class topic classification task** |
| `CodEAlltag_formality_scores` | **formality scores** → a second German e-mail task, regression or ordinal |
| `privacy_tagger` (**MIT**) | the authors' own flair-based German e-mail PII tagger, fine-tuned on 3,000 pseudonymised CodEAlltag e-mails; model 2.6 GB, hosted off-repo. A strong **domain-matched detector for axis D** — but a detector, not gold |

No surrogate inventory or gazetteer is published, so AM's rule-based recovery route is not directly
available for this corpus. Three ways forward, and they are not exclusive: **ask Eder / Krieg-Holz /
Hahn for the annotated S+d subset**; use `privacy_tagger` as a strong domain detector and accept
detector-only cells here; or keep CodEAlltag purely as a utility-task corpus and let German gold
spans come from CARDIO:DE.

### ✅ Licence resolved — CC-BY-SA-4.0, not NC

The `LICENSE` file in every CodEAlltag repository is **Attribution-ShareAlike 4.0 International**. The
CC-BY-NC seen earlier applies to the ELRA *proceedings paper*, not to the corpus. No NC constraint.

**But ShareAlike is now the binding constraint on what we can release** — see §6.

---

## 6. Distribution: the meta corpus must be a build recipe, not a dataset

The members' licences cannot be combined into one redistributable artefact:

| licence | members |
|---|---|
| MIT | TAB |
| CC-BY-4.0 | MEDDOCAN · MedDeID |
| **CC-BY-SA-4.0 (copyleft)** | CodEAlltag · REDACT |
| custom, academic free / commercial separate | AI4Privacy |
| **DUA, per individual user** | i2b2/n2c2 · CARDIO:DE · BRONCO150 |
| LDC licence | OntoNotes |
| public | Enron |

A single distributed blob would have to satisfy ShareAlike *and* three separate DUAs at once, which
is not possible. So the deliverable is:

- **converters** — one per source, source format → the §3 schema;
- **a manifest** — exact versions, URLs, DOIs, splits and checksums;
- **a builder** that assembles the meta corpus locally once the user has obtained each source under
  their own agreement;
- **derived artefacts only** where the licence permits — statistics, span offsets, mappings, results.

This is the same pattern PIIBench and BigBIO use, and it should be stated in `PLAN.md` §Deliverables
so the release plan is not built on an assumption that turns out to be illegal.

---

## 7. Still open

- **Balance means capping.** Enron has ~500 k messages and TAB has 1,268 documents. A balanced meta
  corpus requires sampling the large members. **This is a design decision for AM, not a cost saving**
  — `CLAUDE.md` §1 forbids reducing a corpus to save time, and a deliberate balance criterion is a
  different thing. It must be written down as a stated rule (per-corpus cap? per-cell cap? equal
  token budget per language?) before any sampling happens.
- **Enron is still undecided** (`candidates.md` §Open question) — load-bearing twice over: one of only
  two T1 corpora with a natural name distribution, and one of only two with cross-document identity.
- **Ask the CodEAlltag authors** for the annotated S+d subset (see above).
- **OntoNotes is free to non-members** from LDC (no licence fee, shipping/handling only) — confirm
  FAU's LDC status and whether the download route is now electronic.
- **PIIBench release location not yet found**; needed both as a corpus slice and as the taxonomy.
