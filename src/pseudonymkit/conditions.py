"""The three conditions (``experiment_plan.md`` §7), as configurations over the existing axes.

AM collapsed the design to three conditions on 2026-09-10.  The key normaliser, the cryptographic
technique and the surrogate form are **not varied**: they are fixed at one setting each, chosen from
the literature, and together they define what B and C are.

====  ===============  ==============================================  ========  ==============
       condition        identifiers become                              linkable  reversible
====  ===============  ==============================================  ========  ==============
 A     full data        the text as the corpus ships it                 yes       —
 B     pseudonymised    a realistic, locale-appropriate surrogate; one  yes       with the key
                        entity, one surrogate, corpus-wide
 C     de-identified    a typed placeholder without an index, so all    no        no
                        persons look alike
====  ===============  ==============================================  ========  ==============

**The axes are not deleted.**  A condition is a *configuration* over them, which is what keeps the
package able to answer the questions §17 records as unrun — the document-randomised policy, an
unkeyed variant of B — the day AM adds a fourth condition.  What this module does is fix the
configuration so no experiment can drift into a different one by accident.

## Why B is configured as it is

Deterministic policy, HMAC-SHA256, N2 normaliser, a realistic surrogate drawn locale-appropriately.
B is *"hiding in plain sight"*, the field's standard since Carrell et al. (JAMIA 2012), and it is
what this study's own German baseline does — Eder et al. (RANLP 2019) replace *"a person originally
named 'John Doe'… as 'Bill Powers'"*.  It is also what runs in production.  HMAC because ENISA calls
it *"generally considered a robust pseudonymisation technique from a data protection point of view"*
and, being keyed, it resists the dictionary attack.  N2 because it casefolds and strips titles and
punctuation, so *"Dr. Weber"*, *"weber"* and *"Weber"* resolve to one entity while distinct people do
not — the least aggressive normalisation that still recognises the same person written two ways.

## Why C differs from B in exactly one level

C keeps N2, the deterministic policy and HMAC, and changes only the surrogate form.  The placeholder
discards the index, so the technique's output goes nowhere — and that is the point: the pair differ
in one thing, so a difference between them is attributable to that thing.  Anything else would make
H2's exchange rate — what de-identification costs in cross-document utility and buys in leakage —
a comparison between two pipelines rather than between two conditions.

## Why A is a pipeline at all

Condition A is the unmodified text, so it needs no engine.  It gets one anyway, because §8.4 runs
A3, A4 and A5 **on condition A as the ceiling** — what an adversary recovers with no protection at
all — and without that a leakage rate on B or C has no scale.  The attacks read a
:class:`~pseudonymkit.engine.PseudonymisedCorpus`, so :class:`Unmodified` produces one whose text is
byte-identical to the corpus and whose assignments map each mention to its own surface.  Every attack
then runs on A unchanged, with no special case anywhere downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .domain import Assignment, Corpus, Document, Mention, PseudonymMapping
from .engine import PseudonymisedCorpus, PseudonymisedDocument, Pseudonymiser
from .inventories import Inventory
from .keys import NORMALISERS, Normaliser, entity_key
from .policies import POLICIES
from .surrogates import SURROGATES
from .techniques import TECHNIQUES

__all__ = ["ConditionSpec", "SPECS", "build", "Unmodified", "NORMALISER", "POLICY", "TECHNIQUE"]

NORMALISER = "N2"
"""Fixed for B and C (§7).  Not an axis in this design."""

POLICY = "deterministic"
TECHNIQUE = "hmac"

POOLED = ("PERSON", "LOC", "ORG", "DEMOGRAPHIC")
"""Types condition B renders by drawing from an inventory."""

CONSTRUCTED = ("CODE",)
"""Types condition B renders by building a string of the same shape — there is no list to draw
from.  35.2 % of the study's mentions, and all 444,332 of Enron's."""

UNCHANGED = ("DATETIME", "QUANTITY", "MISC")
"""Types condition B leaves alone (AM, 2026-09-13).

