# Methods — what the engine has to be

The independent variable of this study is the pseudonymisation function and policy. This file
specifies what that means concretely, what has to be built, and what has to be decided first.
`PLAN.md` §Factors is the specification; nothing here changes it.

---

## 1. The factorisation that makes A × B × C cheap

Axes A, B and C look like 3 × 5 × 3 = 45 separate implementations. They are not. They compose:

```
mention ──▶ entity key ──▶ scope key ──▶ pseudonym index ──▶ surface form
             (§2)          (A: policy)   (B: technique)      (C: surrogate form)
```

- **A, the policy, is a scoping rule.** It says what the key is qualified by, and nothing else:

  | policy | scope key | consequence |
  |---|---|---|
  | deterministic | `(entity_key)` | one pseudonym corpus-wide |
  | document-randomised | `(entity_key, doc_id)` | one pseudonym per document, differs across documents |
  | fully-randomised | `(entity_key, mention_id)` | every mention differs |

- **B, the technique, is a keyed map** from scope key to an index. Every one of the five reduces to
  `scope_key → integer`.
- **C, the surrogate form, is a rendering** of that index into a surface string, given the entity type
  and (for attribute-matched) the attributes of the original.

So the engine is three small interfaces, not forty-five pipelines. One consequence worth stating in
the paper: **the policy is the only axis that changes what is linkable**; B and C cannot make a
fully-randomised corpus linkable, and cannot make a deterministic one unlinkable.

---

## 2. The entity key — the decision everything else rests on

*What counts as "the same entity"?* Three candidates, and the choice decides whether the stability
metrics measure anything:

| option | effect |
|---|---|
| **gold co-reference id** | fragmentation is **zero by construction** under a deterministic policy. Measures nothing; useful only as an upper bound |
| **raw surface form** | *Dr. Weber*, *Weber*, *F. Weber* are three keys → three pseudonyms. This is what a real deployed system does, and it is exactly the failure `PLAN.md` §Measurements/2 wants to quantify |
| **normalised surface form** | a middle position: casefolding, title stripping, initial expansion. Realistic for a good implementation |

**Decided (AM, 2026-09-07): choose from the data.** Measured on TAB's gold co-reference chains —
8,701 PERSON chains over 15,955 mentions, 3,603 LOC chains over 6,436 mentions, collisions counted
within document because TAB's `entity_id` is document-scoped:

| normaliser | fragmentation (chains split) | collisions | | LOC split | LOC collisions |
|---|---:|---:|---|---:|---:|
| N0 raw surface form | 11.8 % | 0.00 % | | 0.7 % | 0.00 % |
| N1 + casefold | 11.8 % | 0.10 % | | 0.7 % | 0.28 % |
| **N2 + strip titles & punctuation** | **9.8 %** | **2.32 %** | | 0.7 % | 0.28 % |
| N3 + drop single-letter initials | 5.2 % | 4.70 % | | 0.7 % | 0.30 % |
| N4 surname only | 1.4 % | 9.02 % | | 0.5 % | 4.54 % |

**The normaliser alone traces a collision–fragmentation frontier, monotonically, before any
cryptography is involved.** That is the paper's thesis in miniature and it is worth reporting in its
own right: the trade-off practitioners attribute to the choice of function is already present in the
key-construction step nobody documents.

Two further observations from the same measurement:

- **11.8 % of PERSON chains carry more than one surface form** (mean 1.13 distinct forms, up to 10),
  so fragmentation is a real phenomenon on real text, not a hypothetical.
- **LOC barely varies — 0.7 %.** Place names are written the same way each time, so the LOC arm is
  dominated by *collisions* and the PERSON arm by *fragmentation*. The two entity types that
  `PLAN.md` singles out for stability fail in opposite directions, which no prior work reports.

**Default: N2** — casefold, strip punctuation and honorifics — which halves nothing but removes the
free 2 % of fragmentation that pure casefolding leaves on the table, at 2.3 % collisions. **The
normaliser is run as a reported sub-axis N0–N4**, since it costs almost nothing and traces the
frontier directly.

Caveat to carry into the paper: these collision figures are **within document**. Corpus-wide, under a
deterministic policy, collisions will be substantially higher — that measurement needs a corpus with
cross-document entity identity, i.e. Enron.

This also separates the two causes of fragmentation, which no prior work does:

