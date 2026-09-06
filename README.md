# pseudonymization

Experiment repository for a study on **text pseudonymisation**, evaluated end to end —
**detection, utility and leakage** — across languages, domains, methods and *policies*.

Target venue: **TrustFMI @ ACCV 2026** (workshop, Osaka, 14 Dec 2026). Submission **25 Sept 2026**;
6–8 pages full / 4 pages short, LNCS, via OpenReview. Treat that deadline as the near-term target,
not as a limit on the study — compute is available and the work is intended to outlive the workshop.

**Read [`PLAN.md`](PLAN.md) first.** It carries the thesis, the factor design, the metrics and the
hypotheses. Everything else here is supporting material.

## Decisions already taken

- **Public data only.** No Erlangen clinical data in this paper (AM, 2026-09-06). This removes the
  data-protection dependency, makes every result reproducible, and lets us release everything.
- **Not another detection benchmark.** REDACT, PIIBench and the OpenAI-Privacy-Filter evaluation all
  landed in 2026 and own that ground. Our independent variable is the **pseudonymisation function
  and policy**, not the detector.
- **Scope is not negotiable.** Nobody — human or agent — reduces the scope or the number of
  experiments in `PLAN.md` to save time, money or compute. The budget is sufficient (AM,
  2026-09-06). If a planned cell turns out to be impossible, that is reported and stated, not
  silently substituted or dropped.
- **Ensemble detection is in.** In the group's own tests an ensemble across LLMs plus the baseline
  methods outperformed any single detector; it belongs in the detector axis as both a strong
  baseline and a recall upper bound. See `PLAN.md` §Factors, axis D.
- **Text only.** This repository is the pseudonymisation study and nothing else (AM, 2026-09-06).
  Image de-identification — defacing, CT, MRI, DICOM — is a separate paper with a separate team; its
  reference base was moved out of this repo to
  `mailassist/projects/trustfmi_paper_deid/literature_image_deidentification.md`.

## Layout

| path | contents |
|---|---|
| [`PLAN.md`](PLAN.md) | thesis, factors, metrics, attacks, hypotheses, deliverables |
| [`AUTHORS.md`](AUTHORS.md) | author list — complete; middle order (2–5) still unsettled, **do not guess it** |
| [`references/standards.md`](references/standards.md) | ISO 25237, ENISA, ISO/IEC 20889, GDPR |
| [`references/text_pseudonymization.md`](references/text_pseudonymization.md) | detection benchmarks, surrogate generation, utility, leakage, email |
| [`data/candidates.md`](data/candidates.md) | every corpus considered, including ones beyond the current plan |
| `config/` | `*.example.toml` templates; the real `*.toml` are gitignored — no hostnames, usernames or keys in this repo |
| `experiments/` | empty; code lands here |

## For the agent picking this up

- Every reference in `references/` was retrieved from Crossref, arXiv, ACL Anthology or the
  publisher during 2026-09-05/06. Where an abstract could **not** be retrieved it says so — those are
  title-level evidence only and must be opened before being relied on.
- **No credentials in this repo, ever.** Corpora are not committed either: several are DUA-bound
  (BRONCO), licensed (Avocado, i2b2/n2c2) or contain real personal data (Enron). `.gitignore` covers
  `data/corpora/`.
- The **Enron question is open and deliberate** — see `data/candidates.md`. It is the largest public
  English e-mail corpus and it is itself an unresolved privacy incident. Decide it explicitly; do not
  drift into using it silently.