Reported, not hidden: this is 9.6 %, 3.8 % and 1.1 % of the study's mentions respectively, and for
CARDIO:DE — where 45,176 of 55,154 mentions are dates — it means 82 % of the corpus's identifiers
are carried into condition B verbatim.  See :class:`~pseudonymkit.surrogates.PassThrough` for what
the literature does instead, which for DATETIME is to shift."""


@dataclass(frozen=True, slots=True)
class ConditionSpec:
    """One condition, in the terms §7's table states it and a results row must record it."""

    name: str
    label: str
    identifiers: str
    linkable: bool
    reversible: str
    normaliser: str | None
    policy: str | None
    technique: str | None
    surrogate: str | None
    stability_meaningful: bool
    """False for A (nothing was replaced) and for C (every identifier of a type is one string, so
    there is no mapping whose integrity could be measured — §8.2)."""

    def describe(self, key_id: str | None = None) -> dict[str, object]:
        """The cell configuration for a results row (§9).

        ``key_id`` and never key material: a run records which key it used, not the key.
        """
        return {
            "condition": self.name,
            "condition_label": self.label,
            "linkable": self.linkable,
            "reversible": self.reversible,
            "normaliser": self.normaliser,
            "policy": self.policy,
            "technique": self.technique,
            "surrogate": self.surrogate,
            "key_id": key_id,
        }


SPECS: Mapping[str, ConditionSpec] = {
    "A": ConditionSpec(
        name="A",
        label="full data",
        identifiers="the text as the corpus ships it",
        linkable=True,
        reversible="—",
        normaliser=None,
        policy=None,
        technique=None,
        surrogate=None,
        stability_meaningful=False,
    ),
    "B": ConditionSpec(
        name="B",
        label="pseudonymised",
        identifiers=(
            "a realistic, locale-appropriate surrogate; the same entity receives the same "
            "surrogate throughout the corpus. Names, places, organisations and demographic "
            "attributes are drawn from an inventory; codes are rebuilt to the same shape; dates, "
            "quantities and MISC are left unchanged"
        ),
        linkable=True,
        reversible="with the key",
        normaliser=NORMALISER,
        policy=POLICY,
        technique=TECHNIQUE,
        surrogate="routed",
        stability_meaningful=True,
    ),
    "C": ConditionSpec(
        name="C",
        label="de-identified",
        identifiers="a typed placeholder without an index — [PERSON], [LOCATION]",
        linkable=False,
        reversible="no",
        normaliser=NORMALISER,
        policy=POLICY,
        technique=TECHNIQUE,
        surrogate="placeholder",
        stability_meaningful=False,
    ),
}
"""The three levels of the condition axis.  Fifteen cells with the five corpora (§7)."""


