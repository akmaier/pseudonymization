"""Axis C: the surrogate form.

The technique produces an index; the surrogate form renders it into text.  Three levels, in
increasing order of how much of the original they preserve — and therefore, per H4, in increasing
order of both utility and leakage.
"""

from __future__ import annotations

import hashlib
from typing import Mapping, Protocol, Sequence, runtime_checkable

from .domain import Mention
from .inventories import Inventory
from .registry import Registry

__all__ = [
    "SurrogateForm",
    "SURROGATES",
    "TypedPlaceholder",
    "PLACEHOLDER_NAMES",
    "PassThrough",
    "FormatPreserving",
    "TypeRouted",
    "URL_PREFIXES",
]

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


# ---------------------------------------------------------------------------------------------
# Renderers for the types that have no surrogate pool.
#
# Three of the eight harmonised types cannot be drawn from a list, and for a different reason each
# time.  What follows is what the literature actually does, read in full and quote-verified on
# 2026-09-14; see references/text_pseudonymization.md for the sources.
# ---------------------------------------------------------------------------------------------


@SURROGATES.register("unchanged")
class PassThrough:
    """Returns the original surface.  The type is **not** pseudonymised.

    Used for ``DATETIME``, ``QUANTITY`` and ``MISC`` (AM, 2026-09-13: *"I would avoid DATETIME
    manipulation ... Quantity must remain unaffected. I don't think that MISC is relevant"*).

    This is a deliberate, reported deviation for DATETIME and a well-supported choice for QUANTITY:

    * **DATETIME.** The clinical norm is date *shifting* — one random offset held constant across a
      record unit, so intervals survive while absolute anchoring does not.  Stubbs & Uzuner's i2b2
      2014 corpus shifts "all of the DATEs forward by the same random number of years, months, and
      days", over a patient's merged longitudinal record rather than per document; Carrell's MIST
      does the same per document.  Not shifting is therefore a departure from practice, and the
      fraction of mentions it leaves untouched has to be reported rather than assumed away — it is
      82 % of CARDIO:DE's mentions.
    * **QUANTITY.** No source in the surveyed literature gives any mechanism for percentages or
      monetary values in narrative text; i2b2, MIST, BRATsynthetic, PHICON and Sariyar's 2026 scoping
      review have no such category at all.  Leaving it alone is the field's implicit position.
    * **MISC.** i2b2's OTHER was dropped from the gold standard as "a useless tag for a
      de-identification challenge" and BRATsynthetic routed its UNIQUE category to manual redaction.
      There is no automated treatment to copy.

    Pass-through is a surrogate form rather than a special case in the engine on purpose: it keeps
    B and C exactly one axis level apart, and it keeps the offset bookkeeping identical for a type
    that happens not to change.
    """

    name = "unchanged"

    def render(self, index: int, mention: Mention, language: str) -> str:
        return mention.surface


URL_PREFIXES: tuple[str, ...] = ("https://", "http://", "mailto:", "ftp://", "file://", "www.")
"""Kept verbatim at the head of a CODE surrogate.

Eder et al. (2019) preserve exactly this — "the subdomain 'www' and commonly used URL schemes like
'http', 'https', 'ftp', 'file' and 'mailto'" — because a scheme is syntax rather than identity, and
randomising it produces a string no reader or parser would accept as a URL."""


