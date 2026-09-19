"""Axis C: the surrogate form.

The technique produces an index; the surrogate form renders it into text.  Three levels, in
increasing order of how much of the original they preserve — and therefore, per H4, in increasing
order of both utility and leakage.
"""

from __future__ import annotations

import calendar
import hashlib
import re
from typing import Callable, Mapping, Protocol, Sequence, runtime_checkable

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
    "Checked",
    "SurrogateRejected",
    "code_is_consistent",
    "differs_from_source",
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

    def _date_shaped(self, index: int, source: str) -> str | None:
        """Generate a valid date or time directly, or ``None`` if the source is not one.

        Redrawing until a random string happens to be a real date works — a valid ``dd.mm.yyyy``
        turns up about one draw in twenty-seven — but adding a plausible-year band takes it to one
        in twelve hundred, and a blind retry loop would then exhaust its budget on two thirds of
        date-shaped spans.  So the components are drawn inside their own ranges instead, and
        :class:`Checked` stays as the guarantee rather than the mechanism.

        Every component keeps the width it had, so the surrogate is the same length as the original
        and a one-digit day stays one digit.
        """
        digits = self._keystream(index, 8)

        def year_of(width: int, a: int, b: int) -> int:
            if width == 4:
                low, high = PLAUSIBLE_YEARS
                return low + ((a << 8 | b) % (high - low + 1))
            return a % 100

        def day_of(raw: int, width: int, year: int, month: int) -> int:
            top = calendar.monthrange(year, month)[1]
            return (raw % min(top, 9 if width == 1 else top)) + 1

        match = _DMY.match(source)
        if match:
            day_s, sep, month_s, year_s = match.groups()
            year = year_of(len(year_s), digits[0], digits[1])
            month = (digits[2] % (9 if len(month_s) == 1 else 12)) + 1
            day = day_of(digits[3], len(day_s), year if len(year_s) == 4 else year + 2000, month)
            return (f"{day:0{len(day_s)}d}{sep}{month:0{len(month_s)}d}{sep}"
                    f"{year:0{len(year_s)}d}")

        match = _YMD.match(source)
        if match:
            year_s, sep, month_s, day_s = match.groups()
            year = year_of(4, digits[0], digits[1])
            month = (digits[2] % (9 if len(month_s) == 1 else 12)) + 1
            day = day_of(digits[3], len(day_s), year, month)
            return (f"{year:04d}{sep}{month:0{len(month_s)}d}{sep}{day:0{len(day_s)}d}")

        match = _TIME.match(source)
        if match:
            hour_s, minute_s, second_s = match.groups()
            hour = digits[0] % (10 if len(hour_s) == 1 else 24)
            out = f"{hour:0{len(hour_s)}d}:{digits[1] % 60:02d}"
            return out if second_s is None else f"{out}:{digits[2] % 60:02d}"
        return None

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
        dated = self._date_shaped(index, source)
        if dated is not None:
            return prefix + dated
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


# ---------------------------------------------------------------------------------------------
# Consistency: a surrogate that is the wrong *kind* of thing is worse than no surrogate at all.
# ---------------------------------------------------------------------------------------------


class SurrogateRejected(RuntimeError):
    """No candidate passed the check within the attempt budget.

    Raised rather than returning the last failing candidate: emitting a surrogate that is known to
    be wrong is the silent substitution §1 forbids, and a check that can never pass is a defect in
    the check, which should be visible.
    """


