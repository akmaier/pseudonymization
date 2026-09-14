# Experiment plan

**This is the only plan.** It carries the standards the work is measured against, the argument, the
hypotheses, what is to be run, on what, measured how, and with which statistics. No other document in
this repository specifies anything (§1).

Last updated 2026-09-10. Every decision is attributed and dated; nothing here is a default.

---

## 1. The rule above the design

### The design is AM's

**No axis, level, corpus, metric, attack or corpus role is added, removed or redefined without AM's
explicit decision, recorded here with a date.** This binds in both directions: inventing a factor is
as much a change as dropping one.

If a cell cannot be run because the data or the service does not exist — corpus unobtainable, licence
refused, annotation absent, backend down — **stop, and record it in §17**, naming the cell and the
obstacle. Do not substitute, do not silently narrow, do not run "a representative subset".

Sampling is part of the design, not an exception to it: rates are fixed before a run and recorded
with every result (§13).

### This file is not edited without AM's explicit approval

**Approval is given before the edit, never after.** An agent proposes the change — quoting the
passage, stating what is wrong, offering the replacement — and then waits. It does not edit and
report.

**Approval is never assumed from a statement by AM.** It is not implied by AM asking about a passage,
criticising it, calling it outdated or wrong, approving a different change that resembles this one,
or saying anything from which an agent infers consent. Approval is AM approving *this* change. If
AM's answer is ambiguous, ask again; do not resolve the ambiguity in favour of editing.

### There is one plan document

**This one. No further plan, specification, design note or requirements document is to be created**,
under any name, in any directory. Requirements written elsewhere drift out of step and then
contradict this file — which is what happened to `PLAN.md` and to `data/metacorpus.md`, and is how an
invented axis and a five-level tier taxonomy came to sit in the design for three days.

---

## 2. Standards

| | |
|---|---|
| **DIN EN ISO 25237:2026-06** | *Medizinische Informatik — Pseudonymisierung* (ISO/DIS 25237). `10.31030/3696721` — a **2026 revision** of the health pseudonymisation standard |
| DIN EN ISO 25237:2017-05 | the superseded edition, `10.31030/2555889`; BSI equivalent *Health informatics. Pseudonymization* `10.3403/30285709` |
| **ENISA 2021** | *Data Pseudonymisation: Advanced Techniques and Use Cases* — downloaded and read; the practical European reference |
| ENISA 2019 | *Pseudonymisation techniques and best practices* |
| ISO/IEC 20889 | privacy-enhancing de-identification terminology and technique classification — **not directly verified**, iso.org returns 403 to scripted access |
| GDPR Art. 4(5) | the legal definition pseudonymisation has to satisfy |

Publishing against a standard revised in **June 2026** is a good position for a workshop paper.

## 3. ENISA's technique taxonomy — the claim the paper tests

ENISA's 2021 report ranks the five techniques qualitatively, in §"pseudonymisation techniques". The
study does not adopt that ranking. It tests it.

| technique | ENISA's verdict | notes for us |
|---|---|---|
| **Counter** | simplest | the ordinal character "can still provide information on the order of the data" |
| **RNG + mapping table** | better protection than counter | AM's "random key table". *"Collisions, however, may be an issue, as well as scalability."* Table compromise reveals everything |
| **Cryptographic hash** | *"generally considered **weak** as a pseudonymisation technique, as it is prone to **brute force and dictionary attacks**"* | **exactly the short-name concern** — confirmed verbatim |
| **MAC / HMAC** | *"generally considered a **robust** pseudonymisation technique from a data protection point of view"* | keyed, so deterministic *and* attack-resistant → gives stability without storing a table. Recovery is a problem if originals are not kept |
| **Symmetric encryption** | *"robust"* | block cipher under a secret key |

### What the ranking does not distinguish

**Every one of these is fully invertible by whoever holds the mapping.** That is not a weakness of
any of them — it is the requirement. Pseudonymisation is reversible for the controller by definition
(GDPR Art. 4(5)), and the "additional information kept separately" *is* the counter's table, the RNG
table, or the HMAC/AES key. A leaked mapping is total, immediate and retroactive across the whole
corpus, and it is equally total for a counter, a hash, an HMAC and a block cipher.

So the taxonomy does not rank how much a technique leaks. It states where the residual risk sits
**when the mapping has not leaked**:

- **Counter and hash have no secret to lose.** No key management, and nothing between an attacker and
  enumeration. ENISA's *weak* is about exactly this.
- **Table, HMAC and symmetric encryption have a secret.** They resist enumeration, and in exchange
  the entire risk moves into key management — an operational property that **no experiment in this
  study measures**, and which the paper must say it does not measure.

### The claim under test

Stability and resistance pull in different directions:

- A plain hash is stable and needs no table — and is broken by a dictionary of ~50k common surnames.
- **HMAC is stable, needs no table, and resists the dictionary attack** — but the whole corpus inverts the moment the key leaks.
- An **RNG mapping table** has no key to leak, but the table *is* the crown jewels, and ENISA flags collisions — a collision is precisely "person 1 confused with person 2".

ENISA's verdict is about **inverting a pseudonym**. The study's question is whether an attacker needs
to. Under a deterministic policy the pseudonym frequency distribution mirrors the real one under
*any* injective mapping, so if that alone identifies people, *weak* and *robust* describe a defence
the attacker walks around rather than through.

The claim is therefore **not that ENISA is wrong about the cryptography, but that the cryptography is
not where the risk is**. It follows from the construction (§5) and **no hypothesis tests it**: the
technique is fixed at HMAC-SHA256 in condition B (§7), so the study argues this rather than measuring
it.

## 4. What already exists

**Detection is crowded, and not solved.** REDACT (arXiv 2606.19881) covers 25 languages and 51
entity types; PIIBench (arXiv 2604.15776) unifies ten corpora into 48 types; MultiGraSCCo (LREC 2026)
is multilingual clinical; MEDDOCAN, i2b2/n2c2, CARDIO:DE and BRONCO precede them. Building another
detection benchmark would add nothing.

But detection is not solved where it matters most. The OpenAI Privacy Filter evaluation
(arXiv 2608.02616), across 14 languages and 5 domains, reports **person names at F1 0.40** and
addresses at 0.49, against e-mail addresses 0.78 and phone 0.76, and collapses on non-Latin script
(Arabic 0.04, Cyrillic 0.03). **The entity class on which pseudonym stability depends is the
worst-detected one.** Surrogate assignment, cross-document consistency, collision rate and leakage
are all built on that foundation, and nobody has measured what it does end to end.

**Surrogate generation is well developed and under-evaluated.** The *hiding in plain sight* line runs
from Carrell et al. (JAMIA 2012, `10.1136/amiajnl-2012-001034`), which conceals ~90 % of residual
identifiers behind realistic surrogates, through two adversarial follow-ups: the "parrot attack"
(JAMIA 2019, `10.1093/jamia/ocz114`) recovers 68 % of 310 real leaks by mimicking the defender's
tagger, and four hostile human readers (JAMIA 2020, `10.1093/jamia/ocaa095`) leave ~70 % of leaked
PII undetected. Alongside it: Yeniterzi et al. (JAMIA 2010, `10.1136/jamia.2009.002212`) on the bias
resynthesis introduces into de-identification measurement; MIST (Aberdeen et al., IJMI 2010,
`10.1016/j.ijmedinf.2010.09.007` — *title-level*); Chambon et al. (JAMIA 2022,
`10.1093/jamia/ocac219`); the shared-task corpora built by surrogate substitution (Uzuner et al.
2007, `10.1197/jamia.m2444`; Stubbs et al. 2015); Neamatullah et al. (BMC MIDM 2008,
`10.1186/1472-6947-8-32`); Dalianis et al. (2019), where 91 % of pseudonymised records were judged
real; Hatvani et al. (2023, `10.33039/ami.2023.08.009`) for a morphologically rich language.

**Attribute-matched surrogates exist. Frequency-matched surrogates do not.** Yermilov et al.
(TrustNLP 2023, `10.18653/v1/2023.trustnlp-1.20`) match gender and language of origin via Wikidata;
Kocaman et al. (arXiv 2312.08495) preserve gender in production. No work selects surrogates to match
the **frequency** of the name replaced — which is the property a distributional attack consumes.

**The pseudonymisation function has been varied before, and every study varies one thing about it in
one domain.** Osborne et al. (BRATsynthetic, arXiv 2210.16125; Electronics 2025,
`10.3390/electronics14193945`) compare consistent, random and Markov substitution for leakage and IE
utility, decoupled from detection — clinical. Yermilov et al. compare five pseudonymisation systems
on downstream tasks and residual-entity rate — news, and detector and replacement co-vary. Bao et al.
(arXiv 2608.03172) show surrogate substitution is detection-neutral across 11 detectors, 7 benchmarks
and 7 languages, by equivalence testing. Adelani et al. (arXiv 2008.03101) compare redaction against
word-by-word replacement with differential-privacy guarantees — dialogue. Outside text, Cretu et al.
(arXiv 2404.03948) make pseudonym-change frequency the independent variable and break it with a
learned profiler at 73.4 % top-1 over 5,139 households, verified on a disjoint user set —
smart-meter time series; and pseudonym-change strategy is a mature paradigm in vehicular networks
(Boualouache et al., IEEE COMST 2017, `10.1109/comst.2017.2771522`).

