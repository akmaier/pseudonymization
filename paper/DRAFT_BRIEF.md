# Brief for the drafting agent

Write the **first draft** of the paper into `paper/sections/*.tex`. This is a draft to be iterated
on, not a final text — but it should be a serious attempt, not a skeleton.

## Read first, in this order

1. `paper/OUTLINE.md` — the structure, the page budget per section, and most of the numbers. **Follow
   it.** Section order, subsection presence and page targets are decided; do not add sections, and do
   not add subsections to the introduction.
2. `paper/FORMAT.md` — 8 pages of content, references free; double-blind, so **no author names, no
   acknowledgements, and no repository URL or any external link**.
3. `paper/style/AGENT4CT_STYLE_WORDS.md` — the voice. Didactic first-person plural, short sentences,
   the signature pivot **"Yet,"**, the didactic aside **"Note that"**. The test in that file is the
   right one: the first author should read it and think *"yes, that sounds like me"*. Do not sprinkle
   connectors mechanically.
4. `paper/style/AGENT4CT_JARGON.md` — the *method*, not the content. Fix the reader model, then gloss
   every term that reader would not know, on first use.
5. `paper/style/README.md` — **our** reader model, which differs from Agent4CT's.

## Reader model

A computer-vision researcher at a medical-imaging workshop. Fluent in deep learning, ensembles,
precision and recall, adversarial attacks. **Not** fluent in named-entity recognition, co-reference,
keyed hashing, surrogate generation, or clinical text. Gloss on first use: named entity, span,
co-reference chain, surrogate, the difference between pseudonymisation and anonymisation, keyed
hashing, information-weighted precision.

## Hard rules

- **Never write A1–A5 or N0–N4.** The attacks have names: *frequency matching*, *context linkage*,
  *LLM candidate ranking*, *learned linkage*, and *dictionary lookup* (defined, not run). The key
  normaliser is described by what it does, never numbered.
- **Every figure and table is referenced from running prose**, in a sentence that says what it shows
  and why it matters — never a bare "see Table 2". Use `\ref{}` and `\label{}`.
- **Mark every provisional number** with `\provisional{...}` (define the macro in `main.tex` as
  something visible, e.g. a coloured box), so a reader of the draft can see instantly what is not
  final. The large-ensemble results are provisional; say so in the discussion too.
- **Invent nothing.** Every number must come from `paper/OUTLINE.md` or a file under `results/`. If a
  number is needed and not available, write `\provisional{TBD}` and a comment saying what is missing.
  Do not guess citations, DOIs or author names either — cite only what is in `references/`.
- British spelling, consistent with the repository.

## The figure

Produce a **TikZ overview figure** for §2 — one column wide, showing the design: a document flowing
through detection (a pool of detectors, combined by a rule) into the three conditions, then into the
three measurement families. This is a **first sketch**; arrows will be corrected afterwards, so keep
the node positions explicit and easy to nudge, use named coordinates rather than relative
positioning, and do not use `positioning` chains that are hard to adjust. Aim for something that
would look good in a paper: consistent rounded boxes, a restrained palette, no drop shadows, labels
that do not collide.

## Tables

Use `booktabs`. No vertical rules. Numbers right-aligned on the decimal point (`siunitx` `S` columns
are available). Caption above the table, one sentence, saying what the reader should take from it.
Keep each table to one column where possible.

## Where things are

- Results: `results/` on the cluster is not reachable from here; the numbers you need are in
  `paper/OUTLINE.md`.
- Literature: `references/standards.md` and `references/text_pseudonymization.md`. Populate
  `paper/references.bib` from these — **only** entries that appear there.
- The experiment specification is `experiment_plan.md` if you need to check a design detail. Do not
  edit it.

## Do not

- Do not edit `experiment_plan.md`, `README.md`, `CLAUDE.md`, or anything under `experiments/` or
  `src/`.
- Do not write an abstract. It is written last.
- Do not add a related-work section; the literature goes where it does work.
