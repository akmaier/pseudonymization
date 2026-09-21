# STYLE_WORDS.md — Maier sentence-opener & connector vocabulary

Vocabulary analysis for rewriting `paper/tex/main.tex` in Andreas Maier's
own didactic voice. Grounded in his own prose:

- Maier et al., *"A gentle introduction to deep learning in medical image
  processing"* (Z. Med. Phys. 2019; arXiv:1810.05401).
- Maier et al., *"Learning with known operators reduces maximum error
  bounds"* (Nat. Mach. Intell. 2019; arXiv:1907.01992).

All quoted sentences below are verbatim from those two papers. They are the
evidence for which openers/connectors are genuinely *his*, and roughly how
often he reaches for each.

**Register (the thing to preserve):** didactic first-person plural — *"we …
let us … note that … hence"*. He motivates, then pivots on **"Yet,"**, then
resolves. He states an intuition, gives the math, then restates it in plain
words. Sentences are short. He is comfortable with gentle rhetorical framing
("Obviously,", "Of course,") and with signposting the reader ("Here, we …",
"In the following, …"). The goal is that Maier reads the paper and thinks
"yes, that sounds like me" — not a mechanical sprinkle of transition words.

---

## (A) SENTENCE OPENERS / TRANSITIONS he uses

Ordered roughly by how characteristic each is of his voice.

### Very characteristic (his signature moves)

- **"Yet,"** — his signature pivot from a promising premise to its flaw.
  Very frequent.
  - "Yet, some of these approaches neglect prior knowledge and bear risk of
    implausible results"
  - "Yet, their approach neither uses deep nets nor end-to-end training"
  - "Yet, during the derivation of our mathematical models, we often
    introduce [simplifications]"
  - "Yet, our error analysis is still useful, as for the case …"

- **"Note that"** — didactic aside, points the reader at a subtlety.
  Frequent.
  - "Note that the approximation will only be valid for samples drawn from
    the same compact set"
  - "Note that many intermediate results can be reused during computation"
  - "Note that this simplification does not limit the generality"

- **"Hence,"** — his preferred consequence marker (more than "Therefore").
  Frequent.
  - "Hence, blind deep learning methods have to be performed with care"
  - "Hence, correct choice of η is crucial for successful training"
  - "Hence, decision trees also describe general boundaries in ℝⁿ"

- **"Obviously,"** — gentle rhetorical confidence, often to open a
  motivating claim. Characteristic.
  - "Obviously this technology is highly relevant for medical imaging"
  - "Obviously, known operators have been embedded into neural networks
    already"

### Common

- **"In fact,"** — sharpens or escalates the previous point.
  - "In fact, the maximal error ϵ is close to 0.7"
  - "In fact, this approach is general and holds for all decision trees"
  - "In fact, we only adopted weights while run-time [and] behaviour …"

- **"As such,"** — draws a consequence about applicability/requirement.
  - "As such, an additional practical requirement is representative training
    sets"
  - "As such, the concept is widely applicable for many researchers in
    physics"

- **"Still,"** — concessive: acknowledges a limit, then presses on.
  - "Still, there is continuous progress"
  - "Still, these simplifications introduce slight errors along the way"

- **"Here,"** — locational signpost to what *this* work/section does.
  - "Here, we only report representative examples"
  - "Here, we offer a set of known operations in parallel and determine …"

- **"However,"** — plain contrast (used, but he prefers "Yet,").
  - "However, due to general non-convexity, minima are likely local only"

- **"Furthermore,"** — additive, to stack a second contribution/fact.
  - "Furthermore, we connect observations with traditional concepts in
    pattern recognition"
  - "Furthermore, we also show experimentally that known operators reduce …"

- **"Thus,"** — consequence (interchangeable with "Hence," but rarer).
  - "Thus, we are able to use the gradient of the original problem"

- **"In order to"** — purpose opener.
  - "In order to compute gradients, we define loss functions …"
  - "In order to update parameters, we compute matrix derivatives"

- **"Let us"** — the lecturer inviting the reader along. Rhetorical.
  - "Let us consider slightly more complicated network structures"

### Occasional

- **"Interestingly,"** — flags a non-obvious payoff.
  - "Interestingly, as the approach is end-to-end, discretization errors are
    intrinsically corrected"
- **"Now,"** / **"Now that"** — shifts to the present state of the field.
  - "Now that deep learning also starts addressing fields of physics …"
- **"Of course,"** — concedes the expected objection before answering it.
- **"One …"** — "One … is …" to introduce an instance ("One example is …").

---

## (B) CONNECTORS he uses to link ideas

### Very characteristic

- **"i.e."** — restate precisely (his "plain-English restatement after the
  math" habit). Very frequent.
  - "… to yield 𝐲 = ReLu(𝐀ᵀ𝐊𝐖𝐱), i.e. 𝐊 …"
- **"e.g."** — give an instance. Very frequent.
  - "Examples range from image super resolution, image denoising and
    inpainting …" (his enumerated "e.g." register)
- **"such that"** — specify a condition on a construction. Frequent.
  - "an approximation û(𝐱) such that the difference between true function
    [and approximation is small]"
  - "using combination weights such that networks approximate continuous
    functions"

### Common

- **"in particular"** — zoom from general to the salient case.
  - "In particular, [it] demonstrates that mismatches in training and test
    data …"
  - "In particular, the trained algorithm learns to compensate for the loss"
- **"with respect to"** — frame optimality/comparison.
  - "optimal with respect to our training data"
- **"in the following"** — forward signpost.
  - "In the following, we are interested in hybrid imaging of magnetic …"
- **"hence"** (mid-sentence) — inline consequence, same as the opener.
- **"as"** (causal) — lightweight "because": "our error analysis is still
  useful, **as** for the case …".

### Occasional

- **"as a result"** — consequence phrase (rare; he prefers "Hence,").
- **"which is why"** — causal hinge (rare).
- **"thereby"** — means/result (rare).
- **"in practice"** — pivot from theory to the applied number.

---

## How this maps onto our paper

- Intro: keep the funnel. The existing **"Yet a purely data-driven
  reconstructor …"** is already his pivot — reinforce that arc, add a
  **"Note that"** / **"Hence,"** where a bare sentence can carry his voice.
- Discussion / Conclusions: this is where the voice matters most. Use
  **"Hence,"**, **"Still,"**, **"In fact,"**, **"As such,"**,
  **"Note that"**, **"Of course,"** to open the honest-scorecard sentences —
  but keep them short and one-idea-per-sentence (the non-native-reader rule
  overrides everything; we vary beginnings, never lengthen).
- Do not start many consecutive sentences with the same word. Rotate the
  openers above rather than repeating one.
