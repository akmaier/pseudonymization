"""Turning CARDIO:DE's tag markup back into a letter — condition A.

CARDIO:DE is the only corpus in the study that does not ship a condition-A text.  TAB, OntoNotes and
Enron carry real names, so A is the text as released; CARDIO:DE was de-identified before release and
the identifiers were left in the running text as IOB tag tokens.  Measured over all 500 letters,
5,864,475 characters: **26,836 tag tokens, 16 types, 19,729 runs**.  A letter that says
``B-SALUTE B-TITLE I-TITLE I-TITLE B-PER I-PER`` where it should say a name is not a clinical letter,
and every downstream measurement — detection, utility, the leakage attacks — needs one that is.

So condition A here is *built*, not read, and this module builds it.  Two products, and the second
matters as much as the first:

1. the letter with every run replaced by a plausible German entity of the right type;
2. **the map** from each run to what replaced it — position, type, surface and the entity it belongs
   to.  That map is the gold: after the fill we know where every identifier in the letter is and what
   it refers to, because we put it there.

## Identity is stipulated, never inferred

The tags mark *where* an identifier stood.  They do not say **who** — two ``B-PER`` runs in one letter
may be one person or two, and nothing in the markup distinguishes them.  Any identity structure is
therefore ours, and the rule is written down rather than guessed at from the filled text:

* **The patient is one entity per letter.**  A ``PER`` run whose preceding context contains
  *Patient* / *Patientin* is a patient mention — 562 of 3,383 runs.  Gender comes from the same cue,
  since the German morphology survives de-identification even though ``Herr``/``Frau`` became
  ``B-SALUTE``.
* **Every other ``PER`` run is a separate person.**  1,699 runs sit after *Mit freundlichen Grüßen*
  and are the signing physicians, 82 follow a referral cue, 1,040 carry no cue at all.  Treating each
  as its own entity is an **upper bound on the entity count** and is recorded as such: a physician
  named in the body and again in the signature receives two names.

Inferring identity from the filled names instead would be circular — the names are ours, so
clustering them measures the generator (``experiment_plan.md`` §8.2).

## Surface variation comes from the run length, not from a coin flip

``B-PER`` alone (1,442 runs) stood for a surname; ``B-PER I-PER`` (1,880) for a given name and a
surname.  Filling them accordingly gives one entity two surface forms exactly where the original
letter had two, which is the fragmentation case §8.2 measures rather than a decoration.  ``TITLE``
behaves the same way: 296 one-token runs, 445 two-token, 762 three-token — ``Dr.``, ``Prof. Dr.``,
``Prof. Dr. med.``

## Two things the markup does that a naive reader gets wrong

* **A run is not every consecutive tag token.**  ``I-`` tokens sometimes resume after intervening
  prose, so joining on tag identity alone swallows the text between them.  A run continues only
  across whitespace or a hyphen.
* **265 ``ADDR`` runs and 93 ``ORG`` runs begin with ``I-`` and no ``B-``.**  The markup is not
  well-formed everywhere; an orphan ``I-`` token starts its own run rather than being dropped.

Every replacement shifts the offsets of everything after it, so :func:`fill_document` remaps the
medication, section and relation layers and the ``<[Pseudo] …>`` date mentions onto the new text.
Those layers are the utility tasks; losing them would cost more than the fill is worth.
"""

from __future__ import annotations

import bisect
import random
import re
from dataclasses import dataclass, replace as _replace
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from ..domain import Document, Mention, Span
from ..serialisation import register_type
from .cardiode import CasAnnotations, MedicationRelation, MedicationSpan, SectionSpan

__all__ = [
    "TagRun",
    "FilledEntity",
    "FillReport",
    "Inventories",
    "find_runs",
    "fill_document",
    "fill_corpus",
    "TAG_TYPES",
]

TAG_TYPES: tuple[str, ...] = (
    "PER", "TITLE", "SALUTE", "ORG", "LOC", "ADDR", "PLZ", "PHONE",
    "DATE", "DAY", "MONTH", "YEAR", "OTHER", "OTHERG", "OTH", "II",
)
"""Every tag type observed in the 500 letters, in descending frequency within its group."""

_BARE_TYPES = ("SALUTE", "TITLE", "OTHERG", "OTHER", "MONTH", "PHONE", "ADDR",
               "DATE", "YEAR", "PER", "ORG", "LOC", "PLZ", "DAY", "OTH")
