# pseudonymization

**Taking the names out of text is easy to measure badly.** Report recall alone and the answer is
always "use more models". This study measures the other columns too — what the detection *costs*,
what the text is still *good for* afterwards, and what can still be *recovered* from it.

It runs across languages, domains and detection methods, but the variable under test is the one
usually held fixed: the **pseudonymisation policy** itself — whether a name becomes `[PERSON]`, a
plausible surrogate, or something else.

### Three findings you can read off the tables below

- **Detection recall bounds leakage. The replacement scheme does not.** Conditions B and C replace
  *identical* spans, so overwriting each replaced span of the surrogate release with `[PERSON]`
  reproduces the placeholder release character for character — verified on every TAB and OntoNotes
  document. A release cannot be safer than a text anyone can compute from it, so a surrogate buys
  nothing against an adversary who knows the scheme. Telling a candidate-ranking attacker that much,
  **without changing one character of the text**, lifts it from 0.085 to 0.205.
- **The cheap option is often not the worse option.** On CARDIO:DE the fast-sensitivity ensemble
  gives up 0.097 of sensitivity but is *more* specific than the maximum (0.9769 against 0.9670) and
  **191× cheaper**. Catching the last identifiers means over-detecting, and over-detection has its
  own price.
- **Over-detection destroys more utility than pseudonymisation does.** Downstream NER agreement is
  0.611 under a permissive detector union and 0.973 under a majority vote — *same policy, same
  surrogates, same corpus*. What you replace matters less than what you wrongly decide to replace.

**Everything uses public corpora only**, so every number here can be reproduced.

### Where to start

| you want | read |
|---|---|
| the results, in prose | this file, below |
| what exactly was run, and why | [`experiment_plan.md`](experiment_plan.md) — the authoritative specification: thesis, gap, hypotheses, factor design, metrics, statistics, corpora, compute |
| how the code is put together | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| who wrote it | [`AUTHORS.md`](AUTHORS.md) |

Target venue: **TrustFMI @ ACCV 2026** (workshop, Osaka, 14 Dec 2026), submission 25 Sept 2026. The
deadline is a near-term target, not the limit of the study — the work is intended to outlive the
workshop.

Everything under `data/` is **superseded historical record**: it shows how decisions were reached
and is not binding.

## Decisions already taken

- **Public data only.** No Erlangen clinical data in this paper (AM, 2026-09-06). This removes the
  data-protection dependency, makes every result reproducible, and lets us release everything.
- **Not another detection benchmark.** REDACT, PIIBench and the OpenAI-Privacy-Filter evaluation all
  landed in 2026 and own that ground. Our independent variable is the **pseudonymisation function
  and policy**, not the detector.
- **Nothing is dropped to save compute.** The full factor design in `experiment_plan.md` is run as
  specified; where a planned cell proves impossible it is reported as such rather than quietly
  substituted. This is why some cells below are expensive and reported anyway — the cost *is* the
  finding.
- **Ensemble detection is in.** In the group's own tests an ensemble across LLMs plus the baseline
  methods outperformed any single detector; it belongs in the detector axis as both a strong
  baseline and a recall upper bound. See `experiment_plan.md` §1, axis D.
- **Enron is in** (AM, 2026-09-07), and the paper states the ethics position explicitly rather than
  using the corpus silently. Excluding it would have protected nobody while removing the only public
  e-mail corpus with real names in a natural frequency distribution. Five safeguards bind — see
  `experiment_plan.md`. This closes the repo's oldest open question.
- **Text only.** This repository is the pseudonymisation study and nothing else (AM, 2026-09-06).
  Image de-identification — defacing, CT, MRI, DICOM — is a separate paper with a separate team; its
  reference base was moved out of this repo to
  `mailassist/projects/trustfmi_paper_deid/literature_image_deidentification.md`.

## Detection operating points — what an ensemble costs

The detection sweep scores every subset of the detector pool up to size three (2,151 span sources on
fifteen detectors) on recall and precision. On that table alone the winner is always whatever runs
the most models. Cost is the missing column, and it was already on disk: the detector cache records
`elapsed` per document, so every detector carries its observed wall-clock latency on every corpus it
ran on — measured, not estimated. `experiments/ensemble_cost.py` joins the two.

The spread is three orders of magnitude, and its shape is the same on all four corpora:

| detector family | seconds per document (CARDIO:DE · TAB · OntoNotes · Enron) |
|---|---|
| cheapest classical (Stanford de-identifier) | 0.263 · 0.117 · 0.049 · 0.026 |
| dearest classical (flair privacy tagger) | 0.694 · 0.408 · 0.169 · 0.119 |
| cheapest LLM (granite-4.1-3b) | 0.724 · 1.197 · 0.418 · 1.103 |
| dearest LLM (Qwen3.6-35B) | 442.9 · 98.1 · 71.1 · 41.7 |

**The last point of quality is bought with an LLM and costs two to three orders of magnitude.** On
CARDIO:DE the maximum-sensitivity ensemble reaches 0.992 at 57.6 s/document while the fast one
reaches 0.895 at 0.301 s — 0.097 of sensitivity for **191× the cost**, and the cheaper ensemble is
the *more specific* of the two. The latency table above is where that factor comes from: a single
LLM in an ensemble sets its parallel cost, because cost is the slowest member.

So four operating points are named — **fast against maximum, on specificity and sensitivity**
(AM, 2026-09-20) — each chosen per corpus from that corpus's own sweep by a stated rule:

| | **sensitivity** (identifier tokens caught) | **specificity** (non-identifier tokens left alone) |
|---|---|---|
| **maximum** | the most caught, at any cost | the most left alone, at any cost |
| **fast** | the cheapest ensemble still within 10 % of that maximum | the cheapest ensemble still within 10 % of that maximum |

Three parts of that decision matter and are recorded here because none is inferable from the numbers:

- **Sensitivity and specificity, not precision.** They are the detector's two error rates read
  against their own denominators, and between them they say what pseudonymisation did and did not
  touch. Precision mixes the denominators; it is reported beside them, not optimised for.
- **Cost is the slowest member, not the sum** (AM, 2026-09-20: *"as we can run methods in parallel
  fast should be the max of the three methods considered"*). The detectors are independent passes
  over the same text, so adding a cheap detector to a slow one is free — and summing would punish an
  ensemble for exactly the members that cost nothing. On CARDIO:DE this halves the maximum-specificity
  ensemble's cost from 1.57 s to 0.69 s without changing the ensemble.
- **A sensitivity floor is kept, and is not optional.** Specificity is `1 − FP/negatives`, so an
  ensemble that predicts nothing has no false positives and scores a perfect 1.0 while catching
  nothing. Maximising it unconstrained selects the emptiest candidate available. The floor (0.5 token
  recall) is reported with every selection.

**Both error rates are shown for every point.** Reading one alone hides the cost of the other, which
is the whole reason for choosing sensitivity and specificity as the pair.

| corpus | operating point | cost (s/doc) | sensitivity | specificity | rule |
|---|---|---:|---:|---:|---|
| CARDIO:DE | MAX sensitivity | 57.633 | 0.992 | 0.9670 | union |
| | **FAST sensitivity** | **0.301** | 0.895 | 0.9769 | union |
| | MAX specificity | 116.875 | 0.523 | **0.9997** | vote |
| | FAST specificity | 0.263 | 0.781 | 0.9862 | single |
| TAB | MAX sensitivity | 14.210 | 0.925 | 0.8986 | union |
| | **FAST sensitivity** | **0.219** | 0.893 | 0.9242 | union |
| | MAX specificity | 98.110 | 0.501 | 0.9959 | vote |
| | FAST specificity | 0.117 | 0.520 | 0.9934 | single |
| OntoNotes | MAX sensitivity | 9.450 | 0.747 | 0.9763 | union |
| | FAST sensitivity | 5.376 | 0.684 | 0.9731 | union |
| | MAX specificity | 0.103 | 0.503 | 0.9960 | union |
| | FAST specificity | 0.103 | 0.503 | 0.9960 | union |
| Enron | MAX sensitivity | 25.557 | 0.973 | **0.7720** | union |
| | **FAST sensitivity** | **0.057** | 0.899 | 0.7419 | union |
| | MAX specificity | 20.931 | 0.588 | 0.9428 | intersection |
| | FAST specificity | 0.026 | 0.674 | 0.8787 | single |

The search covers singles, pairs and triples, so the 13-detector ensemble the study **recommends**
lies outside it and can exceed the "maximum" row.

Three things only become visible with both columns present:

- **The fast cell is usually not the worse cell.** On CARDIO:DE, FAST sensitivity gives up 0.097
  sensitivity but is *more* specific than the maximum (0.9769 against 0.9670) and 191× cheaper — not
  a compromise, but better on one axis and cheaper on the other. TAB behaves the same way (0.9242
  against 0.8986, 65× cheaper).
- **On OntoNotes the fast/maximum specificity distinction is degenerate.** The 10 % band admits all
  414 candidates, so both cells select one ensemble. A criterion optimised in isolation can fail to
  discriminate at all.
- **Enron's maximum sensitivity costs 23 % of the corpus.** Specificity 0.7720 means nearly a quarter
  of the non-identifier tokens were replaced too. Catching 97.3 % of identifiers on real e-mail is
  possible, and the price is a text with a quarter of its ordinary words overwritten — which the
  sensitivity column alone reports as a triumph.

## What CARDIO:DE says about utility

Three tasks, scored per document against condition A and tested under §8.3's protocol (Wilcoxon or
McNemar by score kind, Benjamini-Hochberg within a task family, an effect size beside every
*p*-value). `medication_ie:in_narrative` is excluded throughout: the frozen model is near chance on
the **original** text, so it cannot measure a loss.