In German e-mail specifically, Eder et al. (RANLP 2019, ACL Anthology R19-1030) decompose the task
into detecting privacy-bearing entities and then replacing them *"by synthetically generated
surrogates (e.g., a person originally named 'John Doe' is renamed as 'Bill Powers')"*, with a system
architecture for surrogate generation, evaluated on CodEAlltag (Krieg-Holz et al.,
`10.1515/9783110464856-013`). That is this study's pipeline in its German e-mail arm — and its
corpus. It does not vary the function and measures neither utility nor leakage. We do not use
that corpus — it ships no gold spans, so nothing on it is attributable to a method (§11) — but the
paper remains the nearest published prior art to what this study varies, and its substitute lexicons
are the inventory the CARDIO:DE fill draws on (§12). *Cloaked Classifiers* (PrivateNLP
2024, `10.18653/v1/2024.privatenlp-1.13`) crosses pseudonymisation strategy with a downstream
classification task — the utility axis in miniature.

**Utility after de-identification** — *Utility Preservation of Clinical Text After De-Identification*
(BioNLP 2022, `10.18653/v1/2022.bionlp-1.38`); *The Impact of De-identification on Downstream Named
Entity Recognition in Clinical Text* (LOUHI 2020, `10.18653/v1/2020.louhi-1.1`); Manzanares-Salor et
al. (Neural Networks 2026, `10.1016/j.neunet.2026.109079`) argue that treating precision as utility
is a category error.

**Leakage, risk and re-identification.** Scaiano et al. (JBI 2016, `10.1016/j.jbi.2016.07.015`) argue
that recall is not a risk metric. Manzanares-Salor et al. (DMKD 2024,
`10.1007/s10618-024-01066-3`) cast re-identification as classification with neural language models —
the published analogue of A5. Oh et al. (SPIA, arXiv 2604.21211) move the unit of evaluation from
spans to individuals and find subject-level protection at 33 % with over 90 % of spans masked, and
that documents with several subjects leave the non-target ones far more exposed. Meystre et al.
(2014, `10.3233/978-1-61499-432-9-778`) is the human-oracle counterweight: physicians thought they
recognised 4.65 % of their own de-identified notes and were right about none. Base rates come from El
Emam et al. (PLoS ONE 2011, `10.1371/journal.pone.0028071`) and Rocher et al. (Nat Commun 2019,
`10.1038/s41467-019-10933-3`), which puts 99.98 % of Americans within reach of 15 demographic
attributes. DeIDClinic (arXiv 2410.01648) is a risk-aware framework. *The Enron Corpus: Where the Email Bodies
are Buried?* (arXiv 2001.10374) reports 50,000 previously unreported instances of exposed PII in the
field's most-used public e-mail corpus. TAB (Computational Linguistics
2022, `10.1162/coli_a_00458`) remains the only benchmark marking which spans must be masked *to
conceal identity* rather than to hit a category.

**The LLM threat model the workshop cares about.** Staab et al. (arXiv 2310.07298) infer personal
attributes from Reddit text at 85 % top-1 and report that anonymisation and alignment are currently
ineffective against it. Lukas et al. (IEEE S&P 2023, `10.1109/sp46215.2023.10179300`) evaluate PII
extraction, inference and reconstruction on case law, health care and e-mail — the same three domains
as this study. Nyffenegger et al. (NAACL Findings 2024, `10.18653/v1/2024.findings-naacl.157`) find
high re-identification on Wikipedia but that even the best LLMs struggled with court decisions.
Huang et al. (EMNLP Findings 2022, `10.18653/v1/2022.findings-emnlp.148`) find models memorise but
are weak at association, which is what the public-figure stratification tests.

**The thesis has a precedent worth citing rather than hiding:** *Automatic end-to-end
De-identification: Is high accuracy the only metric?* (arXiv 1901.10583, 2019). And an independent
statement of the same gap: Volodina et al. (arXiv 2308.16109) call for studies into the *effects* of
pseudonymisation on unstructured data.

### 4.1 The gap

1. **Every function study is one domain, usually one language.** BRATsynthetic clinical, Yermilov
   news, Adelani dialogue, Cretu smart meters, the whole surrogate literature clinical. Nothing in it
   can separate a property of the method from a property of the corpus. This study crosses legal,
   e-mail, news and clinical text in four languages and two non-Latin scripts, which is what makes
   that separation possible.
2. **Detection, utility and leakage meet pairwise, never as a triple.** Utility × leakage has
   dedicated frameworks (Tau-Eval, arXiv 2506.05979; RAT-Bench, arXiv 2602.12806); detection ×
   leakage has the HIPS attack papers and the risk-metric line; detection × utility has the clinical
   downstream studies. No study reports all three from the same runs on the same corpora with the
   function as the manipulated variable.
3. **Mapping integrity is never measured.** Cross-document consistency is implemented in production —
   Kocaman et al. (Research Square 2025, `10.21203/rs.3.rs-6867162/v1`, *vendor preprint, not peer
   reviewed*) link two billion patient notes into a longitudinal dataset by keeping names, dates and
   identifiers consistent per patient — and within documents in research tools. No published work
   reports a collision, fragmentation or drift rate, or what stability costs in leakage and buys in
   utility. Searching for it is hard because the terminology is taken: "pseudonym consistency"
   returns blockchain work, and a dozen targeted queries returned nothing.

## 5. The thesis

ENISA states the tension and does not measure it (2021 report, §2, on pseudonymisation policies):

> *"fully-randomised pseudonymisation offers the best protection level but prevents any comparison
> between databases. Document-randomised and deterministic functions provide utility but allow
> linkability between records."*

Pseudonym stability — one entity, one pseudonym, held across a corpus — is required for the data to
remain usable: patient timelines, co-reference chains and e-mail threads all depend on it. Stability
is obtainable only under the deterministic policy, which is the policy ENISA identifies as permitting
linkage between records. A practitioner who preserves usability therefore selects the weakest of the
three policies, and no standard states what that costs. This study measures it.

All claims below concern an attacker who does not hold the mapping. Every policy and every technique
is fully invertible to whoever does (§3), so the policy axis governs only what is recoverable without
it.

The claim has two parts. **Empirically**, the choice between pseudonymisation and de-identification —
whether the same entity stays recognisable as itself — dominates both residual re-identification risk
and utility loss; A2, A3 and A5 measure the first (§8.4) and the task scores measure the second
(§8.3). **Structurally**, the
cryptographic technique cannot affect a distributional attacker under a deterministic policy, because
that policy makes the entity-to-pseudonym mapping injective and frequency is invariant under any
injection: counter, hash, HMAC and AES-SIV are indistinguishable to an attacker who counts
occurrences. This follows from the construction rather than from measurement, and the paper states it
as such.

The claim is made for the languages and domains the corpora support: legal (en), e-mail (en),
news (en, zh, ar), clinical (de) — with detection scorable on **all four** corpora, though only TAB's
gold was annotated for de-identification and the others' limits are stated with every number (§8.1).
German e-mail left the study with CodEAlltag (§11), so German rests on CARDIO:DE alone — which is
also the German detection cell, gold by construction from the condition-A fill (§12).

## 6. Hypotheses

Each is falsifiable, and the paper is informative either way. Two earlier hypotheses were dropped
when the axes collapsed to three conditions (§7, AM 2026-09-10): one contrasted an unkeyed hash
against HMAC under the dictionary attack, and one concerned frequency-matched surrogates. Neither has
an experiment any more, and both are recorded in §17.

**H1 — detector recall dominates total leakage.** A missed name leaks in full, whatever is done to
the names that were found. Measured by comparing every detector and every combination rule against
the gold-span oracle (§7, axes D and D′), with leakage recomputed at each recall level. **This
hypothesis can undercut the thesis**: if the ensemble closes most of the gap to the oracle, detection
stops being the bottleneck and the condition axis carries the paper; if it does not, detection recall
is the headline. Both are worth reporting, and the paper should say which it found.

**H2 — de-identification costs the cross-document utility that pseudonymisation preserves, and buys
leakage reduction in return.** B keeps one entity as one surrogate throughout, so anything that
depends on recognising the same person twice survives; C makes every person the same string, so it
cannot. Co-reference — CoNLL F1 per document on TAB and OntoNotes (§8.3) — should be near-unaffected
by B and collapse under C, and the Enron tasks that depend on a person recurring across messages
should degrade under C alone. Leakage moves the opposite way, measured by A2, A3 and A5 (§8.4). *The
size of that exchange is the number the paper exists to report.*