"""Tag names that also occur **without** the ``B-``/``I-`` prefix — 325 across the 400 letters, and
every one a real remnant rather than German text: ``vom DATE``, ``unserer ORG``, ``Telefon: PHONE``,
and ``SALUTE PER``, two bare tags in a row.  The prefixed pattern could not see them, so they reached
condition A as literal English words in a German letter.

``II`` is deliberately absent.  It occurs 438 times unprefixed and is nearly always the Roman numeral
— ``GOLD II``, ``AV-Block II°``, ``NYHA II`` — so matching it bare would corrupt clinical text.  It is
still filled in its prefixed form.  Ordered longest-first so ``OTHERG`` is not read as ``OTHER``
followed by a stray ``G``."""

_TOKEN = re.compile(
    r"\b[BI]-[A-Z]+\b|(?<![-\w])(?:" + "|".join(_BARE_TYPES) + r")(?![-\w])"
)
"""Word boundaries are load-bearing: without them the prefixed branch matches the ``B-EKG`` inside
``LSB-EKG``, and the bare branch would match ``ORG`` inside a hyphenated compound."""

_JOIN = re.compile(r"\A[ \t]*-?[ \t]*\Z")
"""What may separate two tokens of one run — whitespace, optionally around a hyphen. Nothing else."""

_PSEUDO = re.compile(r"<\[Pseudo\]\s*([^>]*?)\s*>")
"""CARDIO:DE's in-place date marker.  18,145 of them across the 500 letters.

The date inside is already a surrogate, so nothing has to be *chosen* for it — but the angle
brackets are markup, and condition A is a letter, not a marked-up letter (AM, 2026-09-10).  The
marker is therefore unwrapped to the date it carries, which keeps the corpus's own date formats
(``2032-09-04`` beside ``04/12/1980``) rather than imposing one, and the DATETIME gold moves onto
the unwrapped span."""

_DATE_FORMS = (
    re.compile(r"\A(\d{4})-(\d{1,2})-(\d{1,2})\Z"),          # 2032-09-04
    re.compile(r"\A(\d{1,2})/(\d{1,2})/(\d{4})\Z"),          # 04/12/1980
    re.compile(r"\A(\d{1,2})/(\d{1,2})/(\d{2})\Z"),          # 04/09/32
    re.compile(r"\A(\d{1,2})\.(\d{1,2})\.(\d{4})\Z"),        # already German
)


def _german_date(value: str) -> str:
    """Rewrite a date into ``DD.MM.YYYY``, the German convention, or return it unchanged.

    The letters are German; the dates in them are not.  Heidelberg's de-identifier emitted its
    surrogates as ``2032-09-04``, ``04/12/1980`` and ``04/09/32`` — ISO, US-style slash and a
    two-digit-year slash — none of which a German clinician writes, and all three appear in one
    document, sometimes in adjacent rows of one lab table.  Normalising every date the same way
    makes condition A read as German *and* removes a surface cue that separated the dates we
    inserted from the ones the corpus shipped.

    A two-digit year is read against 2000: the corpus's timeline is shifted into the 2030s, so
    ``04/09/32`` is 2032, matching the admission date in the same letter.
    """
    value = value.strip()
    for index, pattern in enumerate(_DATE_FORMS):
        match = pattern.match(value)
        if not match:
            continue
        if index == 0:
            year, month, day = match.groups()
        else:
            day, month, year = match.groups()
        if len(year) == 2:
            year = f"20{year}"
        return f"{int(day):02d}.{int(month):02d}.{year}"
    return value                                       # a month, a year, or free text: leave it


_PTB_BRACKETS = {"-LRB-": "(", "-RRB-": ")", "-LSB-": "[", "-RSB-": "]",
                 "-LCB-": "{", "-RCB-": "}"}
_PTB = re.compile(r"(?<![\w-])(" + "|".join(_PTB_BRACKETS) + r")(?![\w-])")
"""Penn Treebank escapes for brackets, unescaped back to the characters they stand for.

The corpus was tokenised PTB-style, which escapes ``(`` and ``)`` because parentheses *are* the
parse-tree notation.  It was never converted back, and the proof that this is systematic rather than
incidental is that **not one literal parenthesis survives in 5.9 M characters**: 11,655 ``-LRB-`` and
11,755 ``-RRB-``, balancing 11,614 times.  ``-LRB- EF 25% -RRB-`` is simply ``(EF 25%)``.

Condition A is meant to be text a deployment would see, and no clinician writes ``-LRB-``.  Every
model in the study reads this — the detectors now, the frozen task models later — and none of them
met PTB escapes in training.  The substitution is lossless and reversible, which is why it is done
here while ``-UNK-`` is not: see :data:`_UNK`."""