- **detector-induced** — a missed or truncated span produces a different surface form;
- **function-induced** — the key normaliser fails to unify two forms of the same name.

The gold-span level of axis D isolates the second from the first.

---

## 3. What each technique needs

| technique | mechanism | what it needs | note |
|---|---|---|---|
| **counter** | ordinal per `(type, scope)` | an iteration order | the order **is** the leak ENISA names: the ordinal carries document order. Iteration order must be fixed and reported |
| **RNG + mapping table** | random draw, stored | a table store, a **collision policy** | ENISA flags collisions; to measure them we need a mode that does *not* redraw. See §7 |
| **cryptographic hash** | `SHA-256(scope_key) mod N` | nothing | unkeyed, so **A1 is defined against it** |
| **HMAC** | `HMAC-SHA256(k, scope_key) mod N` | a secret key per run | keyed, so A1 needs the key; A2 does not |
| **symmetric encryption** | `E_k(scope_key) mod N` | a **deterministic** mode | see below |

**The encryption mode is a real decision.** AES-CBC/GCM with a random IV is not deterministic, so it
would destroy stability outright and the cell would be meaningless. Two defensible choices:

- **AES-SIV** (RFC 5297) — deterministic authenticated encryption. Simple, standard, and behaves like
  a keyed permutation for our purposes. Effectively indistinguishable from HMAC in what it leaks,
  which is itself the point H1 makes.
- **Format-preserving encryption, FF1** (NIST SP 800-38G) — encrypts within an alphabet, so a name
  can map to a name-shaped string. Closer to what practitioners mean by "encrypt the identifier",
  and it interacts with axis C in an interesting way.

**Decided (AM, 2026-09-07): AES-SIV is the axis-B level; FF1 is cited as related work.** FF1's
format preservation is really a surrogate-form property and would confound B with C. AES-SIV is
available in `cryptography` (verified 49.0.0, `AESSIV`, deterministic output confirmed).

---

## 4. The one external dependency: surrogate inventories

Axis C levels 2 and 3 cannot be built from the corpora. They need name and place inventories **with
frequencies and attributes**, per language:

| need | for | must carry |
|---|---|---|
| given names | PERSON | **gender**, **locale**, frequency |
| surnames | PERSON | locale, frequency |
| cities, regions, streets | LOC | country, population/frequency |
| organisations | ORG | locale |
| date/number generators | DATE, CODE | format templates |

Frequencies are not optional: **H4 is about frequency and attribute preservation**, and **A2 consumes
the frequency distribution**, so an unweighted name list cannot test either.

Candidate public sources — *to verify licences before use, none acquired yet*: US Census surname
frequencies, SSA given names by year and sex (public domain, en); GeoNames (CC-BY, places, all
languages); Destatis / regional registry first-name lists (de); INE (es); CBS (nl). Chinese and
Arabic inventories for the OntoNotes arm need a separate look and are the likely weak point.

**Attribute-matched surrogates also need an attribute inferencer** for the original — the gender of a
given name, the country of a place — which is the same inventory read backwards.

---

## 5. Stability metrics, defined so they mean something

Both are functions of the mapping plus gold co-reference. Both must be **reported relative to the
policy**, because what is a failure under one policy is the definition of another:

| metric | definition | deterministic | document-randomised | fully-randomised |
|---|---|---|---|---|
| **collision** | distinct gold entities sharing a pseudonym within a scope | a defect | a defect | meaningless |
| **fragmentation, within scope** | one gold entity, several pseudonyms inside one scope | a defect | a defect | by design |
| **drift, across scope** | one gold entity, different pseudonyms in different documents | a defect | **by design** | by design |

Reporting a single "fragmentation rate" across policies would be a category error. Three numbers,
each labelled by whether it is a defect or the policy working as specified.

Both need co-reference-resolved gold, so they are computable on **TAB** and **OntoNotes** (within
document) and on **Enron** (across documents, via mailbox identity). That is the constraint that
decided the meta corpus.

---

## 6. What the attacks need