- **The detector's precision, not the pseudonymisation policy, is the dominant lever.** NER agreement
  under condition B is 0.611 with a permissive union of all fifteen detectors and 0.973 when the same
  fifteen must reach a majority — same policy, same surrogates, same corpus. Over-detection destroys
  more utility than pseudonymisation does.
- **…but "majority" over fifteen detectors means eight of them, and that removes whole identifier
  classes rather than trimming recall evenly.** `DEMOGRAPHIC`, `MISC` and `QUANTITY` fall to **zero**
  mentions on all three corpora scored so far, and `CODE` loses 94 % on TAB and 99 % on OntoNotes.
  Eleven of the fifteen detectors emit thousands of demographic spans each; eight never overlap on
  one, because the harmonised label collapses genuinely different categories — Presidio's
  nationality/religion/politics, GLiNER's PII classes, and an open LLM vocabulary of age, ethnicity
  and title. So the rule that makes medication IE statistically free is also the rule under which
  every demographic identifier survives untouched into the released text. The utility gain and the
  privacy loss have the same cause, and neither is visible in a token-recall column.
- **Medication extraction is free under a precise rule, and only under one.** Against an
  original-text score of 0.371 ± 0.182, A vs B is significant under `union` (0.346 ± 0.181,
  *q* = 5.6 × 10⁻³) and **not distinguishable from zero** under the majority vote (0.364 ± 0.189,
  paired difference −0.008 ± 0.178, *q* = 0.80) or either three-detector ensemble (*q* = 0.94–0.99).
- **Surrogates beat placeholders decisively for token-level tasks — partly by construction.** NER
  agreement under condition C collapses to 0.004 (union) and 0.674 (vote), against B's 0.611 and
  0.973. Replacing a name with `[PERSON]` removes the thing the downstream model is looking for, and
  the frozen recogniser never tags `[PERSON]` as a name, so every replaced mention counts as a
  disagreement. That column measures the metric as much as the release: read it *between rules*, not
  between forms.
- **…and are worth less than nothing for document-level ones.** Against an original-text score of
  0.749, section classification loses 0.072 ± 0.086 to surrogates and only 0.038 ± 0.089 to
  placeholders (both *q* < 10⁻¹³; rank-biserial −0.846 and −0.531). A classifier reading the whole
  letter does not care which string stood where, and the surrogate machinery is the *worse* of the
  two there.
- **Every document loses NER agreement, not merely the average.** Rank-biserial is −1.000 for that
  task at every span source; the rules differ in the median loss (−0.377 union, −0.021 vote), not in
  whether it is universal.


## What the attacks recover

All figures are for the **recommended 13-detector union**, and all concern people: identity is
`PERSON`, and the other identifier classes are what linkage exploits rather than what it names.

| corpus | person recall | people still named in clear | frequency matching (public / oracle) | context linkage | learned linkage | chance |
|---|---:|---:|---:|---:|---:|---:|
| CARDIO:DE | 1.000 | 0.1 % | 0 / 1 | 0.0000 ± 0.0000 | 0.0071 ± 0.0160 | 1/207 |
| TAB | 0.996 | 0.8 % | 0 / 1 | — | — | — |
| OntoNotes | 0.935 | 4.9 % | 0 / 1 | — | — | — |
| Enron | 0.890 | 18.0 % | 0 / 0 | 0.0095 ± 0.0012 | 0.0407 ± 0.0029 | 1/3816 |

