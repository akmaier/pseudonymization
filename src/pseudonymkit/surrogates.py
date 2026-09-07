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

__all__ = ["SurrogateForm", "SURROGATES"]


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