_UNK = re.compile(r"(?<![\w-])-UNK-(?![\w-])")
"""Flattened to ``-`` (AM, 2026-09-13).  5,554 occurrences.

4,801 of them start a line where a sub-bullet character stood — a ``•``, ``–`` or ``○`` outside the
tokeniser's vocabulary — and ``-`` is what the letters already use for a top-level bullet, so the
line reads correctly at the cost of the nesting level.

The ~700 in-line cases are the ones to be aware of when reading a result: the original glyph is
unrecoverable there, and ``Ramipril 5 mg 1 -UNK- -0-0`` is a dosing schedule whose missing character
is plausibly ``½``, which ``-`` does not convey.  Flattening is a decision to prefer clean text over
a marker no model has seen; it is not a recovery, and the count belongs with any result that reads
medication text."""

_NONE_MARKER = re.compile(r"\s*<none>\s*", re.IGNORECASE)
"""178 of these across the 400 letters.  They mark a value the de-identifier removed and could not
type.  Condition A must be text rather than markup, so the token goes — but **nothing is invented in
its place**: a lab value we made up would be fabricated clinical data, and a blank field is what a
missing measurement actually looks like."""

_PATIENT_CUE = re.compile(r"patient(in)?", re.IGNORECASE)
# Case matters here, and only here. German capitalises the formal address *Sie*, and a discharge
# letter is written *to* the referring physician — "wie Sie dem Befund entnehmen" says nothing about
# the patient. Matched case-insensitively, that pronoun made 11 of 400 letters female whose text
# calls the patient *der Patient* (measured 2026-09-14); all 11 carried the masculine noun and none
# were ambiguous. So `patientin` stays case-insensitive — it is a noun and may start a sentence —
# while the pronoun `sie` is matched lower-case only.
_FEMALE_CUE = re.compile(r"(?i:patientin)|\bsie\b")

_MONTHS: tuple[str, ...] = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)

_TITLES: Mapping[int, tuple[str, ...]] = {
    1: ("Dr.", "Prof.", "PD"),
    2: ("Prof. Dr.", "Dr. med.", "PD Dr.", "Dr. rer."),
    3: ("Prof. Dr. med.", "PD Dr. med.", "Dr. med. univ.", "Prof. Dr. rer."),
}

_ORG_FORMS: Mapping[str, Mapping[int, tuple[str, ...]]] = {
    "f": {
        1: ("{city}klinik", "{city}praxis"),
        2: ("Kreisklinik {city}", "Herzklinik {city}"),
        3: ("Kardiologische Praxis {city}", "Medizinische Klinik {city}"),
    },
    "n": {
        1: ("{city}krankenhaus", "Herzzentrum", "Kreiskrankenhaus"),
        2: ("Klinikum {city}", "Herzzentrum {city}", "Krankenhaus {city}"),
        3: ("Universitätsklinikum {city} gGmbH", "Klinikum {city} GmbH",
            "Medizinisches Versorgungszentrum {city}"),
    },
}
"""Grouped by the grammatical gender of the head noun, because the article in front of the slot is
**not** replaced and has to keep agreeing with what lands there.

``unsere Notfallambulanz`` became ``unsere Herzzentrum Oberdorfelden`` — feminine article, neuter
noun. Small, but it is one more surface cue marking exactly the spans we inserted, on top of the
date formats. *Klinik* and *Praxis* are feminine; *Klinikum*, *Krankenhaus* and *Zentrum* neuter."""

_FEMININE_ARTICLE = re.compile(
    r"\b(die|der|eine|einer|unsere|unserer|ihre|ihrer|seine|seiner)\s*$", re.IGNORECASE
)
"""The determiners immediately before an ORG slot that require a feminine head. ``der``/``einer``
are ambiguous (masculine nominative or feminine genitive/dative); feminine is the safe read here,
since the composed heads are never masculine."""
"""Composed rather than drawn from a list, because CodEAlltag's ``org`` sublist is general business
names — *Apfelscheune*, *AC-Cosmetics* — and a discharge letter that refers a patient to one of those
is not a plausible condition-A text.  A real hospital register (Destatis *Krankenhausverzeichnis*,
1,829 site names, free to reproduce with attribution) is the upgrade and is not yet fetched."""