| attack | needs | defined against |
|---|---|---|
| **A1 dictionary** | the §4 inventory; the *function*, applied by the attacker | **unkeyed** techniques only — hash, and counter trivially. HMAC and AES require the key, so A1 not succeeding there is a fact about the threat model, not a result. State that explicitly |
| **A2 frequency** | pseudonym frequency distribution + a reference name-frequency distribution | **every** technique, including keyed ones. This is H1 |
| **A3 linkage** | co-occurrence graph + an auxiliary record | Enron's ~184-employee org chart is the only real auxiliary we have |
| **A4 LLM re-identification** | the NHR@FAU gateway (verified, 10 chat models, free) | scored as recovery of the corpus surface form, stratified by public-figure status — see the Enron safeguards in `PLAN.md` |

A1 and A2 report **inversion rate against name frequency and name length**, which is the curve the
hash-vs-HMAC question actually turns on.

---

## 7. Module layout and build order

Everything in §1–§6 except the detectors is **corpus-free** and unit-testable on synthetic input.
That is the critical path while corpus access is in flight.

```
experiments/
  pseudonymise/
    keys.py         entity key + normalisers            (§2)
    scope.py        axis A: three scoping rules         (§1)
    techniques.py   axis B: counter, table, hash, HMAC, AES-SIV
    surrogates.py   axis C: tag, realistic, attribute-matched
    inventory.py    gazetteer loading, frequency + attribute lookup (§4)
    pipeline.py     spans + policy + technique + form -> text, mapping
  metrics/
    stability.py    collision, fragmentation, drift      (§5)
    detection.py    P/R/F1 per type, PERSON and LOCATION separately
  attacks/
    a1_dictionary.py  a2_frequency.py  a3_linkage.py  a4_llm.py
  detectors/        Presidio, GLiNER/XLM-R, LLM, ensemble union+vote, gold
  convert/          one converter per corpus -> the metacorpus schema
  configs/          one YAML per cell; seed + key material referenced, never inlined
```

**Order:** (1) keys + scope + techniques + tag surrogates, tested on synthetic entities; (2) stability
metrics against a hand-built gold; (3) A2, then A1 — A2 is where H1 lives and needs no inventory
beyond frequencies; (4) inventories and the realistic/attribute-matched forms; (5) converters, TAB
first; (6) detectors; (7) A3, A4; (8) utility.

Every run writes a manifest: config hash, seed, key id, library versions, corpus versions, commit.

---

## 8. Decisions needed before coding starts

1. ~~Entity key~~ — **decided: N2 default, N0–N4 as a reported sub-axis**, chosen from the TAB measurement in §2.
2. ~~Encryption mode~~ — **decided: AES-SIV**, FF1 cited.
3. ~~Collision policy for the mapping table~~ — **decided: both**, as two sub-levels.
   Draw-without-replacement makes ENISA's collision warning untestable; draw-with-replacement lets it
   be measured. Running both and reporting the difference is the only way to test the claim.
4. **Balance / capping rule** — still open from the meta corpus. Gates the corpus side, not §1–§6.

Decisions 1–3 are settled. Only the capping rule remains, and it does not block the engine.

---

## 9. Concrete methods, branch by branch

### 9.1 Detection / de-identification (axis D)

The detector is **not** the independent variable, so the levels are chosen to span the families the
field uses, not to be exhaustive.

| level | method | notes |
|---|---|---|
| rule-based | **Microsoft Presidio** — regex + checksum recognisers over a spaCy NER backbone | REDACT reports rule-based recall **0.07** on HIGH-sensitivity entities; it is the floor, and belongs in the paper as such |
| fine-tuned NER | **XLM-RoBERTa-large** token classifier, fine-tuned per language on the corpus's own train split | the standard multilingual baseline; one model per language arm |
| zero-shot NER | **GLiNER** (and GLiNER2-PII, arXiv 2605.09973) | covers entity types with no training data, which matters for the long tail of 48 types |
| domain-specific | **CodEAlltag `privacy_tagger`** (flair, German e-mail) | the authors' own tagger, already on disk — a strong in-domain baseline for the German e-mail arm and an honest comparator |
| LLM, single | via the **NHR@FAU gateway**, free: `gpt-oss-120b`, `Qwen3.6-35B-A3B`, `RedHatAI/gemma-4-31B`, `Mistral-Small-3.2-24B`, `DeepSeek-V4-Flash-0731` | JSON span extraction with offset validation and retry; at least two distinct models run individually, per `PLAN.md` axis D |
| **ensemble** | union **and** majority vote over {Presidio, XLM-R, GLiNER, ≥2 LLMs} | reported separately — union maximises recall, vote maximises precision, and the gap between them is the privacy/utility trade-off appearing at the detector level |
| **gold spans** | oracle | separates detector error from pseudonymisation error; without it everything downstream is confounded by a 0.40-F1 name detector |