**H3 — pseudonym stability is measurable, and its failures are systematic rather than random.**
Collision, fragmentation and drift (§8.2) are functions of the mapping and the key normaliser.
Applies to B only: under C every identifier of a type is the same string, so there is no mapping to
be stable. The prediction is that the failures are governed by the entity type — person names
fragment because one person appears in many surface forms, locations collide because many distinct
places share a name. No published work reports any of the three (§4.1), so any value is new; the
falsifiable part is that the failures are predictable from the type rather than spread evenly.

**H4 — the condition effect is a property of the method; the detection effect is a property of the
language.** The study spans legal, e-mail, news and clinical text in four languages and two non-Latin
scripts, which is what allows the two to be told apart (§4.1). The prediction is that the **ordering**
of A, B and C on leakage and on utility is the same in every corpus, while the **magnitude** is
governed by measurable corpus structure — how often an entity recurs, how many distinct people share
a document, how skewed the name distribution is — rather than by domain or language as such.
Detection runs the other way: PERSON recall is strongly script-dependent (§4), so the same condition
applied after the same detector leaks differently in Arabic than in English, for reasons that have
nothing to do with the condition. *If the ordering flips between corpora, the method is not
corpus-independent and the paper's claim narrows to the corpora it was measured on.*

**H5 — classical detectors add most where LLMs are weakest, and that is on structured identifiers.**
A high-precision rule-based recogniser for IBANs, phone numbers, e-mail addresses and record numbers
should add recall to an LLM ensemble; a fine-tuned NER should add least, because it fails where the
LLMs already agree. Measured by comparing every LLMs-only subset against the same subset plus one
classical detector (§7, axis D′). *If the hybrid never beats LLMs-only, that is a clean negative
result about where the field should spend its effort.*

## 7. Axes

Three conditions (AM, 2026-09-10). The key normaliser, the cryptographic technique and the surrogate
form are **not varied**: they are fixed at one setting each, chosen from the literature, and together
they define what B and C are.

| | condition | identifiers become | linkable | reversible |
|---|---|---|---|---|
| **A** | full data | the text as the corpus ships it | yes | — |
| **B** | pseudonymised | a realistic, locale-appropriate surrogate; the same entity receives the same surrogate throughout the corpus | yes | with the key |
| **C** | de-identified | a typed placeholder without an index — `[PERSON]`, `[LOCATION]` — so all persons look alike | no | no |

**How B is configured, and why.** Deterministic policy, **HMAC-SHA256**, **N2** normaliser (casefold,
strip titles and punctuation), realistic surrogate drawn locale-appropriately from the gazetteers
(§14). B is "hiding in plain sight", the field's standard since Carrell et al. (JAMIA 2012,
`10.1136/amiajnl-2012-001034`), and it is what this study's own German baseline does — Eder et al.
(RANLP 2019) replace *"a person originally named 'John Doe'… as 'Bill Powers'"*. It is also what runs
in production: Kocaman et al. (2025) keep names consistent across a patient's documents to hold a
longitudinal dataset together. HMAC because ENISA calls it *"generally considered a robust
pseudonymisation technique from a data protection point of view"* (§3) and, being keyed, it resists
the dictionary attack. N2 because it casefolds and strips titles and punctuation, so *"Dr. Weber"*, *"weber"* and
*"Weber"* resolve to one entity while distinct people do not — the least aggressive normalisation
that still recognises the same person written two ways.

**How C is configured, and why.** Presidio's default replacement operator: a typed placeholder with
no index, which is also the shape HIPAA Safe Harbor implies. Tau-Eval (arXiv 2506.05979) measured
exactly this — Presidio placeholder against a frozen model — as near-lossless across eight tasks, so
it is the right comparison point rather than a straw man.

**What was collapsed, and what that costs.** Earlier versions crossed five normalisers × six
techniques × three surrogate forms. Those combinations are not run. The cost is stated rather than
hidden: the hash-versus-HMAC contrast is not measured, so **A1 has nothing to attack** (§8.4);
frequency-matched surrogates are not measured, which was the one surrogate level no published
generator implements (§4); and the document-randomised policy — linkable within a document, not
across — is not run, so the middle of the linkability range is absent. All three are recorded in §17.

| axis | levels | count |
|---|---|---:|
| **condition** | A full data · B pseudonymised · C de-identified | **3** |
| **D** detector | Presidio · GLiNER-multi · GLiNER-PII · `obi/deid_roberta_i2b2` · `StanfordAIMI/stanford-deidentifier-base` · `Davlan/xlm-roberta-large-ner-hrl` · `privacy_tagger` · **every chat model the NHR@FAU gateway serves at run time, DeepSeek excluded** · gold spans | 7 + gateway |
| **D′** combination rule | union · vote(k) · intersection · weighted vote · cascade · token-level BIO voting | **6** |
| **E** corpus | TAB · OntoNotes · Enron · CARDIO:DE | **4** |
| sampling rate | fixed per corpus before the run and recorded with every result (§13) | — |

The condition and the corpus give **15 cells**. Detection is a separate stage: it produces spans,
which B and C then consume, and its cost is corpus × detector — the only runs that cost model time.
The gateway's model list is not fixed in advance: **every chat model it serves at run time is used,
DeepSeek excluded** (AM, 2026-09-08, the backend is down), and which models were live is recorded
with the run because availability is part of the experimental record. The combination rules are a
post-hoc read of the detector cache and cost nothing to compute, however many are reported.

**The gold-spans level is essential, not decorative.** It separates *detector* error from
*pseudonymisation* error, which no prior work does. Without it everything downstream is confounded by
a name detector that the 2026 cross-lingual evaluations put at F1 0.40 (§4).

**`privacy_tagger` stays; the overfitting probe it was included for does not** (AM, 2026-09-09;
narrowed 2026-09-11). It was fine-tuned on 3,000 pseudonymised CodEAlltag e-mails, and the probe was
to run it on that corpus, where it has already seen the substitutions it is asked to find, *and* on
German text it has not — measuring how much a corpus-trained detector inflates its own recall. With
CodEAlltag out (§11) the in-domain half is gone, so the contrast is not measured. The detector
remains in axis D as the German domain-specific level and runs on CARDIO:DE, where it has seen
nothing; that is the out-of-domain half alone, and it is reported as such rather than as the probe. Its README concedes the mechanism from the other side: *"ORG, CITY, URL and EMAIL currently
do not get recognized well due to their replacements in the pseudonymized texts."*

**`privacy_tagger`, GLiNER and the fine-tuned de-ID models emit taxonomies that differ from each
other and from the gold.** §10 carries the mapping.

---

## 8. Measurements

### 8.1 Detection

Scored with the Text Anonymization Benchmark's own scheme (Pilán et al., Computational Linguistics
48(4) 2022, `10.1162/coli_a_00458`; reference implementation ships as `tab/evaluation.py`), because
it is the only published scheme designed for **concealing an identity** rather than hitting a
category:

- **Entity-level recall** is the detection-side privacy metric. An entity counts as protected only if every one of
  its mentions is masked; one unmasked mention leaks the person. This is the risk-weighted measure
  Scaiano et al. (JBI 2016) argue plain recall is not.
- **Token-level recall** is reported alongside it for comparability with the i2b2/n2c2 and MEDDOCAN
  literature, which scores strict and merged spans.
- **Information-weighted precision** is the over-masking metric: each masked token is weighted by how
  predictable it is from the remaining context, so masking a token that carried no information is not
  punished like masking one that did.
- **DIRECT and QUASI identifiers are reported separately**, as TAB annotates them, and **PERSON and
  LOCATION separately** because those carry the stability requirement.

**Scored on all four corpora** (AM, 2026-09-12). Their gold differs in kind, and the kind is
reported beside every number rather than averaged over:

| corpus | what the gold is | recall counts |
|---|---|---|
| **TAB** | manual annotation built for de-identification — 8 types, DIRECT/QUASI/NO_MASK, document-scoped `entity_id`, multiple annotators | of the spans annotators judged identifying |
| **CARDIO:DE** | **ours by construction** — the 16,164 identifiers the condition-A fill inserted, each with its position, type and referent, plus the 14,854 released date markers (§12) | of the identifiers we placed; whatever the Heidelberg de-identifier missed is invisible to us |
| **OntoNotes** | NER: 18 ENAMEX types, annotated for linguistics. No identifier notion, no DIRECT/QUASI | of the spans a linguist marked ENAMEX — a **proxy**, and labelled as one |
| **Enron** | built here from message headers: an 11,124-name identity table matched into bodies | of the names matchable from a header. **No true denominator** — a name never appearing in a header cannot be counted as missed |

