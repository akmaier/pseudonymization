"""Axis C: the surrogate form.

The technique produces an index; the surrogate form renders it into text.  Three levels, in
increasing order of how much of the original they preserve — and therefore, per H4, in increasing
order of both utility and leakage.
"""

from __future__ import annotations

from typing import Mapping, Protocol, Sequence, runtime_checkable

from .domain import Mention
from .inventories import Inventory
from .registry import Registry

__all__ = ["SurrogateForm", "SURROGATES", "TypedPlaceholder", "PLACEHOLDER_NAMES"]

PLACEHOLDER_NAMES: Mapping[str, str] = {"LOC": "LOCATION"}
"""Harmonised type -> the name that appears inside the placeholder.

``experiment_plan.md`` §7 gives condition C's examples as ``[PERSON]`` and ``[LOCATION]``, and
``LOCATION`` is also Presidio's own name for the class whose default operator shape C adopts.  The
harmonised taxonomy calls it ``LOC`` (§10), so exactly one entry is needed; everything else appears
under its harmonised name."""


@runtime_checkable
class SurrogateForm(Protocol):
    """Renders a pseudonym index into replacement text."""

    name: str

    def render(self, index: int, mention: Mention, language: str) -> str: ...


SURROGATES: Registry[SurrogateForm] = Registry("surrogate form")


@SURROGATES.register("tag")
class OpaqueTag:
    """``[PERSON_1]`` — carries the entity type and an ordinal, nothing else.

    Maximum privacy, maximum utility damage: the text stops being text.  The ordinal is assigned in
    order of first appearance so tags stay small and readable; it is a presentation detail and
    carries no information the index did not already carry.
    """

    name = "tag"

    def __init__(self, template: str = "[{type}_{ordinal}]") -> None:
        self._template = template
        self._ordinals: dict[tuple[str, int], int] = {}
        self._next: dict[str, int] = {}

    def render(self, index: int, mention: Mention, language: str) -> str:
        key = (mention.type, index)
        ordinal = self._ordinals.get(key)
        if ordinal is None:
            ordinal = self._next.get(mention.type, 1)
            self._next[mention.type] = ordinal + 1
            self._ordinals[key] = ordinal
        return self._template.format(type=mention.type, ordinal=ordinal)


@SURROGATES.register("placeholder")
class TypedPlaceholder:
    """``[PERSON]`` — the type and nothing else.  Condition C (``experiment_plan.md`` §7).

    **The index is deliberately discarded.**  That single line is what makes C de-identification
    rather than pseudonymisation: every person in the corpus becomes the same string, so there is no
    mapping, nothing is linkable, nothing is reversible, and the stability metrics of §8.2 are not
    merely zero but meaningless — there is no mapping whose integrity could be measured.

    It is also why the technique still runs underneath C.  B and C differ in **exactly one axis
    level**, the surrogate form; keeping the rest identical is what makes the pair a clean contrast
    for H2 rather than two differently configured pipelines.

    The shape is Presidio's default replacement operator, which is also what HIPAA Safe Harbor
    implies.  Tau-Eval (arXiv 2506.05979) measured precisely this — a Presidio placeholder against a
    frozen model — as near-lossless across eight tasks, so C is the field's real comparison point
    rather than a straw man.
    """

    name = "placeholder"

    def __init__(
        self, template: str = "[{type}]", names: Mapping[str, str] = PLACEHOLDER_NAMES
    ) -> None:
        self._template = template
        self._names = dict(names)

    def render(self, index: int, mention: Mention, language: str) -> str:
        return self._template.format(type=self._names.get(mention.type, mention.type))


@SURROGATES.register("realistic")
class RealisticSurrogate:
    """A real-looking name drawn from the inventory by index — *John Doe* becomes *Bill Powers*.

    The text stays text, so downstream models still see a well-formed document.  Attributes of the
    original are ignored, so gender and locale are scrambled.
    """

    name = "realistic"

    def __init__(self, inventory: Inventory) -> None:
        self._inventory = inventory

    def render(self, index: int, mention: Mention, language: str) -> str:
        return self._inventory.surface(index, mention.type, language)


@SURROGATES.register("attribute_matched")
class AttributeMatchedSurrogate:
    """A surrogate drawn from the stratum matching the original's attributes.

    Preserves gender, locale and — where the inventory is frequency-weighted — frequency band.
    That is exactly what A2 and A4 consume, so H4 predicts this level buys utility and costs
    privacy.  Which attributes are matched is a reported setting, not a hard-coded choice.
    """

    name = "attribute_matched"

    def __init__(self, inventory: Inventory, attributes: Sequence[str] = ("gender", "locale")) -> None:
        self._inventory = inventory
        self._attributes = tuple(attributes)

    def render(self, index: int, mention: Mention, language: str) -> str:
        stratum: Mapping[str, str] = {
            a: mention.attributes[a] for a in self._attributes if a in mention.attributes
        }
        return self._inventory.surface(index, mention.type, language, stratum or None)