_AREA_CODES: tuple[str, ...] = (
    "030", "040", "0221", "0231", "0341", "0351", "0511", "0611",
    "0621", "0711", "0911", "0931",
)


@register_type
@dataclass(frozen=True, slots=True)
class TagRun:
    """One identifier slot in the released text: ``B-PER I-PER`` and where it sits."""

    start: int
    end: int
    type: str
    tokens: int
    text: str
    """The literal markup, e.g. ``"B-PER I-PER"`` — kept so the map can be checked against the source."""


@register_type
@dataclass(frozen=True, slots=True)
class FilledEntity:
    """What replaced one run, and which entity it belongs to.

    ``entity_id`` is stipulated by the rule in this module's docstring, not read off the corpus.
    ``role`` records which branch of that rule applied, so a reader can see how much of the identity
    structure rests on a lexical cue and how much on the upper-bound fallback.
    """

    start: int
    end: int
    """Offsets into the **filled** text."""
    type: str
    surface: str
    entity_id: str
    role: str
    run: TagRun


@dataclass(frozen=True)
class FillReport:
    """What the fill did, per corpus."""

    documents: int = 0
    runs: int = 0
    entities: int = 0
    by_type: Mapping[str, int] = None  # type: ignore[assignment]
    orphan_runs: int = 0
    """Runs that began with an ``I-`` token and no ``B-``."""
    layers_remapped: int = 0

    def __str__(self) -> str:
        types = ", ".join(f"{k} {v}" for k, v in sorted((self.by_type or {}).items()))
        return (
            f"{self.documents} letters, {self.runs} runs filled, {self.entities} entities, "
            f"{self.orphan_runs} orphan runs, {self.layers_remapped} annotation spans remapped\n"
            f"  by type: {types}"
        )


class Inventories:
    """The German name, place and street lists, as CodEAlltag ships them.

    Eder et al.'s substitute lists are the right source here: they are the inventory the German
    pseudonymisation baseline this study cites already used, so the fill is citable rather than
    improvised.  Sizes as found: 53,028 surnames, 441 male and 534 female given names, 91,899 cities
    across DE/AT/CH, 51,583 street names.
    """

    def __init__(
        self,
        family: Sequence[str],
        male: Sequence[str],
        female: Sequence[str],
        city: Sequence[str],
        street: Sequence[str],
    ) -> None:
        for name, pool in (("family", family), ("male", male), ("female", female),
                           ("city", city), ("street", street)):
            if not pool:
                raise ValueError(f"inventory {name!r} is empty")
        self.family = tuple(family)
        self.male = tuple(male)
        self.female = tuple(female)
        self.city = tuple(city)
        self.street = tuple(street)

    @classmethod
    def from_sublists(cls, directory: Path | str, country: str = "DE") -> Inventories:
        """Load the CodEAlltag ``*.json`` sublists, which nest ``initial -> [entries]``."""
        import json

        directory = Path(directory)

        def flat(name: str, *, under: str | None = None) -> list[str]:
            data = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
            if under is not None:
                data = data.get(under, {})
            out: list[str] = []
            for value in data.values():
                out.extend(value) if isinstance(value, list) else out.extend(
                    x for sub in value.values() for x in sub
                )
            return out

        return cls(
            family=flat("family"),
            male=flat("male"),
            female=flat("female"),
            city=flat("city", under=country),
            street=flat("street"),
        )


def find_runs(text: str) -> tuple[TagRun, ...]:
    """Every tag run in a released letter.

    A run is a ``B-X`` followed by the ``I-X`` tokens that are adjacent to it — separated by
    whitespace or a hyphen and nothing else.  An ``I-X`` that resumes after prose starts a new run
    instead of swallowing the prose, and so does an ``I-X`` with no ``B-X`` before it.
    """
    hits = [(m.start(), m.end(), m.group()) for m in _TOKEN.finditer(text)]
    runs: list[TagRun] = []
    index = 0
    while index < len(hits):
        start, end, token = hits[index]
        type_ = token[2:] if token[:2] in ("B-", "I-") else token
        follow = index + 1
        while (
            follow < len(hits)
            and hits[follow][2] == "I-" + type_
            and _JOIN.match(text[hits[follow - 1][1] : hits[follow][0]])
        ):
            follow += 1
        stop = hits[follow - 1][1]
        runs.append(
            TagRun(start=start, end=stop, type=type_, tokens=follow - index, text=text[start:stop])
        )
        index = follow
    return tuple(runs)