class Unmodified:
    """Condition A: the corpus, unchanged, in the shape the rest of the pipeline consumes.

    Interface-compatible with :class:`~pseudonymkit.engine.Pseudonymiser` so that a runner, a metric
    or an attack takes a condition without asking which one it has.

    Two details make it a faithful ceiling rather than an approximation:

    * **The text is reconstructed from the document, not copied.**  Each mention is "replaced" by the
      document's own characters at its offsets, so the output is byte-identical *and* the assignment
      list is complete — which is what lets :func:`pseudonymkit.attacks.profiles.build_queries` and
      :func:`~pseudonymkit.attacks.profiles.truth_map` run on A with no special case.
    * **Overlapping mentions are skipped exactly as B and C skip them.**  If A kept a mention that B
      dropped, the two conditions would be scored on different entity populations and the comparison
      would be confounded by the overlap rule rather than by the condition.

    The scope key is per *mention*, not per entity: an entity's surface forms differ ("Dr. Weber",
    "Weber"), and a per-entity assignment would reuse the first one and quietly rewrite the text.
    """

    name = "A"
    spec = SPECS["A"]

    def __init__(self, normaliser: Normaliser | None = None) -> None:
        self.normaliser = normaliser or NORMALISERS.create(NORMALISER)
        self.mapping = PseudonymMapping()
        self._next = 0

    def assign(self, mention: Mention, surface: str) -> Assignment:
        """An identity assignment: the entity's own surface form is its "pseudonym"."""
        key = entity_key(surface, mention.type, self.normaliser)
        assignment = Assignment(
            scope_key=(key, mention.doc_id, mention.mention_id),
            entity_key=key,
            entity_type=mention.type,
            index=self._next,
            surface=surface,
        )
        self._next += 1
        return self.mapping.put(assignment)

    def pseudonymise(self, document: Document) -> PseudonymisedDocument:
        ordered = sorted(document.mentions, key=lambda m: (m.span.start, -m.span.length))
        assignments: list[Assignment] = []
        skipped: list[Mention] = []
        cursor = 0
        for mention in ordered:
            if mention.span.start < cursor:
                skipped.append(mention)
                continue
            surface = document.text[mention.span.start : mention.span.end]
            assignments.append(self.assign(mention, surface))
            cursor = mention.span.end
        return PseudonymisedDocument(
            document=document,
            text=document.text,
            assignments=tuple(assignments),
            skipped=tuple(skipped),
        )

    def pseudonymise_corpus(self, corpus: Corpus | Iterable[Document]) -> PseudonymisedCorpus:
        documents = corpus.documents if isinstance(corpus, Corpus) else corpus
        return PseudonymisedCorpus(
            documents=tuple(self.pseudonymise(d) for d in documents),
            mapping=self.mapping,
        )


def build(
    condition: str,
    *,
    inventory: Inventory | None = None,
    key: bytes | None = None,
) -> Pseudonymiser | Unmodified:
    """Construct one condition.

    ``inventory`` is required for B — a realistic surrogate has to come from somewhere, and §14 fixes
    the gazetteers (US Census surnames, UCI given names, GeoNames cities).  It is not this module's
    business which languages that inventory covers; a document in a language it does not cover raises
    from the inventory, loudly, rather than being given surrogates from another language (§1).

    ``key`` is HMAC key material and is required for B.  C accepts it and ignores it, because its
    placeholder discards the index; passing the same key to both is what keeps the two conditions one
    axis level apart.  **Only a key id is ever recorded with a result** (see
    :meth:`ConditionSpec.describe`); key material lives in the gitignored config and never in a log,
    a results row or a commit.
    """
    spec = SPECS.get(condition.upper())
    if spec is None:
        raise KeyError(f"unknown condition {condition!r}; available: {', '.join(sorted(SPECS))}")

    if spec.name == "A":
        return Unmodified()

    if spec.name == "B":
        if inventory is None:
            raise ValueError(
                "condition B replaces identifiers with realistic surrogates and needs an inventory; "
                "see pseudonymkit.gazetteers.build_inventory"
            )
        if key is None:
            raise ValueError(
                "condition B is HMAC-SHA256 (experiment_plan.md §7) and needs key material; "
                "load it from the gitignored config and record only its key id with the result"
            )
        # One condition, but not one rendering rule.  A person is drawn from a name list, a phone
        # number has to be constructed digit by digit, and a date is left as it stands.  Routing
        # keeps all three inside the surrogate-form axis, so B and C still differ in exactly one
        # level (§7) — which is what makes H2's exchange rate attributable to the condition.
        pooled = SURROGATES.create("realistic", inventory=inventory)
        surrogate = SURROGATES.create(
            "routed",
            routes={
                **{t: pooled for t in POOLED},
                **{t: SURROGATES.create("format_preserving") for t in CONSTRUCTED},
                **{t: SURROGATES.create("unchanged") for t in UNCHANGED},
            },
            default=pooled,
        )
    else:
        surrogate = SURROGATES.create("placeholder")

    assert spec.normaliser and spec.policy and spec.technique  # B and C fix all three (§7)
    return Pseudonymiser(
        NORMALISERS.create(spec.normaliser),
        POLICIES.create(spec.policy),
        TECHNIQUES.create(spec.technique, key=key),
        surrogate,
    )