**Silver gold is admitted, and its limits are stated rather than hidden** (AM, 2026-09-12). Only TAB
carries annotation made for this purpose. OntoNotes answers a different question and Enron's layer is
our own construction, but both have limits that can be written down, which is what separates them
from a corpus with no span layer at all — the ground on which CodEAlltag was excluded (§11).
**Recall is therefore not comparable across the four**, and no table may place the four numbers in
one column without saying what each denominator is.

Three consequences follow from the table. Enron has **no LOC gold**, so PERSON and LOCATION cannot be
separated there. **DIRECT/QUASI is TAB only**; no other corpus annotates the distinction. And
entity-level recall needs co-reference, so it is computable on TAB, OntoNotes, and — through mailbox
identity — Enron; on CARDIO:DE the identity is the fill's own stipulation and most entities are
singletons by construction, so entity-level and token-level recall nearly coincide there and the
entity-level figure carries little extra information. Token-level recall works wherever there is
gold.

That asymmetry reappears in the combination rule (§7, axis D′) and must be reported there too.
Union-of-spans maximises recall — the privacy-relevant direction — at the cost of precision and
therefore of utility, because every false positive pseudonymises a token that carried meaning.
Majority vote trades the other way. **Report union and vote separately**: the privacy/utility
trade-off the paper is about appears a second time at the detector level, and averaging the rules
hides it.

### 8.2 Stability

Three metrics, computed from the mapping and the co-reference gold.

| metric | counted | denominator |
|---|---|---|
| collision | (document, pseudonym) pairs carrying more than one gold entity | distinct (document, pseudonym) pairs |
| fragmentation | (document, gold entity) pairs carrying more than one pseudonym | distinct (document, gold entity) pairs |
| drift | gold entities whose pseudonym differs between documents | distinct gold entities |

The denominators differ, so the three rates are not comparable with each other. All three apply to
**condition B only**: C replaces every identifier of a type with one string, so there is no mapping
whose integrity could be measured.

| | B pseudonymised | C de-identified |
|---|---|---|
| collision | defect | not meaningful — every identifier of a type is the same string by construction |
| fragmentation | defect | not meaningful |
| drift | defect | not meaningful |

Collision has two causes, and they need separate counts. The **technique** collides when two entity
keys map to one integer — ENISA flags this for RNG mapping tables; HMAC and AES-SIV make it
negligible. The **normaliser** collides when it maps two entities to one key before any cryptography
runs. B fixes the normaliser at N2, which casefolds and strips titles and punctuation, so
*"Dr. Weber"* and *"Weber"* become one key deliberately while *"J. Smith"* and *"Jane Smith"* stay
distinct.

Collision and fragmentation need co-reference within a document: TAB, OntoNotes and Enron. On both
TAB and OntoNotes about three quarters of PERSON chains hold a single mention, so fragmentation is
measured on the remainder; the counts are produced by the run and reported with it, not fixed here.

Drift needs identity across documents. Enron has it through mailbox identity; TAB's and OntoNotes'
chains are document-scoped. CARDIO:DE carries no entity identity and enters no stability cell
(§11).

Cretu et al. (arXiv 2404.03948) measure what pseudonym-change frequency costs in linkability on
smart-meter data, which is drift in another modality. No published work reports these on text (§4.1).

### 8.3 Utility — frozen models, task-based, no single scalar

**No detector is trained by us** (AM, 2026-09-08; clarified 2026-09-10 — the rule was always about
detectors). The A5 attacker is trained, deliberately (§8.4). For the utility instrument the reason is
separate and is not a blanket rule: a TrustFMI audience prompts a
foundation model over a corpus rather than fine-tuning an encoder on one, so **degradation at fixed
weights** is the measurement that matches the deployment pattern.

**The unit of analysis is the document.** For each condition, keep the **vector of per-document
scores** — that is the primary artefact. Report **mean, SD, n** per condition per task. **No deltas,
no ratio, no composite scalar across tasks** (AM, 2026-09-08): a single number loses the information
and makes interpretation harder.

| task | corpus | per-document score |
|---|---|---|
| co-reference | TAB, OntoNotes | CoNLL F1 for that document |
| ECHR article classification (30 labels, multi-label) | TAB | per-case micro-F1 |
| medication IE | CARDIO:DE | span F1 per letter |
| section classification | CARDIO:DE | per-letter accuracy |
| folder classification | Enron | correct / incorrect |
| intent / speech act | Enron | correct / incorrect |
| formality | Enron | Spearman ρ per batch, or per-document error |
| NER agreement | all | span F1 between original and pseudonymised output |

**Always report the original-text score beside every condition.** If the frozen model is near chance
on the original, that task's numbers are uninterpretable and are excluded **with the reason stated**,
never silently averaged away.

**Statistics.** Conditions run on the same documents, so the scores are **paired**:

- **Wilcoxon signed-rank** for continuous scores — F1 is bounded and skewed, so a t-test's normality
  assumption is unsafe.
- **McNemar** for binary correctness (folder, section, intent).
- **Effect size beside every p-value** — median paired difference or rank-biserial. With n ≈ 1,268
  almost anything reaches p < 0.05, so significance without magnitude misleads.
- **Benjamini–Hochberg** across the comparison family. Dozens of conditions per task produce
  spurious significance by construction otherwise.

**Co-reference is the sharpest of these**, and it was previously buried as a proxy. Fragmentation
*is* chain breakage: a resolver's CoNLL F1 on pseudonymised text measures the utility cost of exactly
the failure the stability metrics count, on the same documents. It ties §8.2 to §8.3 directly, which
no prior work does.

The Enron folder task is Klimt & Yang's (ECML 2004), scored zero-shot against the mailbox folder.

Two task-independent proxies — LM perplexity shift and embedding drift — are **sanity signals only**.
They always show that something changed and never show whether anything useful was lost.

**Out of scope, and said so:** whether a model *retrained* on pseudonymised text recovers. If it does,
the field's assumed utility cost is domain shift rather than information loss. It requires training
by definition and belongs in future work.

**Confound: memorisation.** A frozen LLM may recognise an ECHR case or an Enron thread and answer
from memory rather than from the text. Control with the same public-figure stratification A4 uses,
plus a no-context condition.

### 8.4 Leakage

| | attack | applies to | scored as |
|---|---|---|---|
| **A1** | dictionary / brute force | **not run** — no unkeyed condition in the design (§7, §17) | — |
| **A2** | frequency analysis | **B only** — on C every identifier of a type is one string, so there is no distribution to align | top-1 / top-5, Spearman ρ; rank alignment is the optimal 1-D assignment, so no Hungarian solver is needed |
| **A3** | structural linkage (fixed cosine over entity profiles); on Enron the **~184-employee org chart** is the public auxiliary record to link against | A, B and C | Rank-1 / Rank-5 / mAP |
| **A4** | LLM re-identification | A, B and C | **ranked candidate list** — see below |
| **A5** | learned relational re-identification | A, B and C | Rank-1 / Rank-5 / mAP |

**Stated predictions, so the hypotheses can fail.** A2 succeeds on B and has nothing to work with on
C, since every identifier of a type is the same string there. A3 and A5 are strong on B and weak on
C. If that holds, **the stability requirement is itself the vulnerability**: what makes B usable is
what makes it attackable. The residual on C is the more interesting number: removing identity from the identifiers need not
remove it from the surrounding text, and whatever A5 still recovers there is what pseudonymisation
cannot reach.

**A2 candidate representation (AM, 2026-09-10): name alone, and name with date of birth.** Two
entities drawn from a population-weighted inventory receive the same surrogate name; that is what a
natural distribution produces and it is not corrected. An attacker ranking names by frequency cannot
separate them, and A2 scores the pair as a failure — which is a real protection, reported as one.
A2 is therefore run in two settings and both are reported: **name alone**, the scorer as it stands;
and **name with date of birth**, where the candidate is the pair and a shared name is separated by
the date beside it. The difference measures what an independently pseudonymised quasi-identifier
costs: a name collision protects only until a second attribute is released alongside it. This is the
Fellegi–Sunter record-linkage setting.

No corpus in §11 links a date of birth to a person — CARDIO:DE's dates are surrogate-replaced in
place and unchained, TAB's `entity_id` is document-scoped, Enron's `Date` header is dropped in
condition A. The pair setting therefore runs only on the synthetic construction of §8.2.

**A5 is the text analogue of Packhäuser et al.**, *Deep learning-based patient re-identification …*
(Sci Rep 2022, `10.1038/s41598-022-19045-3`), which showed that images believed de-identified are
not. It attacks what pseudonymisation cannot remove: the name is replaced, the profile is not.

**A4 is scored as recovery of the surface form already present in the corpus**, never as inference of
new facts about an individual — see the Enron safeguards.

**A3, A4 and A5 are run on condition A as well**, where nothing has been replaced. That is the
ceiling — what the adversary recovers with no protection at all — and without it a leakage rate on B
or C has no scale. It is the same requirement §8.3 places on utility, where the original-text score
is reported beside every condition.