class _Person:
    """A stipulated identity, rendered short or long according to the run that asks for it."""

    __slots__ = ("entity_id", "given", "second", "family", "female")

    def __init__(self, entity_id: str, given: str, second: str, family: str, female: bool) -> None:
        self.entity_id = entity_id
        self.given = given
        self.second = second
        self.family = family
        self.female = female

    def surface(self, tokens: int) -> str:
        if tokens <= 1:
            return self.family
        if tokens == 2:
            return f"{self.given} {self.family}"
        return f"{self.given} {self.second} {self.family}"


def _house_number(rng: random.Random) -> str:
    number = str(rng.randint(1, 180))
    return number + rng.choice(("", "", "", "a", "b"))


def _fill_surface(
    run: TagRun,
    person: _Person | None,
    inventories: Inventories,
    rng: random.Random,
    year_hint: int,
    gender: str | None = None,
) -> str:
    """The replacement text for one run.  Plausible German, of the right type and rough length."""
    type_ = run.type
    if type_ == "PER":
        assert person is not None
        return person.surface(run.tokens)
    if type_ == "TITLE":
        return rng.choice(_TITLES.get(min(run.tokens, 3), _TITLES[3]))
    if type_ == "SALUTE":
        return "Frau" if (person is not None and person.female) else "Herr"
    if type_ in ("ORG",):
        city = rng.choice(inventories.city)
        forms = _ORG_FORMS[gender or "n"]
        form = rng.choice(forms.get(min(run.tokens, 3), forms[3]))
        return form.format(city=city)
    if type_ == "LOC":
        return rng.choice(inventories.city)
    if type_ == "ADDR":
        street = rng.choice(inventories.street)
        return street if run.tokens <= 1 else f"{street} {_house_number(rng)}"
    if type_ == "PLZ":
        return f"{rng.randint(1067, 99998):05d}"
    if type_ == "PHONE":
        return f"{rng.choice(_AREA_CODES)} {rng.randint(100000, 999999)}"
    if type_ == "DATE":
        # German form, and a year drawn from *this letter's* shifted timeline (see fill_document).
        # A global 2004-2020 range put 2014 lab dates in a 2032 admission — separable at a glance
        # and clinically absurd.
        return f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{year_hint}"
    if type_ == "DAY":
        return f"{rng.randint(1, 28):02d}."
    if type_ == "MONTH":
        return rng.choice(_MONTHS)
    if type_ == "YEAR":
        return str(year_hint)
    # OTHER, OTHERG, OTH, II — parenthesised codes, preceded by "-LRB-" in 809 of 1,066 cases.
    return f"{rng.choice('ABCDEFGHKLMNPRSTUVWZ')}{rng.randint(10000, 999999)}"


def _person_for(
    run: TagRun,
    text: str,
    doc_id: str,
    patient: _Person,
    counter: list[int],
    inventories: Inventories,
    rng: random.Random,
) -> tuple[_Person, str]:
    """Which identity a ``PER`` run belongs to, by the stipulated rule."""
    context = text[max(0, run.start - 90) : run.start]
    if _PATIENT_CUE.search(context):
        return patient, "patient"
    lowered = context.lower()
    role = (
        "signature"
        if "grüßen" in lowered or "gruessen" in lowered
        else "referring"
        if any(cue in lowered for cue in ("niedergelassen", "betreuend", "hausarzt", "kolleg"))
        else "unattributed"
    )
    counter[0] += 1
    return _new_person(f"{doc_id}:p{counter[0]}", inventories, rng), role


def _new_person(entity_id: str, inventories: Inventories, rng: random.Random, female: bool | None = None) -> _Person:
    if female is None:
        female = rng.random() < 0.5
    pool = inventories.female if female else inventories.male
    return _Person(
        entity_id=entity_id,
        given=rng.choice(pool),
        second=rng.choice(pool),
        family=rng.choice(inventories.family),
        female=female,
    )


