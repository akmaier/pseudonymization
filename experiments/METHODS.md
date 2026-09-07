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

**Recommendation: the entity key is the normalised surface form, with the normaliser itself a
reported setting** (`none` / `casefold` / `casefold+titles+initials`). The **gold co-reference id is
the ground truth** the fragmentation metric is scored against, never the key. That way fragmentation
is a measured property of the function, not an artefact of being handed the answer.

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

**AM's call.** I would run **AES-SIV as the axis-B level** (it is the honest comparator to HMAC) and
note FF1 as related work, because FF1's format preservation is really a *surrogate form* property and
would confound B with C.

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

1. **Entity key** — normalised surface form, with the normaliser as a reported setting? (§2)
2. **Encryption mode** — AES-SIV as the axis-B level, FF1 noted as related work? (§3)
3. **Collision policy for the mapping table** — draw-without-replacement (no collisions, so ENISA's
   warning is untestable) or draw-with-replacement (collisions occur and are measured)? Measuring
   them is the only way to test ENISA's claim, so I would run **both** as two sub-levels and report
   the difference. (§7)
4. **Balance / capping rule** — still open from the meta corpus, and it gates the corpus side but not
   §1–§6.

Nothing else is blocked.