**A1 does not run.** Condition B uses HMAC-SHA256 (§7), and a dictionary attack against a keyed
function has nothing to compute; reporting "HMAC resisted the dictionary attack" would be a category
error rather than a finding. A1 would require an unkeyed variant of B, which is not in the design
(§17).

**A4 protocol (AM, 2026-09-08): ranked candidate list.** Present the pseudonymised document plus *N*
candidate identities including the true one; score **Rank-1 / Rank-5 / mAP**. Three reasons: it is
directly comparable with A3 and A5, the output is bounded, and the model never free-generates claims
about real people — which is what the Enron safeguards were written to prevent. **The candidates and any auxiliary context come from the corpus itself** — other documents in the
same corpus — never from external knowledge about the person, which is what §15's third safeguard
requires. Run with and without that auxiliary context, and **stratified by public-figure status**, which doubles as a memorisation test
against *Personal Information Parroting in Language Models* (arXiv 2602.20580).

**A5 is the only trained model in the study.** The asymmetry is deliberate and belongs in the paper:
**frozen defenders, trained attackers** — the defence is measured as deployed, the attack is made as
strong as we can make it, because a leakage number is only meaningful against the best available
adversary. The **A5 − A3 gap measures what learning buys the adversary**.

**Two disjointness requirements, both mandatory:**

1. **Entity-disjoint** train/test for A5 — an attacker scored on the entities it trained on measures
   memorisation, not attack strength.
2. **Document-disjoint** gallery/query for A3 and A5 — otherwise the attacker's knowledge and the
   released corpus are the same documents, differing only in replaced spans, and the attack matches
   a corpus against itself. **This was violated in the first run and inflated Rank-1 by 0.29.**

## 9. Statistics and reporting

- Per-document score vectors are the primary artefact; summaries are derived from them.
- Every result row carries: cell configuration, seed, **sampling scheme + rate**, corpus version,
  detector, prompt version, library versions, commit hash.
- Bootstrap CIs over documents where a CI is wanted.
- Results are parquet/JSONL artefacts on disk, never numbers in prose.

## 10. The unified record schema

One format, one converter per source, nothing else changes downstream. Merged verbatim from
`data/metacorpus.md` on 2026-09-09, where it was the only place a record shape was ever specified.

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

**The harmonised taxonomy is TAB's eight categories.** TAB is the only benchmark whose categories were
designed for concealing an identity rather than for hitting a class (§4), so its set is adopted rather
than a new one invented: **PERSON · LOC · ORG · DATETIME · CODE · DEMOGRAPHIC · QUANTITY · MISC**.
Every gold layer and every detector routes into it. The source label is kept verbatim in `type_src`,
so the mapping is reversible and every deviation is countable.

| source | its labels | mapped |
|---|---|---|
| TAB gold | its own eight | identity |
| OntoNotes gold | 18 NE types | PERSON; GPE·LOC·FAC → LOC; ORG; DATE·TIME → DATETIME; NORP → DEMOGRAPHIC; MONEY·PERCENT·QUANTITY·CARDINAL·ORDINAL → QUANTITY; rest → MISC |
| Enron gold | PERSON, EMAIL | PERSON; EMAIL → CODE |
| CARDIO:DE gold | date markers | DATETIME |
| LLM prompt | PERSON, LOC, ORG, DATETIME, EMAIL, PHONE, ID, PROFESSION | EMAIL·PHONE·ID → CODE; PROFESSION → DEMOGRAPHIC; rest identity |
| `privacy_tagger` | FEMALE, MALE, FAMILY, ORG, USER, DATE, STREET, STREETNO, CITY, ZIP, PASS, UFID, EMAIL, URL, PHONE | FEMALE·MALE·FAMILY → PERSON; STREET·STREETNO·CITY·ZIP → LOC; USER·PASS·UFID·EMAIL·URL·PHONE → CODE; DATE → DATETIME; ORG identity |
| `obi/deid_roberta_i2b2` | AGE, DATE, EMAIL, HOSP, ID, LOC, OTHERPHI, PATIENT, PATORG, PHONE, STAFF | PATIENT·STAFF → PERSON; HOSP·PATORG → ORG; EMAIL·ID·PHONE → CODE; AGE → DEMOGRAPHIC; DATE → DATETIME; LOC identity; OTHERPHI → MISC |
| `StanfordAIMI/stanford-deidentifier-base` | DATE, HCW, HOSPITAL, ID, PATIENT, PHONE, VENDOR | PATIENT·HCW → PERSON; HOSPITAL·VENDOR → ORG; ID·PHONE → CODE; DATE → DATETIME |
| `Davlan/xlm-roberta-large-ner-hrl` | DATE, LOC, ORG, PER | PER → PERSON; DATE → DATETIME; LOC, ORG identity |
| GLiNER | open — the label set is ours | prompted with the eight directly |

Three choices in that table are judgement rather than translation, and are recorded as such.
**Structured identifiers — e-mail, phone, URL, username, account and record numbers — all map to
CODE**, which is TAB's own category for them; the source label survives in `type_src`, so H5's
prediction about structured identifiers is still testable without a separate class. **Occupation and
age map to DEMOGRAPHIC**, following TAB, which treats them as attributes rather than identifiers.
**FEMALE and MALE both map to PERSON**: nothing downstream consumes the distinction (§7).

**Unmapped labels are recorded, not discarded.** The detector cache already holds **89 distinct
labels over 1.6 million spans**, including `FILENAME`, `FOLDER`, `GENE`, `COPYRIGHT`, a typo, and a
`<[PSEUDO] …>` marker string used as a type. Anything with no route into the eight maps to MISC and
is counted; the count is reported, because a detector inventing categories is a finding about that
detector.

PIIBench's `LABEL_NORM` — 187 source labels over 54 canonical types — was inspected and **not
adopted**: it is a superset built for ten corpora this study does not use, its canonical set carries
BIO-prefixed duplicates, and routing through it would add a translation step without adding a
distinction any measurement here consumes.

`entity_id` and `subject_id` are what make the stability metrics computable; every converter must
either populate them or declare them null, and a corpus with both null cannot enter a stability cell.

---

## 11. Corpora and their roles

**One assembly, one schema** (AM, 2026-09-06): rather than pick corpora one at a time, the corpora
are assembled as a single set in one unified record schema (§10), so the study's questions are
answered in one pass and the cells become comparable across languages and domains. Task coverage must
reach beyond the clinical domain, and e-mail is required.

A corpus enters the **full** design only if detection, stability **and** utility can be measured on
the same documents — which is the gap §4.1 claims nobody has closed.

| corpus | detection | stability | utility | role |
|---|---|---|---|---|
| **TAB / ECHR** (en, legal) | ✅ 8 types, DIRECT/QUASI | ✅ co-reference | ✅ 30-label articles | **full** |
| **OntoNotes** (en, zh, ar; 5 genres) | ✅ 18 NE types | ✅ co-reference | ✅ co-reference + NER | **full** |
| **Enron** (en, e-mail) | ⚠ structural, header-derived | ✅ cross-document identity | ✅ folder · intent · formality | **full** |
| **CARDIO:DE** (de, clinical) | ✅ **complete for the identifiers we placed** — 16,164 inserted by the condition-A fill, plus the 14,854 released `<[Pseudo] …>` date markers (§12) | ❌ | ✅ medication IE · section classes | detection **+ utility + leakage** (AM, 2026-09-08; detection added 2026-09-12) |
| **BRONCO150** (de, clinical) | ✅ ICD/OPS/ATC | ❌ sentence-scrambled | ✅ coding | utility only — **not yet received** |
| MEDDOCAN · MedDeID · REDACT · AI4Privacy | ✅ | ❌ | ❌ | **OUT** (AM, 2026-09-08) — no utility task, so no cell where a method's effect is attributable |
| **CodEAlltag** (de, e-mail) | ❌ none released | ❌ | ✅ formality · 7-way topic | **OUT** (AM, 2026-09-11) — utility without gold, the same objection from the other side |
| E3C | ❌ no PII layer | ❌ | ❌ | **OUT** (AM, 2026-09-08) |

**The synthetic members are out** (AM, 2026-09-08): *"Let's only use data that has some utility."*
Attributing an effect to a method requires detection, stability **and** utility on the same
documents, and MEDDOCAN, MedDeID, REDACT, AI4Privacy and E3C carry no utility task. **Only TAB,
OntoNotes and Enron carry all three.**

**CARDIO:DE is promoted to a scored detection cell** (AM, 2026-09-12). Its row said *"DATETIME only
… no name layer"*, and that was true of the corpus as released. The condition-A fill changed the
fact: the identifiers in the text are ones we placed, so every position, type and referent is known
by construction (§12). That makes it the most complete detection gold of the four and **the study's
only German detection cell** — §5's *"no scorable German detection cell at present"* no longer holds.
Two limits travel with it. The gold covers what the Heidelberg de-identifier marked, so its own
misses are invisible to us; and the entity identity is the fill's stipulation, not the corpus's,
which is why CARDIO:DE still enters no stability cell.

