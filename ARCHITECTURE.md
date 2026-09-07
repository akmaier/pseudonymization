# Architecture

`pseudonymkit` exists so that the **pseudonymisation function and policy** can be an experimental
variable instead of a fixed implementation detail. Everything below follows from that one
requirement, and from a second one: the code should outlive this paper.

```
src/pseudonymkit/
  domain.py        frozen value objects: Span, Mention, Document, Corpus, Assignment, PseudonymMapping
  registry.py      name -> factory, one per axis
  keys.py          entity key normalisers            N0 … N4
  policies.py      axis A: scoping rules             deterministic · document · full
  techniques.py    axis B: key -> index              counter · table · hash · hmac · aes_siv
  surrogates.py    axis C: index -> text             tag · realistic · attribute_matched
  inventories.py   the surrogate pool port           ListInventory · SyntheticInventory
  engine.py        composes one cell                 Pseudonymiser
  metrics/         stability, detection              pure functions over the domain
  detectors/       axis D: the port, span-level rules, and token-level (ROVER-style) voting
    alignment.py   the shared voting grid: tokenise, BIO projection, per-token vote, LLM grounding
tests/             70 tests, stdlib + pytest, no network, no models
```

## The four patterns, and why each is here

**Strategy, one per axis.** Each of the five axes is a `Protocol` with interchangeable
implementations. The engine holds four collaborators and contains **no branch on which policy or
technique is in play**. A sixth technique is a new class, not an edit to `engine.py`.

**Registry + factory.** Every strategy registers under a stable string name, so an experimental
cell is a small dict of strings — `{"normaliser": "N2", "policy": "deterministic", "technique":
"hmac", "surrogate": "tag"}` — and can be reconstructed exactly from a config file or a results row.
That is what makes a factorial design cheap to run *and* cheap to reproduce. Third-party code
extends an axis by registering into the same registry; nothing in the package needs changing.

**Ports and adapters.** `domain.py` knows nothing about corpora, models, files or the network.
Corpora are converted *into* it, detectors emit into it, metrics read it. Swapping TAB for Enron, or
Presidio for an LLM, touches one adapter. `Inventory` is a port for the same reason: the engine must
not learn whether names came from a census file or a synthetic generator.

**Immutable value objects.** Every domain type is a frozen dataclass. A run must be reproducible
from its configuration and seed, and mutable state shared between cells is the usual way that stops
being true. The two objects that *are* stateful — `Pseudonymiser` and the `counter`/`table`
techniques — are documented as one-instance-per-run, because their state is the mechanism being
studied.

## The composition that makes 45 cells cheap

```
mention ─▶ entity key ─▶ scope key ─▶ index ─▶ surface form
           keys.py       policies.py  techniques.py  surrogates.py
```

Axes A, B and C look like 3 × 5 × 3 separate pipelines. They are not: the policy is only a **scoping
rule** deciding what the key is qualified by, the technique is a **keyed map** to an integer, and
the surrogate form is a **rendering** of that integer. One consequence is worth stating in the
paper: the policy is the only axis that changes what is linkable — no technique can make a
fully-randomised corpus linkable, or a deterministic one unlinkable.

## Quickstart

```python
from pseudonymkit import NORMALISERS, POLICIES, TECHNIQUES, SURROGATES, Pseudonymiser

engine = Pseudonymiser(
    NORMALISERS.create("N2"),
    POLICIES.create("deterministic"),
    TECHNIQUES.create("hmac", key=key_bytes),
    SURROGATES.create("tag"),
)
result = engine.pseudonymise_corpus(corpus)
```

Scoring one cell:

```python
from pseudonymkit.metrics import evaluate_stability
report = evaluate_stability(result, "PERSON", policy="deterministic")
```

Comparing detector ensembles, including hybrids of classical detectors and LLMs:

```python
from pseudonymkit.detectors import COMBINATORS, combination_grid

for members, rule in combination_grid(pool, rules=("union", "vote", "weighted_vote")):
    spans = COMBINATORS.create(rule).combine([out[d] for d in members])
```

## Extending it

| to add | do this |
|---|---|
| a technique | subclass nothing; write a class with `name`, `keyed` and `index()`, decorate with `@TECHNIQUES.register("…")` |
| a surrogate form | class with `name` and `render()`, register in `SURROGATES` |
| a detector | class with `name`, `family` and `detect()`, register in `DETECTORS` |
| a combination rule | subclass `_RuleBase` and implement `_keep()`, or implement `combine()` directly; token-level rules implement `combine_document()` |
| a corpus | write an adapter producing `Document` objects; nothing downstream changes |
| a name inventory | implement the `Inventory` port (`size`, `surface`) |

## Testing

`python -m pytest tests -q` — 70 tests, no network, no model downloads, under a second. Fixtures
build documents by **locating entity strings in the text** rather than by hand-counted offsets, so a
fixture cannot silently drift out of alignment with its own text. (It caught a real bug on the first
run: `Weber` matching inside `Dr. Weber`.)

The stability tests assert the *semantics*, not just execution: fragmentation appears under N2 and
disappears under N3; drift is zero under a deterministic policy and total under a document-randomised
one, with the policy recorded alongside so the number is never read out of context.

## Conventions

- Type hints throughout; `mypy --strict` and `ruff` configured in `pyproject.toml`.
- Docstrings say *why*, not *what* — the trade-off a class embodies, the ENISA clause it implements,
  the failure it is there to measure.
- No secrets in code or results: runs record a **key id**, never key material. Key material lives in
  gitignored `config/`.
- Metrics are pure functions over the domain, so they can be applied to any pipeline's output,
  including one that does not use this engine at all.
