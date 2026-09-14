"""Surrogate inventories for the languages the English gazetteers cannot serve.

``experiment_plan.md`` §7 asks condition B for a *"realistic, locale-appropriate surrogate"*, and §14
fixes three gazetteers — US Census surnames, UCI given names, GeoNames cities — all English.  Three
of the four corpora are not:

* **CARDIO:DE** is German, 400 letters;
* **OntoNotes** is 1,911 Chinese documents and 446 Arabic ones beside its 3,637 English.

:class:`~pseudonymkit.inventories.ListInventory` raises rather than substituting, so B on those
simply fails today — loudly, which is the right failure, but it still fails.  This module supplies
the three missing pools.

## German — Eder et al.'s substitute lists

Already on the cluster and already in use: the CARDIO:DE condition-A fill draws its names from them
(§12).  53,028 surnames, 441 male and 534 female given names, 91,899 place names across DE/AT/CH,
51,583 streets.  Using the same inventory for the fill and for condition B is deliberate — it means a
German surrogate in B is drawn from the same population as the identifier it replaces, which is what
"locale-appropriate" has to mean when the identifiers are themselves ours.

The lists carry **no frequencies**: Eder et al. drew frequency-independent by construction, and
LREC 2022 footnote 5 records that the published lists are deliberately *not* the ones that produced
their corpus.  So a German draw is uniform, and that is stated rather than hidden — H4's
frequency-preservation question is not answerable in German with these.

## Chinese — ChineseNames

1,806 surnames with absolute bearer counts over 1,181,719,774 people, and given-name characters by
sex and birth cohort, from a 2008 National Citizen Identity Information Center extract.  Top-10
surnames cover 43.54 % of the population and the top 100 cover 86.37 %, so this is the one pool in
the study with a *true* population frequency distribution.

**Licence: GPL-3 + CC BY-NC-SA.**  ShareAlike and non-commercial, so the recipe **fetches** it and
never vendors it — :func:`fetch_chinese_names` downloads to a local path that is not in the repo.

## Arabic — recombined from the corpus's own attested parts

No population-weighted Arabic-script name frequency is publicly available (checked 2026-09-11), and
the alternative is worse than absent: OntoNotes Arabic is **82.6 % diacritised**, and its PERSON
spans are 83.4 % marked at span level, 68.6 % at token level.  A surrogate drawn from an unmarked
list would be findable by a one-feature classifier, which would confound detection, stability and
A2/A4 at once — the pseudonymiser's own tooling becoming the strongest signal in the data.

So the Arabic pool is built from the corpus's **own** name parts, with their diacritics as annotated:
1,366 distinct first parts and 1,924 distinct last parts over 6,263 PERSON spans, recombined into
pairs that are *not* attested as real names.  Nothing is generated, so nothing is guessed: every
surrogate is marked in the corpus's own convention, at the corpus's own rate — including the 31 % of
name tokens that carry no diacritic at all.

That the marking is stable enough to reuse is itself measured: of the 1,508 name word forms
occurring more than once, **1,437 (95.3 %) are written identically every time**, and the 71 that vary
are one dominant spelling plus a stray (عَبْد 139 against عَبَّدَ 1).

The cost is stated: the parts are corpus-internal, so the pool carries no population weighting — the
same limitation §12.1 already records for OntoNotes English, whose names are a newswire-celebrity
distribution rather than a population one.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .inventories import Entry, ListInventory

__all__ = [
    "SOURCES_INTL",
    "load_codealltag_sublists",
    "load_chinese_names",
    "fetch_chinese_names",
    "arabic_parts_from_documents",
    "build_arabic_pool",
    "build_german_inventory",
    "build_chinese_inventory",
    "build_arabic_inventory",
    "attested_pool",
    "build_attested_inventory",
    "merge_inventories",
]

SOURCES_INTL: dict[str, dict[str, str]] = {
    "codealltag_sublists": {
        "url": "https://github.com/ee-2/SurrogateGeneration",
        "licence": "MIT (code); the lists themselves carry upstream terms — given names LGPL "
                   "(J. Michael), org/street ODbL (OpenStreetMap), city CC-BY (GeoNames), "
                   "family from the Deutscher Familienatlas with no licence named",
        "note": "no frequencies: drawn frequency-independent by construction (Eder et al.)",
    },
    "chinese_names": {
        "url": "https://raw.githubusercontent.com/psychbruce/ChineseNames/master/data-csv/",
        "files": "familyname.csv, givenname.csv",
        "licence": "GPL-3 + CC BY-NC-SA — fetch, never vendor",
        "note": "1,806 surnames with counts over 1,181,719,774 people; 2008 NCIIC extract",
    },
    "arabic_recombined": {
        "url": "derived from OntoNotes Arabic PERSON spans in the study's own condition A",
        "licence": "derived work; not redistributable beyond the OntoNotes licence",
        "note": "diacritics as annotated; no generation",
    },
}
"""Provenance for the manifest. A gazetteer without its source is not reproducible (§9)."""

_ARABIC_DIACRITICS = frozenset(
    chr(c) for c in list(range(0x064B, 0x0660)) + [0x0670] + list(range(0x06D6, 0x06EE))
)


# --------------------------------------------------------------------------------------- German


def load_codealltag_sublists(directory: Path | str) -> dict[str, list[Entry]]:
    """Eder et al.'s German substitute lists, as ``{"surnames": …, "given_names": …, "cities": …}``.

    The files nest ``initial -> [names]``, except ``city.json`` which nests
    ``country -> initial -> [names]``.  Given names carry sex, which an attribute-matched surrogate
    can stratify on; nothing carries a frequency.
    """
    directory = Path(directory)

    def flat(name: str, under: str | None = None) -> list[str]:
        data = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
        if under is not None:
            data = data.get(under, {})
        out: list[str] = []
        for value in data.values():
            if isinstance(value, list):
                out.extend(value)
            elif isinstance(value, dict):
                out.extend(x for sub in value.values() for x in sub)
        return out

    given: list[Entry] = []
    for file, sex in (("male", "M"), ("female", "F")):
        given.extend(Entry(n, attributes={"gender": sex, "locale": "de"}) for n in flat(file))
    return {
        "surnames": [Entry(n, attributes={"locale": "de"}) for n in flat("family")],
        "given_names": given,
        "cities": [Entry(n, attributes={"locale": "de"}) for n in flat("city", under="DE")],
        "streets": [Entry(n, attributes={"locale": "de"}) for n in flat("street")],
        "orgs": [Entry(n, attributes={"locale": "de"}) for n in flat("org")],
    }


def build_german_inventory(directory: Path | str) -> ListInventory:
    """A German pool keyed ``("PERSON"|"LOC"|"ORG", "de")``."""
    tables = load_codealltag_sublists(directory)
    return ListInventory({
        ("PERSON", "de"): tuple(tables["given_names"]) + tuple(tables["surnames"]),
        ("LOC", "de"): tuple(tables["cities"]) + tuple(tables["streets"]),
        ("ORG", "de"): tuple(tables["orgs"]),
    })


# -------------------------------------------------------------------------------------- Chinese


def fetch_chinese_names(destination: Path | str) -> dict[str, Path]:
    """Download ChineseNames' two CSVs. **Fetched, never vendored** — CC BY-NC-SA (see the module
    docstring). Returns the paths written."""
    import urllib.request

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    base = SOURCES_INTL["chinese_names"]["url"]
    out: dict[str, Path] = {}
    for name in ("familyname.csv", "givenname.csv"):
        path = destination / name
        if not path.exists():
            with urllib.request.urlopen(base + name, timeout=120) as response:
                path.write_bytes(response.read())
        out[name] = path
    return out


def load_chinese_names(directory: Path | str) -> dict[str, list[Entry]]:
    """ChineseNames: surnames with bearer counts, given-name characters with counts by sex."""
    import csv

    directory = Path(directory)

    def read(name: str) -> list[dict[str, str]]:
        # utf-8-sig: both files ship with a BOM, which otherwise lands inside the first column name
        # and makes every lookup on it miss silently.
        with (directory / name).open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    surnames: list[Entry] = []
    for row in read("familyname.csv"):
        surname = (row.get("surname") or row.get("name") or "").strip()
        # ``n.1930_2008`` is the released column: bearers over the 1930-2008 window.
        count = _number(
            row.get("n.1930_2008") or row.get("n") or row.get("count") or row.get("ppl")
        )
        if surname:
            surnames.append(
                Entry(surname, frequency=count or 1.0, attributes={"locale": "zh"})
            )

    given: list[Entry] = []
    for row in read("givenname.csv"):
        character = (row.get("character") or row.get("name") or "").strip()
        if not character:
            continue
        male = _number(row.get("n.male") or row.get("male")) or 0.0
        female = _number(row.get("n.female") or row.get("female")) or 0.0
        if male:
            given.append(Entry(character, frequency=male, attributes={"gender": "M", "locale": "zh"}))
        if female:
            given.append(Entry(character, frequency=female, attributes={"gender": "F", "locale": "zh"}))
        if not male and not female:
            given.append(Entry(character, frequency=1.0, attributes={"locale": "zh"}))
    return {"surnames": surnames, "given_names": given}


def _number(value: object) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def build_chinese_inventory(directory: Path | str, max_names: int = 40_000) -> ListInventory:
    """Surnames × given-name characters, weighted by the product of their frequencies.

    The **joint** surname × given-name distribution is unpublished, so sampling the marginals
    independently gets the marginals right and the joint wrong. That is a stated limitation, not a
    hidden one.
    """
    tables = load_chinese_names(directory)
    surnames = sorted(tables["surnames"], key=lambda e: -e.frequency)[:400]
    given = sorted(tables["given_names"], key=lambda e: -e.frequency)[:200]
    people: list[Entry] = []
    for surname in surnames:
        for first in given:
            people.append(
                Entry(
                    surname.surface + first.surface,
                    frequency=surname.frequency * first.frequency,
                    attributes={k: v for k, v in first.attributes.items() if k == "gender"}
                    | {"locale": "zh"},
                )
            )
            if len(people) >= max_names:
                break
        if len(people) >= max_names:
            break
    return ListInventory({("PERSON", "zh"): tuple(people)})


# --------------------------------------------------------------------------------------- Arabic


def _has_diacritic(text: str) -> bool:
    return any(c in _ARABIC_DIACRITICS for c in text)


_ARABIC_LETTER = re.compile(r"[\u0620-\u064A\u0671-\u06D3]")
_NOT_ARABIC = re.compile(r"[^\u0620-\u065F\u0670-\u06D3\u06D6-\u06ED]")


def _clean_part(token: str) -> str | None:
    """One name part, or ``None`` if it is not one.

    OntoNotes is Penn-Treebank tokenised and its ENAMEX spans keep the punctuation that sits inside
    them, so a naive whitespace split yields parts like ``"``, ``,`` and ``-أَنْطُوان``.  Splicing those
    into a surrogate would put a stray quote in the middle of a German-style name — visible to any
    reader and to any classifier, which is the precise failure this pool exists to avoid.

    A part is kept only if, after stripping surrounding punctuation, it is **entirely Arabic script**
    — letters plus the diacritics that must survive — and at least two characters long.
    """
    token = token.strip().strip("\"'\u00ab\u00bb\u2018\u2019\u201c\u201d.,:;!?()[]{}-\u2013\u2014_/\\|")
    if len(token) < 2 or not _ARABIC_LETTER.search(token) or _NOT_ARABIC.search(token):
        return None
    return token


def arabic_parts_from_documents(
    documents: Iterable, entity_type: str = "PERSON"
) -> tuple[list[str], list[str], dict]:
    """First and last name parts, with their diacritics, from a corpus's own gold PERSON spans.

    Returns ``(first_parts, last_parts, report)``.  ``report`` carries the counts the module
    docstring quotes, so a run records what its pool was built from.
    """
    attested: set[str] = set()
    first: dict[str, int] = {}
    last: dict[str, int] = {}
    spans = marked = 0
    for document in documents:
        if getattr(document, "language", None) != "ar":
            continue
        for mention in document.mentions:
            if mention.span.type != entity_type:
                continue
            surface = " ".join(mention.span.text.split())
            if not surface:
                continue
            spans += 1
            marked += _has_diacritic(surface)
            attested.add(surface)
            parts = [p for p in (_clean_part(t) for t in surface.split()) if p]
            if len(parts) >= 2:
                first[parts[0]] = first.get(parts[0], 0) + 1
                last[parts[-1]] = last.get(parts[-1], 0) + 1
    # The attested set is compared against cleaned parts, so clean it the same way — otherwise a
    # recombination would never match an attested name carrying punctuation and the exclusion would
    # silently do nothing.
    attested = {
        " ".join(p for p in (_clean_part(t) for t in name.split()) if p) for name in attested
    }
    report = {
        "spans": spans,
        "spans_with_diacritic": marked,
        "distinct_surfaces": len(attested),
        "first_parts": len(first),
        "last_parts": len(last),
        "attested_pairs_excluded": 0,
    }
    return sorted(first), sorted(last), report | {"attested": attested}


def build_arabic_pool(
    first_parts: Sequence[str], last_parts: Sequence[str], attested: set[str],
    limit: int = 40_000,
) -> list[Entry]:
    """Recombine attested parts into names that are **not** attested in the corpus.

    Excluding attested pairs matters: a surrogate that happens to be a real person in the same
    corpus would make a leakage number ambiguous between "recovered the pseudonym" and "recognised
    a different real person".
    """
    out: list[Entry] = []
    for a in first_parts:
        for b in last_parts:
            if a == b:
                continue
            candidate = f"{a} {b}"
            if candidate in attested:
                continue
            out.append(Entry(candidate, attributes={"locale": "ar"}))
            if len(out) >= limit:
                return out
    return out


def build_arabic_inventory(documents: Iterable, limit: int = 40_000) -> tuple[ListInventory, dict]:
    """The Arabic pool, plus the report of what it was built from."""
    first, last, report = arabic_parts_from_documents(documents)
    attested = report.pop("attested")
    pool = build_arabic_pool(first, last, attested, limit=limit)
    if not pool:
        raise ValueError(
            "no Arabic PERSON parts found — build_arabic_inventory needs a corpus carrying gold "
            "PERSON spans on documents whose language is 'ar'"
        )
    report["pool"] = len(pool)
    return ListInventory({("PERSON", "ar"): tuple(pool)}), report


# ------------------------------------------------------------------------------ attested pools


def attested_pool(
    documents: Iterable, entity_type: str, language: str, min_count: int = 2, limit: int = 20_000
) -> tuple[list[Entry], dict]:
    """Candidate surrogates for one ``(entity_type, language)``, taken from the corpus's own values.

    §14's gazetteers cover English person names and cities, German names/streets/cities/orgs, and
    Chinese person names.  They do not cover English organisations, Chinese or Arabic places and
    organisations, or ``DEMOGRAPHIC`` in any language — nine pools in all, 129,000 mentions.  For
    some of those no external list plausibly exists: TAB's ``DEMOGRAPHIC`` spans native language,
    descent, ethnicity, job titles, ranks, education, physical descriptions, diagnosis and ages, a
    category with no gazetteer and a vocabulary that differs per corpus.

    Compiling the pool from values the corpus itself attests guarantees a surrogate that is a real
    term of the right kind, register and language — which is the "realistic" requirement, and which
    is what this repository already does for Arabic person names.  It is also what the clinical
    corpora do: i2b2 drew professions from "a pre-compiled list of surrogates" and replaced hospital
    departments with other real department names.

    **Values attested once are excluded from the pool.**  Carrell et al. observe that an attribute
    identifies when it is "extremely rare" — their examples are a "retired chair of OB/GYN department
    at university" and a "pitcher for the Red Sox".  A singleton is exactly that, and admitting it
    would let the pipeline *insert* a rare identifying value into a document that never had one.
    Rare values are still replaced; they are merely not used as replacements.  ``min_count=1``
    disables the filter.

    Frequency is carried through, so a frequency-matched inventory keeps common values common.
    Nothing is ever invented: a type/language the corpus does not attest yields an empty pool.
    """
    counts: Counter[str] = Counter()
    for document in documents:
        if getattr(document, "language", None) != language:
            continue
        for mention in getattr(document, "mentions", ()):
            if mention.type != entity_type:
                continue
            surface = " ".join(mention.span.text.split()).strip()
            if surface:
                counts[surface] += 1
    kept = [(s, n) for s, n in counts.most_common() if n >= min_count][:limit]
    report = {
        "type": entity_type,
        "language": language,
        "distinct_attested": len(counts),
        "mentions": sum(counts.values()),
        "dropped_below_min_count": sum(1 for _, n in counts.items() if n < min_count),
        "min_count": min_count,
        "pool": len(kept),
    }
    entries = [
        Entry(surface, frequency=float(n), attributes={"locale": language}) for surface, n in kept
    ]
    return entries, report


def build_attested_inventory(
    documents: Sequence,
    pairs: Iterable[tuple[str, str]],
    min_count: int = 2,
    limit: int = 20_000,
) -> tuple[ListInventory, dict]:
    """Compile a pool for each ``(entity_type, language)`` in ``pairs`` from ``documents``.

    ``documents`` is walked once per pair, so pass a sequence rather than a generator.  A pair the
    corpus does not attest is **omitted rather than filled**: the inventory then raises for it,
    loudly, instead of handing an Arabic document English organisations (§1 — an impossible cell is
    reported, not substituted).
    """
    pools: dict[tuple[str, str], tuple[Entry, ...]] = {}
    reports: dict[str, dict] = {}
    for entity_type, language in pairs:
        entries, report = attested_pool(
            documents, entity_type, language, min_count=min_count, limit=limit
        )
        reports[f"{entity_type}/{language}"] = report
        if entries:
            pools[(entity_type, language)] = tuple(entries)
    return ListInventory(pools, frequency_matched=True), reports


# ---------------------------------------------------------------------------------------- merge


def merge_inventories(*inventories: ListInventory) -> ListInventory:
    """One inventory covering several languages.

    :class:`ListInventory` is keyed by ``(entity_type, language)``, so merging is a dictionary
    update — and a later inventory overriding an earlier one for the same key would be a silent
    substitution, so that raises instead.
    """
    entries: dict[tuple[str, str], tuple[Entry, ...]] = {}
    for inventory in inventories:
        for key, value in inventory._entries.items():        # noqa: SLF001 — same package
            if key in entries:
                raise ValueError(f"two inventories both cover {key!r}; refusing to pick one")
            entries[key] = tuple(value)
    return ListInventory(entries)