**CodEAlltag is out** (AM, 2026-09-11): *"We can only use codealltag data in our experiment that has
de-id gold. Data with utility alone is not useful."* The rule that removed MEDDOCAN and the others
applies from the other side, and the answer to how much of the corpus survives it is **none**.
Verified against the copy on disk, not against the paper: `pS` holds exactly 800 `.txt` files plus a
LICENSE and a README, the seven `pXL` trees have the same shape, and there is no `.ann`, standoff,
BIO or CoNLL file anywhere in the release. The 35,800 condition-A documents built on 2026-09-10 are
withdrawn.

What that costs, stated rather than absorbed:

- **The German e-mail cell.** §5's coverage becomes legal (en), e-mail (en), news (en, zh, ar),
  clinical (de). E-mail survives through Enron; German rests on CARDIO:DE alone.
- **The German arm of the formality task** (§8.3). Formality survives on Enron.
- **The seven-way topic task**, which in any case had no row in §8.3 and was never wired into a
  measurement.
- **`privacy_tagger`'s overfitting probe** (§7), which needed the in-domain half.

What it does not cost: the corpus was never scorable for detection, carried no entity identity and
entered no stability cell, so no planned detection, stability or leakage cell is lost. The
substitute lexicons from the same authors stay in use — they are the inventory the CARDIO:DE fill
draws on (§12) — and Eder et al. remain the study's nearest prior art (§4).

**The annotations were not requested.** A draft asking the authors for the spans over the 800 public
e-mails was written on 2026-09-10 and deleted unsent (AM, 2026-09-11): *"i don't want to ask."*

**What the identifiers are, stated once and not made into an axis.** TAB, OntoNotes and Enron carry
**real names in a natural frequency distribution**. CARDIO:DE carries **shifted dates**, and the
names its condition-A text carries were inserted by us (§12).

This matters for exactly two attacks. **A1 and A2 both consume the name-frequency distribution**, so
their numbers transfer only where that distribution is natural — TAB, OntoNotes, Enron. On
CARDIO:DE they measure the inventory the fill drew from, not a natural population. That is a stated limit on where
those results hold. It is **not** an experimental factor and there are no cells for it.

**Access status.** TAB, Enron, OntoNotes, CodEAlltag, MEDDOCAN, MedDeID, REDACT, AI4Privacy, E3C,
PIIBench are on the cluster in `/cluster/shared_dataset/pseudonymization-corpora`. **CARDIO:DE is
restricted to AM alone** — `/cluster/maier/dua-restricted/cardiode`, mode 700; every additional
person needs their own countersigned agreement before touching corpus, derived files or cluster copy.
**BRONCO150** is unanswered; its clause 5 requires deletion by **2027-09-07** with Leser informed.
**n2c2 2014** is blocked — registration closed, "temporarily unavailable".

---

## 12. Data preparation — what each corpus needs before it can be used

Established 2026-09-08/09 by running every adapter against the real releases and auditing each
corpus against its own de-identification specification. Nothing here was visible against synthetic
fixtures; every item was found by touching the actual data.

**The general lesson, because it cost four restarted runs.** Detection was started four times before
the corpus underneath it was settled — first on a 1.2 % Enron skim, then on a corpus whose gold turns
out to be markers, then against a text rendering that is going to be replaced. Detection is the only
step that costs model time, and it is the step whose input must be frozen first. A corpus is ready
when its text is decided, its gold is verified against the release, and it is written down which
measurements it can carry.

### 12.1 Per corpus

**TAB / ECHR.** Text is preprocessed by the release: paragraph numbers stripped in 90.6 % of
documents, and every judgment truncated after the Statement of Facts (`THE LAW` occurs in 0 of
1,268). 19.2 % of PERSON mentions — 3,068, in 23.2 % of documents — are the Court's own initials for
third parties, plus 133 bracketed substitutions and 30 `Mr X` pseudonyms; the applicant is never
among them and is named verbatim in 1,242 of 1,268. The applicant's surname occurs **once** in 69.2 %
of judgments while the role noun *"the applicant"* occurs a median of 17 times, and 79.6 % of PERSON
mentions are agents, judges and counsel. 75.6 % of PERSON co-reference chains are singletons, so
fragmentation is measurable on 2,122 chains, not on all of them.
*Defect to fix:* `_annotations()`'s `quality_checked` branch never tests membership in
`record['quality_checked']` — it rotates to the lexicographically second annotator whenever any
quality-checked entry exists. Plain `first` is lexicographically biased (annotator10 chosen 309×,
annotator9 never) and over-annotates by +3.52 mentions per document (t = 5.41, n = 274).
*Open:* which annotator policy, and whether the applicant should be identified from the record so
that A2 can be scored against the protected person rather than against all PERSON mentions.

**OntoNotes.** The `.name` and `.coref` layers are pulled from the 900 MB archive in one streaming
pass; **the directory structure below the language must be preserved**, because document basenames
collide across genres (`nw/…/ann_0001` and `bn/…/ann_0001` both exist) and flattening silently
overwrites documents.
*Defect fixed:* co-reference attached to **no** document at all. The adapter required the two
layers to strip to identical text, and they never do — `.coref` carries the Penn Treebank null
elements (`*pro*`, `*T*-1`, `*PRO*`, `*OP*`, the null complementiser `0`) that `.name` has no
counterpart for, and wraps its body in `<TEXT PARTNO=…>`. Over 102 document pairs, ~27,000 tokens
appear only in `.coref` against five that appear only in `.name`. Chains are now carried across by
token alignment, and a span transfers only when every one of its tokens lands in a matched block.
The unmappable spans are the null elements themselves, which are co-reference mentions in OntoNotes but have no surface in
`.name`; Chinese has the most, because it drops pronouns systematically.
*Co-reference reaches a reduced set, and the reduced set is what is used* (AM, 2026-09-10).
4,560 of the 5,994 documents ship a `.coref` file — 2,384 English, 1,729 Chinese, 447 Arabic. After
the token alignment above, **4,027 carry a chain attached to a gold mention**: 1,940 of 3,637
English, 1,646 of 1,911 Chinese, 441 of 446 Arabic. The 533 that do not are documents whose chains
touch only spans that no `.name` token matched. Every measurement needing co-reference on OntoNotes
— entity-level recall (§8.1), collision and fragmentation (§8.2), the co-reference utility task
(§8.3) — runs on those 4,027 and reports that denominator beside the result.
*Name distribution:* surname Zipf slope −0.925 against a US-Census reference of −0.918, so the shape
is natural — but Spearman ρ with census frequency is 0.263. It is a newswire-celebrity distribution:
real names, not population-representative ones.

*Open:* the text is Penn Treebank tokenised throughout, Chinese segmented by spaces, Arabic 82.6 %
diacritised and 31.1 % clitic-fragmented. That is not text a deployment sees. Whether to detokenise,
and at what cost to the gold offsets, is undecided.

**Enron.** The document text is **sender, recipients, names, addresses, subject and body** (AM,
2026-09-09). The duplicated HTML and plain-text alternatives of the same message are collapsed to
one, as are quoted replies and forwarded blocks. Every message in the drawn subset is processed —
the subset is `subject` @ 0.10 (§13) and it is used whole.
*Messages with no body are excluded* (AM, 2026-09-10). Once quoting is stripped, some messages
carry sender, recipients and subject but no prose — a forward with nothing added. They cannot be
scored on any utility task and would enter every condition as an empty document, so they are dropped.
The identity table is built **before** the filter, so a name appearing only in such a message still
counts towards the corpus's identities.

*The folder label must not be in the text.* `X-Folder` names the mailbox folder, which is the
folder-classification target, so it is excluded along with the other routing headers; only the
fields listed above are kept.
*Defect to fix:* the gold is derived from message headers by our own adapter and is 44.3 % artefact —
`Mail` (70,118), `mail` (72,574), `info` (26,387) and `eren` (23,798) are admitted as person
entities, and 26.6 % of gold spans are matched mid-word (`Mail` inside `JavaMail`) because grounding
uses `str.find` with no word-boundary test. Gold is recomputed at scoring time, so repairing it costs
no detector records — but changing the *text* invalidates every record computed against the old one.
Enron gold emits only PERSON and EMAIL, so **there is no LOC gold on Enron** and §8.1's
PERSON-and-LOCATION-separately requirement cannot be met there.

**Check every corpus directory for LFS stubs before counting it as present.** REDACT's real 213 MB
benchmark was a 134-byte stub; CodEAlltag's formality scores were 130-byte pointers by the same
mechanism. The cluster has no `git-lfs`, so a plain checkout leaves pointers where a reader sees
files, and a corpus can be counted as present when none of it is there.

