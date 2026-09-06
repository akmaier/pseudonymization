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
| **T2** | **realistic surrogates, consistently substituted** | natural *placement* and near-natural distribution; and because the substitution was rule-based from a known inventory, spans are recoverable by dictionary — **gold spans for free** | i2b2/n2c2 2014 · CodEAlltag |
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
| **TAB / ECHR** | en | Latin | legal judgments | ECtHR **article-violation prediction** (join to LexGLUE ECtHR_A/B on case id) | **co-reference** (`entity_id`), DIRECT/QUASI/NO_MASK | T1 |
| **Enron** | en | Latin | corporate e-mail | **folder classification** (Klimt & Yang 2004) | **cross-document**: sender/recipient identity from headers; org chart (~184 employees) as A3 auxiliary | T1 |
| **OntoNotes 5.0** | en, **zh**, **ar** | Latin, Han, Arabic | news · broadcast · weblog · telephone speech · usenet | **co-reference resolution + NER** (the task pseudonymisation most directly damages) | **co-reference**, 18 NE types | T1 |
| **i2b2 / n2c2 2014** | en | Latin | clinical, **longitudinal** | heart-disease **risk-factor extraction** (Track 2, same records — *verify*) | **cross-document**: 1,304 records over **296 patients** | T2 |
| **CodEAlltag** | de | Latin | e-mail (S+d donated) · usenet (XL) | **topic classification** from the XL segments; formality (*verify release*) | manual gold spans on S+d (1,390 mails); consistent surrogates | T2 |
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

## 5. Open, and needing a decision or a check

- **Balance means capping.** Enron has ~500 k messages and TAB has 1,268 documents. A balanced meta
  corpus requires sampling the large members. **This is a design decision for AM, not a cost saving**
  — `CLAUDE.md` §1 forbids reducing a corpus to save time, and a deliberate balance criterion is a
  different thing. It must be written down as a stated rule (per-corpus cap? per-cell cap? equal
  token budget per language?) before any sampling happens.
- **Enron is still undecided** (`candidates.md` §Open question) — and it is now load-bearing twice
  over: it is one of only two T1 corpora with a natural name distribution, and one of only two with
  cross-document identity.
- **Verify:** does TAB's 1,268 ECHR cases join to LexGLUE ECtHR_A/B by case id? Without the join
  there is no legal downstream task.
- **Verify:** are i2b2 2014 Track 1 and Track 2 the same documents? If yes, the strongest cell in the
  design — gold PHI *and* a clinical task on identical longitudinal records.
- **Verify:** does the CodEAlltag public release ship the manual span annotations, or only the
  substituted text? The GitHub repo shows `emails/`, `LICENSE`, `README.md` and nothing that looks
  like standoff annotation. Without the spans it is T2 text without gold.
- **Licence conflict to resolve:** the CodEAlltag 2.0 paper is ELRA **CC-BY-NC**; the GitHub
  repository footer shows **CC-BY-SA-4.0**. NC would constrain what we can release.
- **OntoNotes is free to non-members** from LDC (no licence fee, shipping/handling only) — confirm
  FAU's LDC status and whether the download route is now electronic.
- **PIIBench release location not yet found**; needed both as a corpus slice and as the taxonomy.
