# Style references

Copied from `akmaier/Agent4CT` (`paper/JARGON.md`, `paper/STYLE_WORDS.md`) on 2026-09-21 at AM's
instruction, so the drafting agent has them without needing network access.

- **AGENT4CT_STYLE_WORDS.md** — AM's own sentence openers and connectors, grounded in two of his
  papers. The register to preserve: didactic first-person plural, short sentences, the signature
  pivot **"Yet,"**, the didactic aside **"Note that"**, signposting with "Here, we …". The goal
  stated there is worth repeating: AM should read it and think *"yes, that sounds like me"* — not
  find a mechanical sprinkle of transition words.
- **AGENT4CT_JARGON.md** — the method rather than the content. It fixes a **reader model** and then
  lists every term that reader would not know, with a one-line plain gloss and a verdict
  (define-on-first-use / add gloss / replace with a plainer word / leave).

**Our reader model is different and must be substituted.** Agent4CT assumes an expert medical
physicist who is not an ML specialist. TrustFMI is *Trustworthy Foundation Models in Medical
Imaging*, so assume **a computer-vision researcher who works on images and not on text**: fluent in
deep learning, ensembles, precision/recall and adversarial attacks; **not** fluent in named-entity
recognition, co-reference, HMAC, surrogate generation, or anything specific to clinical text. Terms
needing a gloss on first use under that model include: named entity, span, co-reference chain,
surrogate, pseudonymisation versus anonymisation versus de-identification, keyed hashing, and
information-weighted precision.

Our own internal shorthand must not reach the paper at all — the attacks are **named**, never
A1–A5, and the key normaliser is described, never N0–N4 (AM, 2026-09-21).