**CARDIO:DE.** Every de-identified date is marked in place as `<[Pseudo] 12/03/2019>` — 14,854 in the
400-letter split, 6.20 % of all characters, one every 320 characters — and the marker wraps nothing
but dates. **As released** that is the corpus's only identifier gold, and it is DATETIME only —
superseded by the condition-A fill below, which supplies the rest. Person, institution and contact
tokens were replaced by the de-identifier's own IOB output, shaped `<letter>-<CLASS>`:
**11 distinct strings in the person slot across 400 letters**, one of which fills the patient slot in
384 of them.
*Alignment rule:* the CAS `sofaString` and the `.txt` are **equal in length and differ in content** —
every newline in the `.txt` is a space in the attribute, because XML normalises a literal newline
inside an attribute value. The invariant an offset needs is **equal length, not equal characters**;
demanding both discarded two letters of 400, one of them over a single capital letter. Where the
lengths genuinely differ — one letter in 400, whose CAS lacks a newline — the CAS text is used, since
that is what the annotations were made against.
*Defect to fix:* `custom:Sectionsentence` marks section **headings**, 4–18 characters, ~62 k of
4.76 M characters — not sections. A section-classification task built on them scores ~1.3 % of the
text. Sections must be derived by extending each heading to the next.
*Dates are implausible as values*: admission years span 2019–2519, and 70 of 400 letters state ages
of 280–459. The per-document offset is constant — admission minus birth reproduces the stated age in
400 of 400 letters — so intervals and orderings within a letter are intact, but absolute dates and
anything that asks a model to judge realism are not.

*The heldout split carries no annotations*: `CARDIODE100_heldout` ships CAS files with no `custom:`
layers, so it supports neither utility task. The adapter defaults to `CARDIODE400_main`.

*Also unused:* the Becker extension (`extension/…/json/`) carries a token-level NER layer —
Diagnosis, Diagnostic, Drug, Medical_Finding, Therapy — that no adapter loads.

*Condition A is built, not read* (AM, 2026-09-10). CARDIO:DE is the only corpus of the five that
ships no full-data text: TAB, OntoNotes and Enron carry real names, and here the identifiers are IOB
tag tokens left in the running text — **26,836 tokens, 16 types, 19,729 runs across the 500
letters**. The fill replaces each run with a plausible German entity of the matching type and
unwraps the `<[Pseudo] …>` markers to the bare date, so the result is a letter rather than a
marked-up letter. On the 400-letter split it fills **16,164 runs** and remaps the 27,065 medication,
section and relation spans onto the new offsets. Names come from Eder et al.'s CodEAlltag substitute
lists — 53,028 surnames, 441 male and 534 female given names, 32,758 German cities, 51,583 streets —
so the inventory is the one the German baseline this study cites already used. A run's length decides
its surface: `B-PER` stood for a surname and `B-PER I-PER` for a given name and a surname, so one
entity acquires two forms exactly where the original letter had two. The run → entity map is written
beside the corpus and **is the detection gold**, since after the fill every identifier's position,
type and referent is known by construction.

*Identity is stipulated and is an upper bound.* The tags mark where an identifier stood, not who it
was; two `B-PER` runs may be one person or two and nothing in the markup separates them. The rule:
a `PER` run whose preceding context contains *Patient* / *Patientin* belongs to the letter's single
patient entity — 452 of 2,740 runs — and gender is taken from the same cue, since the morphology
survives de-identification even though *Herr* / *Frau* became `B-SALUTE`. Every other `PER` run
becomes its own person: 1,357 after *Mit freundlichen Grüßen*, 66 after a referral cue, 865 with no
cue at all. That yields **6.72 person entities per letter, which is a ceiling, not an estimate** — a
physician named in the body and again in the signature receives two names. The patient is named
1.13 times per letter and carries more than one surface form in 31 of 400 letters, so CARDIO:DE
supports no fragmentation measurement; §8.2 already excludes it. Inferring identity from the filled
names instead would be circular, since the names are ours.

*Institution names are composed, not drawn.* CodEAlltag's `org` sublist is general business names —
*Apfelscheune*, *AC-Cosmetics* — and a discharge letter referring a patient to one of those does not
read as a letter, so the 1,969 `ORG` runs are filled from templates over the city list
(`Klinikum {Stadt}`, `Universitätsklinikum {Stadt} gGmbH`, `Kardiologische Praxis {Stadt}`). These
are plausible but not attested. The Destatis *Krankenhausverzeichnis* 2024 — 1,829 site names, 2,129
street names, 1,736 postcodes, free to reproduce with attribution — is the attested source and is
not yet fetched.

### 12.2 Cross-cutting

**Chinese and Arabic are pseudonymised with English surrogates.** `engine.mention_language` reads
`mention.attributes['language']`, which **no adapter sets**, so it falls back to `"en"`. 1,911
Chinese and 446 Arabic OntoNotes documents are affected. Non-Latin script is the reason OntoNotes is
in the study.

**Detector output is not on the harmonised grid.** `alignment.ground_snippets` writes the model's raw
string into `Span.type` and never sets `type_src`. The cache holds **55 distinct out-of-taxonomy
labels** — `URL`, `FILE`, `MONEY`, `TIME`, `AGE`, `OTHER`, the typo `PERGSON`, and a literal
`<[PSEUDO] 15/10/39>` used as a type — across 1.05 % of Enron spans and 0.53 % of CARDIO:DE spans.

**Serialisation loses data.** `_document_record` drops `Span.source` and `Span.score`, so a
round-tripped corpus cannot say which model produced a span; `_encode` tags dataclasses with
`__type__` but there is no decoder, so CARDIO:DE's medication and section spans return as plain dicts
and `span.section_type` raises. There is no round-trip test.

**The detector cache records no text version.** It is keyed `(corpus, detector, doc_id)`. If a
document's text changes, `done()` skips it and the stale spans are scored against the new text at
wrong offsets, silently. Records affected by a text change must be **deleted**, not skipped.

**A truncated model reply is indistinguishable from an empty one** unless `finish_reason` is
recorded. Under a 2,048-token budget one reasoning model returned zero spans on every document it saw
with no error at all, which an ensemble reads as "found nothing" rather than "never answered". The
budget is now 16,384 and `finish_reason`, token usage and a truncation count are written with every
record.

## 13. Sampling

Four of the five corpora are small enough to use whole, so no scheme is needed and none is chosen.

| corpus | drawn | scheme |
|---|---|---|
| TAB | all 1,268 | — |
| OntoNotes | all | — |
| CARDIO:DE | all 400 annotated letters | — |
| **Enron** | **`subject` @ 0.10, seed recorded** — whole mailboxes, all their messages | `subject` |

**Enron uses `subject` and only `subject`** (AM, 2026-09-08). Two schemes are two different document
sets, so detection would have to cover their union, and Enron is the largest corpus in the study by
an order of magnitude. `subject` draws whole mailboxes and keeps every message in them, so an
entity's profile stays complete — which A3 and A5 need and which no thinning scheme can restore.
Inside a kept mailbox the frequency distribution is also complete, so A2 loses statistical power
rather than the effect it measures. What `subject` costs is a smaller and shifted entity population:
prolific correspondents are kept or dropped whole, and links to dropped mailboxes disappear. That is
stated with the result.

The identity table is built from **all** ~517,000 messages before the draw, so cross-document
identity is complete even for mailboxes outside the sample (§12).

**CodEAlltag is no longer sampled** — it is out of the study entirely (AM, 2026-09-11, §11). The
reduction designed for `CodEAlltag_XL` on 2026-09-10 — 5,000 per topic from the 881,957 of 1,468,942
documents that passed a 200-byte floor and an encoding check — is withdrawn with it.

Scheme, rate and seed are stamped into `Corpus.name` and into every document's metadata. **No result
may be quoted without its sampling provenance** (§9).

## 14. Models and resources

| role | model |
|---|---|
| rule-based detector | Presidio + spaCy backbone |
| zero-shot NER | `urchade/gliner_multi-v2.1`, `urchade/gliner_multi_pii-v1` |
| public fine-tuned de-ID | `obi/deid_roberta_i2b2`, `StanfordAIMI/stanford-deidentifier-base` |
| multilingual NER | `Davlan/xlm-roberta-large-ner-hrl` |
| domain-specific (de) | `privacy_tagger` (flair) — Eder et al.'s German de-identification tagger; the corpus it was trained on is out of the study (§11), the model is not. **On the cluster: `models/privacy_tagger.pt` under the work directory** — 2,637,679,217 bytes, verified 2026-09-11 against `privacy-tagger.aau.at/model.pt` (`Content-Length` identical, `Last-Modified` 2022-04-19). It is **not** in the `privacy_tagger` repository, which holds only a LICENSE and a README, and it does not need fetching again. `flair` 0.15.1 and `torch` 2.5.1+cu121 are in the venv |
| co-reference | `biu-nlp/lingmess-coref` |
| embeddings | `intfloat/multilingual-e5-large` |
| perplexity | `Qwen/Qwen2.5-0.5B` |
| LLM detectors, A4, zero-shot tasks | NHR@FAU gateway — **every chat model it serves that can extract spans**, which §7 axis D requires and which is **eight** as of the probe of 2026-09-12: `gpt-oss-120b` · `Qwen/Qwen3.6-35B-A3B-FP8` · `RedHatAI/gemma-4-31B-it-FP8-block` · `RedHatAI/Mistral-Small-3.2-24B-Instruct-2506-FP8` · `GaleneAI/Magistral-Small-2509-FP8-Dynamic` · `google/gemma-4-E4B-it` · `Microsoft/Phi-4-mini-instruct` · `ibm-granite/granite-4.1-3b` |

