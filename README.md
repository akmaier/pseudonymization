# pseudonymization

Experiment repository for a study on **text pseudonymisation**, evaluated end to end —
**detection, utility and leakage** — across languages, domains, methods and *policies*.

Target venue: **TrustFMI @ ACCV 2026** (workshop, Osaka, 14 Dec 2026). Submission **25 Sept 2026**;
6–8 pages full / 4 pages short, LNCS, via OpenReview. Treat that deadline as the near-term target,
not as a limit on the study — compute is available and the work is intended to outlive the workshop.

**Read [`experiment_plan.md`](experiment_plan.md) first — it is the sole authority on what is run.**
It carries the factor design, the metrics, the statistics, the corpora and the compute.
[`experiment_plan.md`](experiment_plan.md) carries the *argument*: the thesis, the gap in the literature, the hypotheses and
the limitations. Everything under `data/` is **superseded historical record** — it shows how
decisions were reached and is not binding.

## Decisions already taken

- **Public data only.** No Erlangen clinical data in this paper (AM, 2026-09-06). This removes the
  data-protection dependency, makes every result reproducible, and lets us release everything.
- **Not another detection benchmark.** REDACT, PIIBench and the OpenAI-Privacy-Filter evaluation all
  landed in 2026 and own that ground. Our independent variable is the **pseudonymisation function
  and policy**, not the detector.
- **Scope is not negotiable.** Nobody — human or agent — reduces the scope or the number of
  experiments in `experiment_plan.md` to save time, money or compute. The budget is sufficient (AM,
  2026-09-06). If a planned cell turns out to be impossible, that is reported and stated, not
  silently substituted or dropped.
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
CARDIO:DE an all-classical ensemble reaches token recall 0.982 at 1.41 s/document; the best ensemble
of any kind reaches 0.985 at 118 s/document — 0.003 recall for 84× the cost. On TAB, at a recall
floor of 0.80, the best information-weighted precision is 0.854 using Qwen3.6 at 98.7 s/document,
against 0.844 all-classical at 0.57 s/document — 0.010 precision for 174×.

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

**Within the 10 % band, fast is one to two orders of magnitude cheaper.**

| corpus | MAX-sensitivity | FAST-sensitivity | speed-up | sensitivity given up |
|---|---|---|---|---|
| CARDIO:DE | 0.985 @ 116.9 s | 0.908 @ **0.263 s** | 444× | 0.077 |
| TAB | 0.895 @ 14.2 s | 0.826 @ **0.219 s** | 65× | 0.069 |
| OntoNotes | 0.613 @ 9.45 s | 0.559 @ **5.01 s** | 1.9× | 0.054 |
| Enron | 0.971 @ 25.6 s | 0.881 @ **0.057 s** | 448× | 0.090 |

| corpus | MAX-specificity | FAST-specificity | speed-up |
|---|---|---|---|
| CARDIO:DE | 0.99990 @ 0.694 s | 0.98622 @ **0.263 s** | 2.6× |
| TAB | 0.99755 @ 29.7 s | 0.99338 @ **0.117 s** | 254× |
| OntoNotes | 0.98729 @ 9.45 s | 0.97404 @ **0.103 s** | 92× |
| Enron | 0.94281 @ 20.9 s | 0.87872 @ **0.026 s** | 805× |

**The band binds very differently on the two qualities, and that is itself a result.** Sensitivity
spans 0.50–0.99 and the 10 % band admits 32–414 of the candidates, so it is a real constraint.
Specificity spans only 0.86–0.9999 on three corpora — identifiers are a small minority of any text —
so the band admits *all* of them and FAST-specificity degenerates to "cheapest ensemble above the
floor". Enron is the exception: 15.5 M tokens and specificity down to 0.70, where the band admits
330 of 742 and the cell means something. A specificity criterion only discriminates on a corpus
dense enough in identifiers to move it.

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
- **Medication extraction is free under a precise rule, and only under one.** A vs B is significant
  under `union` (*q* = 5.6 × 10⁻³) and **not distinguishable from zero** under either three-detector
  ensemble (*q* = 0.94–0.99).
- **Surrogates beat placeholders decisively for token-level tasks.** NER agreement under condition C
  collapses to 0.004 (union) and 0.674 (vote), against B's 0.611 and 0.973. Replacing a name with
  `[PERSON]` removes the thing the downstream model is looking for.
- **…and are worth nothing for document-level ones.** Section classification scores 0.677 under B and
  0.711 under C at the same span source — C is *better*. A classifier reading the whole letter does
  not care which string stood where, so the surrogate machinery buys nothing there.
- **Every document loses NER agreement, not merely the average.** Rank-biserial is −1.000 for that
  task at every span source; the rules differ in the median loss (−0.377 union, −0.021 vote), not in
  whether it is universal.


## Layout

| path | contents |
|---|---|
| [`experiment_plan.md`](experiment_plan.md) | **the authoritative experiment specification** — factors, metrics, statistics, corpora, sampling, models, compute |
| [`experiment_plan.md`](experiment_plan.md) | the argument — thesis, gap, hypotheses, related work, limitations |
| [`AUTHORS.md`](AUTHORS.md) | author list — complete; middle order (2–5) still unsettled, **do not guess it** |
| [`references/standards.md`](references/standards.md) | ISO 25237, ENISA, ISO/IEC 20889, GDPR |
| [`references/text_pseudonymization.md`](references/text_pseudonymization.md) | detection benchmarks, surrogate generation, utility, leakage, email |
| [`data/candidates.md`](data/candidates.md) | every corpus considered, including ones beyond the current plan |
| `config/` | `*.example.toml` templates; the real `*.toml` are gitignored — no hostnames, usernames or keys in this repo |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | the software: patterns, extension points, quickstart |
| `src/pseudonymkit/` | the package — policies, techniques, surrogate forms, metrics, detector ensembles |
| `tests/` | 670 tests, no network, no models, under two seconds |
| `experiments/` | code lands here |

## For the agent picking this up

- Every reference in `references/` was retrieved from Crossref, arXiv, ACL Anthology or the
  publisher during 2026-09-05/06. Where an abstract could **not** be retrieved it says so — those are
  title-level evidence only and must be opened before being relied on.
- **No credentials in this repo, ever.** Corpora are not committed either: several are DUA-bound
  (BRONCO), licensed (Avocado, i2b2/n2c2) or contain real personal data (Enron). `.gitignore` covers
  `data/corpora/`.