def _offset_translator(
    replacements: Sequence[tuple[int, int, str]]
) -> Callable[[int], int]:
    """Map an offset in the released text to the same point in the filled text.

    An offset that falls **inside** a replaced run has no exact image; it is clamped to the start of
    the replacement, which is the only choice that keeps a span containing the run from inverting.
    """
    if not replacements:
        return lambda offset: offset

    starts: list[int] = []
    table: list[tuple[int, int, int]] = []   # old_end, new_start, replacement length
    delta = 0
    for old_start, old_end, surface in replacements:
        starts.append(old_start)
        table.append((old_end, old_start + delta, len(surface)))
        delta += len(surface) - (old_end - old_start)

    def translate(offset: int) -> int:
        index = bisect.bisect_right(starts, offset) - 1
        if index < 0:
            return offset
        old_end, new_start, length = table[index]
        if offset < old_end:
            return new_start
        return new_start + length + (offset - old_end)

    return translate


def _remap_layers(task: Mapping[str, object], translate: Callable[[int], int], text: str) -> tuple[dict, int]:
    """Carry the medication, section and relation layers onto the filled text."""
    out = dict(task)
    moved = 0

    def move(span):
        nonlocal moved
        moved += 1
        start, end = translate(span.start), translate(span.end)
        if isinstance(span, MedicationSpan):
            return _replace(span, start=start, end=end, text=text[start:end])
        return _replace(span, start=start, end=end)

    for key in ("medications", "sections", "relations"):
        value = out.get(key)
        if isinstance(value, (list, tuple)) and value:
            out[key] = tuple(move(span) for span in value)
    annotations = out.get("cas")
    if isinstance(annotations, CasAnnotations):
        out["cas"] = CasAnnotations(
            text=text,
            medications=tuple(move(s) for s in annotations.medications),
            sections=tuple(move(s) for s in annotations.sections),
            relations=tuple(move(s) for s in annotations.relations),
        )
    return out, moved


