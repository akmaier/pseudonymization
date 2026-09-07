# i2b2 / n2c2 2014 — DBMI Data Portal

**Route:** register at `portal.dbmi.hms.harvard.edu`, sign the Rules of Conduct and the Data Use
Agreement, wait for human approval.

**Only AM can do this.** Access is granted **per individual user** — every co-author or HiWi who
touches the data must register and be approved separately. Decide now who that is, because the
approval is a human review and the lead time is unknown.

**What we want:** the **2014 i2b2/UTHealth** set — 1,304 records, 296 patients, 805,118 tokens.
Both tracks come from the **same documents** (verified 2026-09-06):

- Track 1 — de-identification gold, PHI replaced by **realistic surrogates**, automatic then manually
  corrected
- Track 2 — heart-disease risk factors, i.e. the downstream task on identical records

This is the strongest single cell in the design: real longitudinal clinical narratives, gold PHI, a
downstream clinical task on the same text, and — because the records are longitudinal over 296
patients — the only clinical corpus in the meta corpus that supports **cross-document** pseudonym
stability.

Also worth requesting while registered: **2006** and **2016 (CEGS N-GRID psychiatric)**, both
de-identification sets, for provenance and genre contrast.

## Research summary for the portal

> **End-to-end evaluation of text pseudonymisation: detection, utility and leakage.**
>
> Research on clinical de-identification varies the detector and holds the replacement step fixed.
> We invert that: the independent variable is the **pseudonymisation function and policy**, using the
> technique and policy taxonomies of ENISA (2021) and DIN EN ISO 25237 — deterministic,
> document-randomised and fully randomised policies crossed with counter, RNG-with-mapping-table,
> hash, HMAC and symmetric encryption, and with opaque, realistic and attribute-matched surrogates.
>
> On each combination we measure detection quality, downstream utility, and residual re-identification
> risk on the same documents. The distinctive requirement is **pseudonym stability** — one person
> keeps one pseudonym corpus-wide and never collapses into another person — which is why the
> longitudinal structure of the 2014 corpus matters to us: it is the only clinical resource we know
> of where the same patient recurs across documents, so cross-document stability can be measured at
> all. The heart-disease risk-factor annotations on the same records give the utility measurement a
> real clinical task rather than a proxy.
>
> Analysis is aggregate. We will publish rates and performance figures only; no record text, no
> identifiers and no re-identification of any individual. Code and aggregate results will be
> released; the corpus will not be redistributed.
>
> Target venue: TrustFMI workshop at ACCV 2026.

## Watch for, when the DUA text appears

The same two clauses that constrain BRONCO are likely present here:

- a **no-re-identification** clause, which would rule out leakage attacks A1–A4 on this corpus;
- a **no-third-party-transfer** clause, which would rule out the LLM detector levels and A4 via the
  NHR@FAU gateway.

If so, report those cells as licence-blocked (`CLAUDE.md` §1) and ask the portal rather than assuming.
Note this corpus is otherwise the best fit for stability and utility, neither of which is affected.