- **Frequency matching recovers nothing.** With a public name-frequency list it names no identity on
  any corpus. Every name it returns is one the *detector missed* and the release printed in clear
  text — that measures the defender's recall, not the adversary's inference, and the two must never
  be added into one rate. Even the corpus's own distribution, which no real attacker holds, aligns
  at most one identity.
- **Linkage succeeds where identity is real, and needs its anchors.** On Enron the same fixed
  similarity recovers **0.706** of held-out people from *unmodified* text; after the recommended
  release it recovers 0.0095 — still 36× chance, but two orders of magnitude below that ceiling.
  Training the metric raises it to 0.0407, four times the fixed attack. The residual risk belongs to
  an adversary who can learn.
- **Recall bounds all of it.** On Enron, two votes lower person recall from 0.890 to 0.732, raise
  fixed linkage fivefold to 0.0500 and take the names left in clear text from 180 to 1,868;
  intersection leaves person recall at 0.037 and linkage at 0.2380.
- **Surrogates are not a privacy control.** B and C replace identical spans, so the placeholder
  release is a character-for-character rewrite of the surrogate release — verified on 1268/1268 TAB
  and 5994/5994 OntoNotes documents. A candidate-ranking LLM scores 0.085 on surrogates against
  0.290 on placeholders, which *looks* like protection; it is the ranker believing the surrogate.
  Told the scheme, with the text untouched, it reaches 0.205; neutralising name-like spans with a
  public name list, 0.215. Choose the replacement form for **utility**, not for privacy.

Token recall also hides exposure, and the denominator decides what a number means. The recommended
release leaves one CARDIO:DE person mention of 4,396 in clear text — one entity of 1,957 and **one
patient of 270**. Counting every identifier class rather than people alone, 8.5 % of letters still
carry something and 12.2 % of patients do.

## Layout

| path | contents |
|---|---|
| [`experiment_plan.md`](experiment_plan.md) | **the authoritative specification** — the argument (thesis, gap, hypotheses, related work, limitations) *and* the design (factors, metrics, statistics, corpora, sampling, models, compute) |
| [`AUTHORS.md`](AUTHORS.md) | author list — complete; the middle order (positions 3–6) is not yet settled |
| [`references/standards.md`](references/standards.md) | ISO 25237, ENISA, ISO/IEC 20889, GDPR |
| [`references/text_pseudonymization.md`](references/text_pseudonymization.md) | detection benchmarks, surrogate generation, utility, leakage, email |
| [`data/candidates.md`](data/candidates.md) | every corpus considered, including ones beyond the current plan |
| `config/` | `*.example.toml` templates; the real `*.toml` are gitignored — no hostnames, usernames or keys in this repo |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | the software: patterns, extension points, quickstart |
| `src/pseudonymkit/` | the package — policies, techniques, surrogate forms, metrics, detector ensembles |
| `tests/` | 670 tests, no network, no models, under two seconds |
| `experiments/` | code lands here |

## Provenance, data and credentials

- **References are retrieved, not remembered.** Every entry in `references/` was pulled from
  Crossref, arXiv, the ACL Anthology or the publisher on 2026-09-05/06. Where an abstract could not
  be retrieved, the entry says so — those are title-level evidence only and should be opened before
  being relied on.
- **No credentials in this repository, ever.** `config/` ships `*.example.toml` templates; the real
  files are gitignored, and carry no hostnames, usernames or keys.
- **Corpora are not committed.** Several are DUA-bound (BRONCO), licensed (Avocado, i2b2/n2c2) or
  contain real personal data (Enron); `.gitignore` covers `data/corpora/`. You will need to obtain
  them yourself under their own terms — `data/candidates.md` lists every corpus considered and what
  each requires.
- **On Enron.** The corpus is used deliberately and the ethics position is stated in the paper
  rather than left implicit: it is the only public e-mail corpus with real names in a natural
  frequency distribution, and excluding it would have protected nobody. Five safeguards bind its use
  — see `experiment_plan.md`.