def _redraw(index: int, attempt: int) -> int:
    """A fresh index derived from the original, deterministically.

    Redrawing must not break stability: the same entity must reach the same surrogate everywhere in
    the corpus, so the retry sequence is a pure function of the first index rather than of a random
    source or of how many entities were seen before.
    """
    digest = hashlib.sha256(f"redraw:{index}:{attempt}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


_DMY = re.compile(r"^(\d{1,2})([./-])(\d{1,2})\2(\d{2,4})$")
_YMD = re.compile(r"^(\d{4})([./-])(\d{1,2})\2(\d{1,2})$")
_TIME = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")

PLAUSIBLE_YEARS = (1900, 2099)
"""The band a four-digit surrogate year must fall in.

``42.87.1008`` became ``16.01.5628`` once the date was required to be real — a valid date, and still
not one a clinical letter would carry (AM, 2026-09-15).  The upper bound is deliberately well past
today: CARDIO:DE's dates were shifted by a constant per-document offset before release and admission
dates already run into the 2030s, so a tighter ceiling would make the surrogates separable from the
originals by year alone.

A two-digit year is left unconstrained — every value 00-99 is plausible."""


def _plausible_year(year: int) -> bool:
    return PLAUSIBLE_YEARS[0] <= year <= PLAUSIBLE_YEARS[1]


def _valid_dmy(day: int, month: int, year: int) -> bool:
    return 1 <= month <= 12 and 1 <= day <= calendar.monthrange(year, month)[1]


def _date_like(value: str) -> bool:
    return bool(_DMY.match(value) or _YMD.match(value) or _TIME.match(value))


def _date_valid(value: str) -> bool:
    """True when ``value`` is not date-shaped at all, or is date-shaped **and** a real date."""
    match = _DMY.match(value)
    if match:
        day, _, month, year = match.groups()
        if len(year) == 2:
            return _valid_dmy(int(day), int(month), int(year) + 2000)
        return _plausible_year(int(year)) and _valid_dmy(int(day), int(month), int(year))
    match = _YMD.match(value)
    if match:
        year, _, month, day = match.groups()
        return _plausible_year(int(year)) and _valid_dmy(int(day), int(month), int(year))
    match = _TIME.match(value)
    if match:
        hour, minute, second = match.groups()
        return int(hour) < 24 and int(minute) < 60 and (second is None or int(second) < 60)
    return True


def code_is_consistent(surrogate: str, mention: Mention) -> bool:
    """A CODE surrogate must be the same *kind* of string as the one it replaces.

    Format preservation copies the layout but not the meaning, so a date-shaped code came back as
    ``42.87.1008`` — day 42 of month 87 — on the first real CARDIO:DE build.  No source in the
    surveyed literature imposes validity on code surrogates, and Carrell concedes the handling is
    not uniform even within one engine; but a value no reader or parser would accept is not
    "realistic" in the sense the condition claims, and it advertises which spans were replaced.

    So: if the original is a real date or time, the surrogate must be one too.  And the surrogate must
    differ from the original — a short numeric code can otherwise collide with itself and silently
    pass the original through.  Anything else is only checked for that.

    **Validity is demanded only where the original has it**, and the qualification is not pedantry.
    ``_DMY`` matches any ``n.n.nnn`` string, so OntoNotes' citation-like codes are date-*shaped*
    without being dates: ``2.31.610`` is month 31.  Requiring its surrogate to be a real date fails
    twice over.  It is unsatisfiable — format preservation keeps the three-digit trailing field, and
    a three-digit year can never fall in ``PLAUSIBLE_YEARS``, so all 512 draws were rejected before
    they could differ from one another, which is how the first OntoNotes build died.  And it is
    backwards: turning a non-date into a valid date makes the surrogate *more* separable from the
    original, which is the exact failure this check was written to prevent.
    """
    # A span with nothing substitutable in it — a bare "(" , which the union rule really did label
    # CODE — can never differ from itself, because format preservation keeps punctuation in place.
    # Requiring a difference there is unsatisfiable and, more to the point, meaningless: a span with
    # no letter and no digit carries no identifier to conceal.  Everything else must change.
    if any(c.isascii() and c.isalnum() for c in mention.surface) and surrogate == mention.surface:
        return False
    if _date_like(mention.surface) and not _date_valid(mention.surface):
        return True          # the original is not a real date either; its shape is all we can match
    return _date_valid(surrogate)


def differs_from_source(surrogate: str, mention: Mention) -> bool:
    """The surrogate must not be the value it replaces.

    Applied to the types drawn from a large pool — PERSON, LOC, ORG — where an index collision means
    an identifier survives into the released text under the name of a pseudonym.

    **Not** applied to DEMOGRAPHIC, and that is deliberate.  Its pools are small and sometimes
    binary — CARDIO:DE's ``SALUTE`` is *Herr* and *Frau* — and forcing a difference on a two-valued
    category turns the mapping into a bijection: every *Herr* becomes *Frau* and the attacker
    recovers the original by inverting it.  A collision is the lesser harm there, and for a
    categorical attribute it is not even a leak: it is one of the values the category has.
    """
    return surrogate != mention.surface


@SURROGATES.register("checked")
class Checked:
    """Wraps a surrogate form with a predicate, redrawing until it passes.

    AM, 2026-09-15: *"It can simply draw again if the check did not pass and just create a new
    one."*  The redraw is deterministic (see :func:`_redraw`), so stability is untouched: the same
    entity still reaches the same surrogate everywhere, it is merely a later candidate in that
    entity's own sequence.

    ``attempts`` is 512 rather than a handful because the date case genuinely needs it.  A random
    ``dd.mm.yyyy`` is a real date about 3.7 % of the time, so a dozen tries would leave roughly half
    of them failing; at 512 the chance of exhausting the budget is about 4e-9 per span, which over
    the study's 448,774 CODE mentions is comfortably below one.  Each attempt is one hash of a short
    string, so the cost is invisible next to a gateway call.
    """

    name = "checked"

    def __init__(
        self,
        form: SurrogateForm,
        check: Callable[[str, Mention], bool],
        attempts: int = 512,
    ) -> None:
        self._form = form
        self._check = check
        self._attempts = attempts
        self.redraws = 0
        """Total extra draws taken.  A rate worth reporting: it says how often the pool or the
        format generator produces something the condition cannot honestly call a surrogate."""

    @property
    def inner(self) -> SurrogateForm:
        return self._form

    def render(self, index: int, mention: Mention, language: str) -> str:
        for attempt in range(self._attempts):
            candidate = self._form.render(
                index if attempt == 0 else _redraw(index, attempt), mention, language
            )
            if self._check(candidate, mention):
                self.redraws += attempt
                return candidate
        raise SurrogateRejected(
            f"no surrogate passed {self._check.__name__} for type={mention.type!r} in "
            f"{self._attempts} draws; last candidate {candidate!r} for {mention.surface!r}. "
            "Either the pool is too small to avoid the original, or the check cannot be satisfied."
        )
