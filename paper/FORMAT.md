# Format — verified against the call, 2026-09-21

Sources: [workshop](https://rashedlab.github.io/TrustFMI) ·
[ACCV workshops](https://accv2026.org/workshops/) ·
[author guidelines](https://accv2026.org/submissions/author-guidelines/) ·
[template zip](https://accv2026.org/wp-content/uploads/2026/04/ACCV_2026_template.zip) ·
[OpenReview venue](https://openreview.net/group?id=afcv.org/ACCV/2026/Workshop/TrustFMI)

## The venue

**TrustFMI = "Trustworthy Foundation Models in Medical Imaging"**, workshop W01 of ACCV 2026.
Half-day, afternoon of **14 December 2026**, Grand Cube Osaka, room 1004. Organisers: Essam A.
Rashed (Univ. of Hyogo), Yang Cao (Inst. of Science Tokyo), Naoto Yanai (Panasonic Holdings).
Contact `trustfmi2026@gmail.com`. Best-paper award CHF 200 (MDPI).

## Settled

| | |
|---|---|
| length | **6–8 pages full, 4 short/position, references excluded** |
| proceedings | **only full papers** enter the ACCV 2026 proceedings; short and position papers are presented but not published |
| review | **double-blind**, ≥ 2 reviewers |
| style | ACCV 2026 kit — `llncs.cls` **plus `accv.sty`**, not plain LNCS |
| submission | OpenReview, single PDF, ≤ 50 MB, no supplementary field |
| dates | submit **25 Sep 2026** · notify 16 Oct · camera-ready 23 Oct · programme 27 Nov · workshop 14 Dec |

> "full papers: 6–8 pages; short papers: 4 pages, excluding references"

## What double-blind requires here

- **Acknowledgements are omitted** from the review copy.
- **Self-citations stay in** — ACCV is explicit: blind review "does not mean that one must remove
  citations to one's own work", only that you do not write "our" when citing it.
- **External links are banned outright**, including code repositories: material for review "should
  not be provided through external links". So **the GitHub URL cannot appear in the submission**,
  even though the repository is intended for release with the paper.
- The author block is **anonymised by the style file**, not by hand — `accv.sty` in `review` mode
  overrides `\author`, `\institute`, `\titlerunning` and `\authorrunning`. `AUTHORS.md` therefore
  does not enter the submission at all, which also sidesteps the unsettled middle order.

## What `review` mode does, and why the preamble is exactly this

```latex
\documentclass[runningheads]{llncs}
\usepackage[review,year=2026,ID=*****]{accv}
```

`accv.sty` raises a hard `\PackageError` if the class is not `llncs` and warns without
`runningheads`. In `review` mode it anonymises as above, turns on **line numbers** (required for
review, removed at camera-ready; it patches the AMS math environments so equations are numbered
too), and prints the **paper ID on every page** — mandatory. Replace `*****` with the number
OpenReview issues.

Page numbering is **on**, from `llncs.cls`'s running head. Geometry is fixed by `accv.sty`
(122 × 193 mm text on 146 × 217 mm paper) and must not be touched: "Papers that differ significantly
from the required style may be rejected without review", and changing `\textheight`, `\vspace` or
`\baselinestretch` is called out specifically. Font stays CMR — using Times "can be interpreted as
purposely circumventing the length limitations".

`hyperref` with `pagebackref` is recommended for review and **not** for camera-ready.

## ⚠️ Deadline anomaly

The OpenReview submission invitation's machine-readable `duedate` is **2028-09-25 15:00 UTC**, not
2026. The time of day is right — 15:00 UTC is midnight JST, i.e. end of 25 September Japan time —
so the year looks like an organiser configuration slip. **The workshop page says 25 September 2026
and that is what to work to.** Worth an email to `trustfmi2026@gmail.com` rather than trusting the
OpenReview clock.

## Still unresolved

- **Whether an in-PDF appendix counts toward the 6–8 pages.** The call says only "excluding
  references"; "appendix" appears nowhere.
- **Whether supplementary material is accepted at all.** The OpenReview form offers one PDF field
  and no supplementary upload, and the venue instructions are empty. Assume not.
- Whether the page count is measured in the `review` geometry or the camera-ready one.
- Whether a paper ID is issued for workshop submissions (the ID field is mandatory in the template).
- Camera-ready instructions — the kit says they follow after decisions.