def fill_document(
    document: Document,
    inventories: Inventories,
    seed: int = 0,
) -> tuple[Document, tuple[FilledEntity, ...]]:
    """Return the condition-A letter and the run → entity map that is its gold.

    Two passes.  The first assigns an identity to every ``PER`` run, because a ``B-SALUTE`` has to
    agree with the person it introduces and that person is only decided by the run *after* it.  The
    second renders each run and splices the text.

    The seed is derived from the document id as well, so one letter's fill does not depend on how
    many letters were processed before it and a single letter can be rebuilt on its own.
    """
    rng = random.Random(f"{seed}:{document.doc_id}")
    text = document.text
    runs = find_runs(text)
    markers = tuple(_PSEUDO.finditer(text))
    nones = tuple(_NONE_MARKER.finditer(text))
    brackets = tuple(_PTB.finditer(text))
    unknowns = tuple(_UNK.finditer(text))
    # Every markup form counts towards "is there anything to do here". Listing them once, rather than
    # adding a clause per form, is why: the first version checked only tag runs, so a letter carrying
    # only <NONE> shipped the markup, and the version after it missed bracket-only letters the same
    # way. Anything added to the substitutions below must be added here too.
    if not (runs or markers or nones or brackets or unknowns):
        return document, ()

    # --- pass 1: who is who ---------------------------------------------------------------------
    female = bool(_FEMALE_CUE.search(text))
    patient = _new_person(f"{document.doc_id}:patient", inventories, rng, female=female)
    # Everything after the closing salutation is the signature block: those are physicians, and each
    # is a different one.  Before it, the letter is about the patient.
    lowered_text = text.lower()
    signature_at = max(lowered_text.rfind("grüßen"), lowered_text.rfind("gruessen"))
    if signature_at < 0:
        signature_at = len(text)
    people: dict[int, _Person] = {}
    roles: dict[int, str] = {}
    made = 0
    for index, run in enumerate(runs):
        if run.type != "PER":
            continue
        context = text[max(0, run.start - 90) : run.start]
        if _PATIENT_CUE.search(context):
            people[index], roles[index] = patient, "patient"
            continue
        lowered = context.lower()
        if "grüßen" in lowered or "gruessen" in lowered or run.start > signature_at:
            roles[index] = "signature"
        elif any(cue in lowered for cue in ("niedergelassen", "betreuend", "hausarzt", "kolleg")):
            roles[index] = "referring"
        else:
            # **An uncued mention in the body is the patient.**  The alternative — a fresh person per
            # run — produced letters in which one man was Marcel Bremert, then Frau Walers, then Herr
            # Schwamberger, then Herr Ganslmaier, then Herr Opden-oordt, then Herr Örtl, across six
            # sentences about the same admission.  A discharge letter's body refers overwhelmingly to
            # its patient; naming each mention differently is not a conservative over-count but an
            # incoherent document, and a co-reference model reads six people where there is one.
            roles[index] = "patient_body"
            people[index] = patient
            continue
        made += 1
        people[index] = _new_person(f"{document.doc_id}:p{made}", inventories, rng)

    # A salutation belongs to the next person named after it.
    next_person: dict[int, _Person] = {}
    upcoming: _Person | None = None
    for index in range(len(runs) - 1, -1, -1):
        if runs[index].type == "PER":
            upcoming = people.get(index)
        next_person[index] = upcoming

    # --- pass 2: render and splice --------------------------------------------------------------
    # The letter's own timeline: Heidelberg shifted every date by a constant per-document offset
    # (§12.1), so an inserted date has to land inside the same shifted window or it is separable by
    # year alone — and reads as a 2014 lab result under a 2032 admission.
    letter_years: list[int] = []
    for marker in markers:
        found = re.search(r"(19|20)\d{2}", marker.group(1))
        if found:
            letter_years.append(int(found.group(0)))
        else:
            short = re.search(r"/(\d{2})\Z", marker.group(1).strip())
            if short:
                letter_years.append(2000 + int(short.group(1)))
    if letter_years:
        low, high = min(letter_years), max(letter_years)
        year_hint = rng.randint(low, high)
    else:
        year_hint = rng.randint(2004, 2020)
    filled: list[FilledEntity] = []
    replacements: list[tuple[int, int, str]] = []
    for index, run in enumerate(runs):
        person = people.get(index) if run.type == "PER" else next_person.get(index)
        # The determiner before an ORG slot stays in the text, so the head noun has to agree with it.
        needed = ("f" if run.type == "ORG"
                  and _FEMININE_ARTICLE.search(text[max(0, run.start - 24):run.start]) else None)
        surface = _fill_surface(run, person, inventories, rng, year_hint, gender=needed)
        replacements.append((run.start, run.end, surface))
        entity_id = (
            people[index].entity_id
            if run.type == "PER"
            else f"{document.doc_id}:{run.type}:{index}"
        )
        filled.append(
            FilledEntity(
                start=0, end=0, type=run.type, surface=surface,
                entity_id=entity_id, role=roles.get(index, run.type.lower()), run=run,
            )
        )

    # The date markers are spliced in the same pass, so one offset table covers both.
    dates = [(m.start(), m.end(), _german_date(m.group(1))) for m in markers]
    # <NONE> marks a value the de-identifier removed and could not type. Blank it: condition A must
    # be text rather than markup, and inventing a lab value would be fabricated clinical data.
    blanks = [(m.start(), m.end(), " ") for m in nones]
    unescaped = [(m.start(), m.end(), _PTB_BRACKETS[m.group(1)]) for m in brackets]
    flattened = [(m.start(), m.end(), "-") for m in unknowns]
    # **`is_date` is built from the markers alone, before the other substitutions are added.**
    # It decides what becomes a DATETIME *gold mention*, and the other three lists are not
    # identifiers at all: they are a PTB bracket restored to "(", a `-UNK-` flattened to "-", and a
    # `<NONE>` blanked to " ". Rebinding `dates` to the concatenation first — which is what this did
    # until 2026-09-15 — made every one of them gold, and 23,818 of the corpus's 55,154 gold
    # mentions were single characters: 9,477 "(", 9,569 ")", 4,619 "-" and 153 spaces, 43.2 % of the
    # layer, all typed DATETIME. Detection scored against that gold would be measuring a detector's
    # willingness to tag punctuation.
    is_date = {(start, end) for start, end, _ in dates}
    # A third bucket, and the reason the partition below needs one. These three are pure text
    # repairs: a PTB bracket restored to "(", a `-UNK-` flattened to "-", a `<NONE>` blanked. They
    # are neither identifiers nor tag runs, so they must splice into the text and produce no mention
    # at all. Folding them into `dates` made every one of them DATETIME gold; folding them into the
    # tag runs instead misaligns `filled` and the build's own offset check catches it.
    cosmetic = {(start, end) for start, end, _ in blanks + unescaped + flattened}
    replacements = sorted(replacements + dates + blanks + unescaped + flattened)

    pieces: list[str] = []
    cursor = 0
    positions: list[tuple[int, int]] = []
    written = 0
    for start, end, surface in replacements:
        pieces.append(text[cursor:start])
        written += start - cursor
        positions.append((written, written + len(surface)))
        pieces.append(surface)
        written += len(surface)
        cursor = end
    pieces.append(text[cursor:])
    new_text = "".join(pieces)

    # Positions came back for every replacement; keep the tag-run ones with their entities and
    # turn the marker ones into the DATETIME gold that replaces the corpus's own.
    date_spans: list[tuple[int, int, str]] = []
    tag_positions: list[tuple[int, int]] = []
    for (start, end, surface), (new_start, new_end) in zip(replacements, positions):
        if (start, end) in is_date:
            date_spans.append((new_start, new_end, surface))
        elif (start, end) in cosmetic:
            continue                      # spliced into the text, carries no annotation
        else:
            tag_positions.append((new_start, new_end))
    filled = [
        _replace(entity, start=start, end=end)
        for entity, (start, end) in zip(filled, tag_positions)
    ]

    translate = _offset_translator(replacements)
    task, moved = _remap_layers(document.task, translate, new_text)

    mentions = tuple(
        Mention(
            doc_id=document.doc_id,
            mention_id=f"{document.doc_id}:fill:{index}",
            span=Span(
                entity.start, entity.end, entity.surface,
                type=_TAXONOMY.get(entity.type, "MISC"), type_src=entity.type,
            ),
            gold_entity_id=entity.entity_id,
            attributes={"role": entity.role, "language": "de"},
        )
        for index, entity in enumerate(filled)
    )
    # The <[Pseudo] …> layer was gold over the *marker*; after unwrapping it is gold over the date.
    # Mentions that were not markers — none in the release today — are carried by the offset table.
    carried = tuple(
        Mention(
            doc_id=document.doc_id,
            mention_id=f"d{index}",
            span=Span(start, end, surface, type="DATETIME", type_src="Pseudo"),
            attributes={"language": "de"},
        )
        for index, (start, end, surface) in enumerate(date_spans)
    ) + tuple(
        _replace(
            mention,
            span=_replace(
                mention.span,
                start=translate(mention.span.start),
                end=translate(mention.span.end),
                text=new_text[translate(mention.span.start) : translate(mention.span.end)],
            ),
        )
        for mention in document.mentions
        if mention.span.type_src != "Pseudo"
    )
    filled_document = _replace(
        document,
        text=new_text,
        mentions=tuple(sorted(carried + mentions, key=lambda m: (m.span.start, m.span.end))),
        provenance="inserted",
        task=task,
    )
    return filled_document, tuple(filled)