Spans are normalised to the meta-corpus schema (character offsets, harmonised type) before anything
downstream sees them, so detectors are interchangeable by construction.

**Combination is its own axis (D′), because the in-house ensemble used LLMs only.** Detectors rarely
agree on boundaries, so agreement is defined by **overlap clustering**: same-type spans that overlap
transitively form one cluster, and the rule decides whether it survives and which span represents it.
Treating *Dr. Weber* and *Weber* as disagreement would understate agreement badly.

| rule | keeps a cluster when | representative | trades toward |
|---|---|---|---|
| **union** | any detector found it | widest span | recall — the privacy direction |
| **vote(k)** | ≥ k detectors agree (default: strict majority) | most-agreed span | balance |
| **intersection** | all detectors agree | narrowest span | precision — the utility direction |
| **weighted vote** | summed detector weights ≥ threshold | most-agreed span | whichever detector is trusted |
| **cascade** | ordered fallback: later detectors fill gaps only | first found | cost |

**Do we need forced alignment, as in ROVER?** Fiscus's ROVER (1997) aligns recognisers' word
sequences into a transition network by dynamic programming before voting, because ASR systems emit
*unaligned* sequences over a reference nobody has. Our detectors all read the same string and emit
character offsets into it, so **the common coordinate system is given and no dynamic programming is
needed**. That is the one respect in which this problem is easier than ASR's.

What ROVER does *after* aligning is still needed, and span-level clustering only does part of it. So
axis D′ carries **two families**, and which wins is itself a result:

| | span-level rules | **token-level voting** (the ROVER analogue) |
|---|---|---|
| unit | whole spans, clustered by overlap | BIO labels on a shared tokenisation |
| partial credit | none — three tokens of a four-token name right counts as disagreement | yes, per token |
| type disagreement | per-type clustering splits the evidence into two minorities and can drop both | **presence pooled first, type settled second** |
| boundaries | picked by a heuristic (widest / narrowest / most-agreed) | decided by the vote |
| cost | cheap | a tokenisation pass per document |

The two-stage vote matters for a pseudonymisation study specifically. Four detectors split two
PERSON / two ORG all agree an entity is present; per-type clustering sees two minorities and
discards both, losing an entity that every detector saw. **A missed entity leaks; a mislabelled one
is still replaced** — so presence must be decided before type.

Two further alignment issues that ROVER's framing surfaces and that we do have to handle:

- **Single-link chaining.** Transitive overlap merges `A(0,10)`, `B(8,20)`, `C(18,30)` into one
  cluster although A and C are disjoint, which on dense text can fuse two adjacent people. An IoU
  linkage criterion is available as a reported setting.
- **Grounding LLM output.** A language model returns *text*, not offsets, and normalises whitespace,
  quotation marks and diacritics on the way. A literal `str.find` silently drops correct spans and
  depresses that detector's recall, corrupting the whole ensemble comparison. `ground_snippets()`
  matches exactly first, then against a Unicode-folded, whitespace-collapsed view, mapping hits back
  to original offsets. **This is the one place a real alignment problem remains.**

`combination_grid()` enumerates (subset, rule) pairs and takes a `require=` argument, which is how
**LLMs-only** and **LLMs + ≥1 classical detector** are compared on equal footing rather than by
anecdote. Weighted vote is where a classical detector can earn its place: a high-precision rule-based
recogniser for structured identifiers can outweigh several language models that disagree about a name
boundary.

### 9.2 Pseudonymisation (axes A · B · C)

