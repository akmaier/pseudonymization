# Format — what is settled and what is not

## Settled, from `README.md`

| | |
|---|---|
| venue | TrustFMI @ ACCV 2026 (workshop, Osaka, 14 Dec 2026) |
| submission | **2026-09-25** |
| length | 6–8 pages full, 4 pages short |
| style | Springer LNCS |
| system | OpenReview |

## Not verified — needs the call for papers

The workshop site has **not** been read. My web-search budget for the session is exhausted and no
URL for the workshop is recorded anywhere in this repository, so the following are assumptions
carried over from `README.md` rather than facts checked against the call:

- whether the page limit counts references and appendices, or excludes them (LNCS workshops differ,
  and 6–8 vs 8+refs is the difference between three results tables and two);
- whether review is **double-blind** — this decides whether `\author{}` and the acknowledgements
  are filled in now or at camera-ready, and whether the GitHub URL can appear in the submission;
- whether the workshop mandates `llncs` specifically or an ACCV variant;
- any numbering, margin or font deviation the workshop imposes on top of LNCS.

**Give me the URL and I will check all four and correct this file.**

## What is set up

`llncs.cls` and `splncs04.bst` come from TeX Live 2026's own `llncs` bundle — already installed,
nothing vendored, nothing to keep in step with upstream. `make` in this directory drives `latexmk`,
which handles the bibtex/rerun cycle; plain `pdflatex` needs three passes and fails quietly.

Build artefacts are gitignored. `main.pdf` is not committed: it is derived, and a binary in the
history makes every diff worse.