_TAXONOMY: Mapping[str, str] = {
    "PER": "PERSON",
    "TITLE": "DEMOGRAPHIC",
    "SALUTE": "DEMOGRAPHIC",
    "ORG": "ORG",
    "LOC": "LOC",
    "ADDR": "LOC",
    "PLZ": "LOC",
    "PHONE": "CODE",
    "DATE": "DATETIME",
    "DAY": "DATETIME",
    "MONTH": "DATETIME",
    "YEAR": "DATETIME",
    "OTHER": "CODE",
    "OTHERG": "CODE",
    "OTH": "CODE",
    "II": "CODE",
}
"""Tag type onto the harmonised taxonomy of ``experiment_plan.md`` §10."""


def fill_corpus(
    documents: Iterable[Document],
    inventories: Inventories,
    seed: int = 0,
) -> tuple[list[Document], list[FilledEntity], FillReport]:
    """Fill a whole corpus, returning the letters, the map and what was done."""
    out_documents: list[Document] = []
    out_map: list[FilledEntity] = []
    by_type: dict[str, int] = {}
    entities: set[str] = set()
    orphans = 0
    moved = 0
    for document in documents:
        for run in find_runs(document.text):
            if run.text.startswith("I-"):
                orphans += 1
        filled, mapping = fill_document(document, inventories, seed=seed)
        out_documents.append(filled)
        out_map.extend(mapping)
        for entity in mapping:
            by_type[entity.type] = by_type.get(entity.type, 0) + 1
            entities.add(entity.entity_id)
        moved += sum(
            len(v) for k, v in filled.task.items()
            if k in ("medications", "sections", "relations") and isinstance(v, (list, tuple))
        )
    report = FillReport(
        documents=len(out_documents),
        runs=len(out_map),
        entities=len(entities),
        by_type=by_type,
        orphan_runs=orphans,
        layers_remapped=moved,
    )
    return out_documents, out_map, report