| axis | level | implementation |
|---|---|---|
| **A** | deterministic · document-randomised · fully-randomised | scope key `(entity_key)` / `(entity_key, doc_id)` / `(entity_key, mention_id)` — §1 |
| **B** | counter | ordinal per `(type, scope)`, fixed iteration order, order reported |
| | RNG + mapping table | seeded `numpy.random.Generator`; table in SQLite; **two sub-levels**, draw-with- and draw-without-replacement |
| | cryptographic hash | `SHA-256(scope_key)` → index |
| | HMAC | `HMAC-SHA256(key, scope_key)` → index |
| | symmetric encryption | **AES-SIV**, `cryptography.hazmat.primitives.ciphers.aead.AESSIV`, 256-bit key, entity type as associated data |
| **C** | opaque tag | `[PERSON_1]`, index only |
| | realistic surrogate | index → inventory lookup by type and language |
| | attribute-matched | index → inventory lookup **stratified** by inferred gender / locale / frequency band |
| **key** | N0–N4 normaliser | reported sub-axis; **N2 default** (§2) |

Key material lives in `config/`, never in code or results; each run records a key id, not a key.

### 9.3 Stability

Pure set operations over `gold chain → entity keys → pseudonyms`, no learning:

- **collision** — distinct gold chains sharing a pseudonym within a scope
- **fragmentation** — one gold chain, several pseudonyms within a scope
- **drift** — one gold chain, different pseudonyms across scopes

Reported per entity type, PERSON and LOC separately, and labelled per policy as defect or as
specified behaviour (§5). Bootstrap confidence intervals over documents.

### 9.4 Utility — frozen models only (AM, 2026-09-08)

**No training anywhere in the study.** Not as an economy: the relevant deployment pattern for this
venue is a foundation model prompted over a corpus, not an encoder fine-tuned on one, so the honest
measurement is degradation at fixed weights.

| corpus | task | how | metric |
|---|---|---|---|
| TAB / ECHR | article classification, 30 labels, ships in `meta.articles` | zero-shot, ≥2 gateway models, fixed prompt | micro / macro F1 |
| Enron | folder classification (Klimt & Yang 2004) | zero-shot, same protocol | accuracy, macro F1 |
| TAB, OntoNotes | **co-reference resolution** | frozen resolver, original vs pseudonymised | CoNLL F1 delta |
| all | NER agreement | frozen multilingual NER on both versions | span F1 between versions |
| all | **semantic drift** | cosine displacement of document embeddings, `multilingual-e5-large` | mean cosine delta |
| all | **fluency** | perplexity under one frozen LM | Δ perplexity |
| CARDIO:DE, BRONCO *(pending)* | medication IE, section classes, ICD/OPS/ATC | zero-shot | F1 |

Three consequences worth stating:

- **Co-reference is promoted from proxy to primary.** Fragmentation is chain breakage, so a
  resolver's F1 drop measures the utility cost of the exact failure the stability metrics count, on
  the same documents — binding measurement 2 to measurement 3. Nothing in the literature does that.
- **The cluster stops being a bottleneck.** No checkpoints, so the 95 %-full disk does not bind; no
  long jobs, so the 24 h wall clock does not bind; the LLM work runs on the free gateway, so the
  GPUs are needed only for frozen NER, co-reference and perplexity — hours, not weeks.
- **Every cell becomes inference**, so utility can be measured across the *whole* factorial rather
  than a sampled corner of it. Refusing to train widens the design rather than narrowing it.

**Memorisation is a confound here and a result in A4.** A frozen model may recognise an ECHR case or
an Enron thread and answer from memory rather than from the text. Utility scores would then measure
recall of training data. Control: stratify by the same public-figure split A4 uses, and run a
no-context condition. Handling it in A4 but not here would be inconsistent.

**Out of scope, and said so:** whether a model retrained on pseudonymised text recovers. If it does,
the field's assumption that de-identification costs utility is domain shift rather than information
loss. It requires training by definition and belongs in future work.

### 9.5 Leakage

| attack | method | metric |
|---|---|---|
| **A1 dictionary** | enumerate the §4 inventory, apply the *public* function, match | inversion rate as a function of **name frequency** and **name length**. Defined only against unkeyed techniques — hash and counter; HMAC and AES-SIV need the key, and saying so is part of the threat model, not a null result |
| **A2 frequency** | rank pseudonyms by corpus frequency, rank candidate names by reference frequency, align | top-1 / top-5 accuracy; Spearman ρ; **Hungarian matching** for the optimal global assignment. Applies to **all five** techniques — this is H1 |
| **A3 linkage** | co-occurrence graph over pseudonymised documents, matched to an auxiliary record | seeded graph matching; precision@k of recovered pairs. Auxiliary: Enron's ~184-employee org chart, the only real one we have |
| **A4 LLM re-identification** | pseudonymised document → gateway LLM → "who is this?", with and without auxiliary context | recovery of the **corpus surface form**, never external facts; **stratified by public-figure status**, which doubles as a memorisation test against arXiv 2602.20580 |