**Two of the gateway's ten chat models are out, for different reasons.** `lightonai/LightOnOCR-2-1B`
is **not a span extractor**: probed 2026-09-12, it echoed the system prompt back and ran to
`finish_reason=length`. **DeepSeek is excluded by decision** (AM, 2026-09-10: *"C1 — no deepseek"*),
and that stands independently of availability — the earlier note that its backend was down was an
observation, not the reason. `deepseek-ai/DeepSeek-V4-Flash` still returns HTTP 500 and the `-0731`
variant timed out on 2026-09-12, but neither fact is what excludes them.

**`Microsoft/Phi-4-mini-instruct` and `ibm-granite/granite-4.1-3b` were added 2026-09-12** (AM). They
were served all along and their absence was a gap between §7's wording and the run script, not a
decision. Both answer in 0.5 s against 4–25 s for the rest, so they cost almost nothing in wall clock,
and at 3–4 B against 24–120 B they are the only small models in the pool — the diversity H5 feeds on.

**Re-probe availability before every run and record which models were live** (§5): a model that is
down blocks its cell and is reported, never silently substituted.

**Gazetteers** (frequency- and attribute-bearing; an unweighted list can test neither H4 nor A1's
banding): US Census 2010 surnames (162,253, public domain) · UCI Gender-by-Name (147,269, CC-BY,
source of the gender attribute) · GeoNames `cities15000` (34,135, CC-BY).

---

## 15. Enron is in — decided, with safeguards

**AM, 2026-09-07: Enron is included, and the ethics point is made explicitly in the paper.**

The reasoning, recorded because the paper has to state it: excluding Enron protects nobody. The
corpus stays public, the field keeps citing it silently, and the people in it are no safer. What
exclusion would cost is concrete — it is the only public e-mail corpus with real names in a natural
frequency distribution, the same people recurring across thousands of messages, a genuine downstream
task, and a real public auxiliary record to link against. E-mail is a required domain (AM,
2026-09-06), and no other English e-mail corpus supplies those four.

Stating this in the paper is itself evidence for the thesis about how the field evaluates privacy:
the corpus is an unresolved privacy incident involving non-consenting individuals, and it is cited
routinely without comment.

The attack target is **our own pipeline output**, not the corpus. We pseudonymise Enron ourselves and
then invert *our* pseudonyms; recovering a name that has sat on a public web server for twenty years
discloses nothing new. Marginal harm is what matters, and it is close to zero — provided the
following hold, which cost the study nothing:

1. **No real name from the corpus appears anywhere** in the paper, figures, tables, appendices or
   released artefacts. Attacks are reported as aggregate rates only.
2. **No released artefact re-exposes PII** — no mapping tables, no worked inversions, no example
   documents reproduced verbatim.
3. **A4 is scored against the corpus surface form**, not against external knowledge of the person,
   and is **stratified by public-figure status**.
4. **The 2020 audit is cited** (arXiv 2001.10374, 50,000 previously unreported PII instances) and the
   position is stated in the paper rather than left implicit.
5. **One written check with the FAU DPO.** Public US data processed in the EU for research is routine
   under GDPR Art. 89, but "it is public" is not itself a lawful basis. Ask once, in writing, cite
   the answer.

---

## 16. Deliverables

**Released.** The code; the per-document score vectors and the aggregate rates for every cell; and
the comparison of A, B and C on detection, stability, utility and leakage, reported **one panel per
task**, since a single utility scalar was rejected (§8.3).

Scores and rates are numbers and expose nothing. **The detector cache is not released**: it stores
every detected span's verbatim text, which for the restricted corpus is a substantial fraction of the
corpus itself, and for Enron is live personal data. `results/` is gitignored wholesale for that
reason. No mapping table, no worked inversion and no example document is released either (§15).

**What is delivered for which language.** Detection and utility are delivered for every corpus that
supports them (§11). **Stability is delivered for English only**: it needs entity identity, and
neither German corpus has any. Nothing here is delivered "per language and domain" without that
qualification.

**Distribution is a build recipe, not a dataset.** Members span MIT, CC-BY-SA (copyleft), a custom
academic licence, the LDC licence, a per-user DUA and one public release; ShareAlike and a DUA cannot
coexist in one redistributable artefact. Ship converters, a manifest with checksums, and a local
builder.

---

## 17. Open items

1. **BRONCO150** — no reply from Prof. Leser since 2026-09-07.
2. **n2c2 2014** — registration closed; ask DBMI when it reopens. Its loss removes clinical
   cross-document stability and the only *clinical* corpus where detection and utility would have
   shared documents (§11).
3. **The fair A3/A5 comparison** — A3 restricted to A5's held-out entities and gallery.
4. **CARDIO:DE person-name handling** — dates are marked in place, names are not, and the release
   README does not say what was done to them. Read it out of Richter-Pechanski et al., *Sci Data*
   10, 207 (2023) before making any claim about the corpus's identifiers.
5. **Where the Enron size sweep stops** — Enron at rate 0.10 is 86 % of the whole detection budget
   The sweep 0.01 → 0.25 is the plan's own design; its upper end is AM's to set.
6. **Three consequences of collapsing to three conditions** (AM, 2026-09-10, §7), recorded so they
   stay visible: the hash-versus-HMAC contrast is not measured and **A1 cannot run**;
   **frequency-matched surrogates** are not measured, and they were the one surrogate level no
   published generator implements (§4); and the **document-randomised** policy — linkable within a
   document, not across — is not run, so the middle of the linkability range is absent. Each would
   need one further condition.
7. **Axis D's non-gateway levels have adapters but have never been run.** Corrected 2026-09-12: the
   earlier wording — *"no adapter"* — was wrong. `PresidioDetector`, `GlinerDetector`,
   `TokenClassificationDetector` and `PrivacyTagger` all exist. What was missing is a **runner** to
   execute them over the corpora into the shared detector cache, which is what
   `experiments/detect_local.py` now is. Two real gaps remain, both measured on 2026-09-12:
   **`privacy_tagger`'s 2.6 GB weights are on the cluster** (`models/privacy_tagger.pt`) and every
   library is installed — `presidio_analyzer`, `gliner` 0.2.29, `flair` 0.15.1, `transformers`
   4.57.6, `torch` 2.5.1+cu121, and the spaCy models `de_core_news_lg`, `en_core_web_lg`,
   `xx_ent_wiki_sm` — but the **five HuggingFace detectors are not downloaded**:
   `urchade/gliner_multi-v2.1`, `urchade/gliner_multi_pii-v1`, `obi/deid_roberta_i2b2`,
   `StanfordAIMI/stanford-deidentifier-base`, `Davlan/xlm-roberta-large-ner-hrl`. Presidio is CPU
   and runs on the head node beside the gateway pool; the neural levels need a GPU and therefore a
   Slurm allocation, which is the one part of the pipeline that does.
8. Does the **2026 revision of ISO 25237** change any recommendation we would make? Somebody needs a
   copy — it is not open access.
9. ~~Ask Eder / Krieg-Holz / Hahn for CodEAlltag's annotated S+d subset.~~ **Closed 2026-09-11,
    both ways.** The request was drafted and deleted unsent — *"i don't want to ask"* (AM) — and the
    corpus is out of the study regardless (§11). Two findings from the drafting are worth keeping,
    because they would otherwise be rediscovered. The annotations over the **800 released** e-mails
    were never barred by the authors: LREC 2020 §6 and LREC 2022 §3.2 bar distribution of *e-mails*
    the donors did not write — the 590 dropped from the release — and say nothing about spans. And a
    manually annotated pseudonymised set that carries no real personal data at all exists in their
    hands: LREC 2022 Table 3, XL1k, 1,000 e-mails and 3,226 entities. Neither was pursued. **German detection no longer depends on
    this ask**: the CARDIO:DE fill supplies that cell (§8.1, §11). BRONCO150, unanswered since
    2026-09-07, would be a second one.
10. Ensemble composition: which LLMs, and is the combination rule fixed across languages or tuned per
   language? Tuning per language risks overfitting the benchmark.

11. **Paper scoping** — which panels fit eight pages.