@SURROGATES.register("format_preserving")
class FormatPreserving:
    """A CODE surrogate: same shape, none of the original characters.

    Every ASCII digit becomes a digit, every ASCII letter a letter of the same case, and every other
    character — ``@``, ``.``, ``-``, ``/``, spaces — is kept where it stands.  Length and layout
    therefore survive exactly; the content does not.

    **This is the literature's consensus, and it is nearly unanimous.**  Stubbs & Uzuner generated
    the i2b2 2014 surrogates by "randomly selecting new strings of digits/letters of the same length
    and format"; Eder et al. substitute "each digit ... with a randomly generated alternative digit,
    each alphabetic character ... with a randomly generated alternative letter of the same case and
    alphabet", leaving "other characters like '@' or punctuation marks ... as is"; BRATsynthetic
    reconstructs format by regex per identifier type.  No surveyed source generalises a code, and
    only Sánchez & Batet's C-sanitized departs, by deleting codes outright.

    Two recorded disagreements this class resolves one way rather than silently:

    * **How much of the string to overwrite.**  Carrell's MIST replaces only "some parts of the
      identifier (eg, the last four digits of a phone number) preserving the original format", so a
      true prefix — an area code, a bank's sort code — survives into the released text.  i2b2 and
      Eder overwrite the whole string.  This class follows i2b2 and Eder: a retained prefix is real
      data, and this study measures leakage.
    * **Validity.**  No source imposes checksums, valid dialling codes or ZIP/city coherence, and
      Carrell concedes the handling is not uniform even within one engine.  Neither does this class.
      A surrogate here is well-formed, not valid, and nothing downstream may assume otherwise.

    The characters come from the pseudonym index, not from an RNG, so the mapping is deterministic
    and stable corpus-wide like every other surrogate: one entity, one code, every time it appears.
    Two surface forms of one entity that differ in length render differently by construction — that
    is inherent to preserving format, and is why ``entity_key`` normalisation matters upstream.
    """

    name = "format_preserving"

    def __init__(self, prefixes: Sequence[str] = URL_PREFIXES) -> None:
        self._prefixes = tuple(prefixes)
        self.unsubstitutable = 0
        """Characters that are alphanumeric but not ASCII, and so were left in place.

        Measured over all four corpora on 2026-09-14 this is **zero** — every one of the 9,764,204
        characters in the study's 448,774 CODE spans is an ASCII letter, an ASCII digit, punctuation
        or a space.  The counter exists so that a corpus which breaks that assumption is reported
        rather than silently leaking the characters it could not handle (§1)."""

    @staticmethod
    def _keystream(index: int, length: int) -> bytes:
        """Deterministic bytes from the pseudonym index.

        The index is 32 bits and a code may be far longer, so it is stretched by counter-mode
        hashing rather than reused.  This adds no secrecy — the HMAC upstream is what makes the
        mapping unguessable — it only supplies enough independent bytes to choose each character.
        """
        out = bytearray()
        counter = 0
        while len(out) < length:
            out += hashlib.sha256(f"{index}:{counter}".encode("utf-8")).digest()
            counter += 1
        return bytes(out[:length])

    def render(self, index: int, mention: Mention, language: str) -> str:
        source = mention.surface
        prefix = ""
        # Repeatedly, not once: Eder et al. keep the scheme *and* the 'www' subdomain, so
        # "https://www.x.org" must surrender both before the rest is rewritten.
        while True:
            for candidate in self._prefixes:
                if source.lower().startswith(candidate):
                    prefix += source[: len(candidate)]
                    source = source[len(candidate) :]
                    break
            else:
                break
        stream = self._keystream(index, len(source))
        out: list[str] = []
        for character, byte in zip(source, stream):
            if character.isascii() and character.isdigit():
                out.append(chr(ord("0") + byte % 10))
            elif character.isascii() and character.isalpha():
                base = "a" if character.islower() else "A"
                out.append(chr(ord(base) + byte % 26))
            else:
                if character.isalnum():           # non-ASCII alphanumeric: kept, and counted
                    self.unsubstitutable += 1
                out.append(character)
        return prefix + "".join(out)


@SURROGATES.register("routed")
class TypeRouted:
    """Dispatches to a different renderer per entity type.

    Condition B is one condition but not one rendering rule: a person is drawn from a name list, a
    phone number has to be constructed, and a date is left alone.  Routing keeps that a property of
    the *surrogate form* — a single axis level, as §7 requires — rather than scattering type tests
    through the engine, so B and C still differ in exactly one thing.
    """

    name = "routed"

    def __init__(self, routes: Mapping[str, SurrogateForm], default: SurrogateForm) -> None:
        self._routes = dict(routes)
        self._default = default

    def for_type(self, entity_type: str) -> SurrogateForm:
        return self._routes.get(entity_type, self._default)

    def render(self, index: int, mention: Mention, language: str) -> str:
        return self.for_type(mention.type).render(index, mention, language)