### 9.6 Harness

One YAML per cell; every run emits a manifest with config hash, seed, key id, corpus versions,
library versions and the commit. Slurm array jobs over cells, checkpointed against the 24 h wall
clock. Results are parquet on disk, never numbers in prose.


---

## 10. Which models need training — none on the defender side

Checked on the HuggingFace API, 2026-09-08. Every level of every axis has a public checkpoint, so
the study runs without training a single defender model.

| role | model | monthly downloads | trained by us? |
|---|---|---:|---|
| rule-based detector | Presidio + spaCy backbone | — | no |
| zero-shot NER | `urchade/gliner_multi-v2.1` | 21,911 | no |
| zero-shot PII NER | `urchade/gliner_multi_pii-v1` | 57,043 | no |
| **"fine-tuned NER" family** | `obi/deid_roberta_i2b2` | 421,833 | **no — public checkpoint** |
| clinical de-ID | `StanfordAIMI/stanford-deidentifier-base` | 1,833,628 | no |
| multilingual NER | `Davlan/xlm-roberta-large-ner-hrl` | 46,221 | no |
| domain-specific | CodEAlltag `privacy_tagger` (flair) | — | no, already on disk |
| LLM detectors, A4, zero-shot tasks | NHR@FAU gateway, 10 chat models | — | no |
| **co-reference** | `biu-nlp/lingmess-coref` | 64,082 | no |
| embeddings / semantic drift | `intfloat/multilingual-e5-large` | 6,981,685 | no |
| perplexity | `Qwen/Qwen2.5-0.5B` | 1,678,815 | no |

**Filling the "fine-tuned NER" level with a public checkpoint is better than training one, not just
cheaper.** A detector fine-tuned on a corpus's own train split has *seen the entities we then try to
protect*, so its recall on that corpus is inflated in a way that does not transfer — the measurement
would flatter the detector and, through it, the whole downstream pipeline. Off-the-shelf checkpoints
remove that confound, and they are also what a practitioner actually downloads.

`PLAN.md` axis D should therefore read "a publicly released fine-tuned NER" rather than "fine-tuned
XLM-R", which is a change of meaning worth being explicit about.

## 11. The exception: the attacker (AM, 2026-09-08 — proposed)

> "The only thing worth training might be an attacker model."

This is the right asymmetry, and it is a principle worth stating in the paper:

> **Frozen defenders, trained attackers.** The defence is measured as deployed, because that is what
> practitioners run. The attack is made as strong as we can make it, because a leakage number is only
> meaningful against the best adversary available — under-powering the adversary overstates privacy.

None of A1–A4 uses a trained model, so every leakage number we have is a *lower bound* on what an
adversary could do. The obvious gap is that all four attack **names and their distribution**, and
none of them attacks the thing pseudonymisation cannot touch.

### Proposed A5 — stylometric re-identification

Train an authorship attributor on pseudonymised text and ask whether it still identifies the author.

- **Why it belongs here.** CodEAlltag was built for *forensic linguistics*, and Enron carries ~150
  mailbox owners as labels. The corpora were made for this question.
- **Why it is a different channel.** A1 inverts a function, A2 exploits frequency, A3 exploits
  co-occurrence, A4 exploits an LLM's world knowledge. **A5 exploits style, which no pseudonymisation
  policy modifies at all.** Fully-randomised pseudonymisation defeats A2 completely and should leave
  A5 untouched — a prediction that separates the axes cleanly.
- **Why the result matters either way.** If style survives, then *pseudonymisation removes names but
  not identity*, and the policy axis — which dominates every other attack — is irrelevant to this
  one. That is the sharpest possible statement of the paper's thesis about what pseudonymisation
  does and does not buy.
- **Cost.** The classical stylometry baseline is character *n*-grams plus a linear classifier: CPU
  only, minutes, no GPU. A transformer attacker can be added if the linear one is not already
  decisive.

Predicted shape: A5 accuracy roughly flat across all three policies and all five techniques, while
A2 collapses from 0.201 to 0.000 across the same axis.
