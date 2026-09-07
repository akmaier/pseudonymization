"""Loaders for the public name and place inventories.

Axis C levels 2 and 3 and attack A1 all need candidate names **with frequencies**, and H4 needs
**attributes** as well.  None of that can be derived from the corpora, so it comes from public
reference data:

======================================  ==========================  ================  ===========
source                                  gives                       size              licence
======================================  ==========================  ================  ===========
US Census 2010 surname file             surnames + counts           162,254           public domain
UCI "Gender by Name" (ID 591)           given names + sex + counts  147,268           CC-BY 4.0
GeoNames ``cities15000``                cities + population         34,134            CC-BY 4.0
======================================  ==========================  ================  ===========

CC-BY is compatible with the build-recipe distribution model: we ship loaders and a manifest, and
attribute the sources, never redistributing the tables themselves.

Frequencies are the point.  An unweighted name list cannot test H4 (does frequency preservation buy
utility and cost privacy?) and cannot band A1's results by how common a name is — which is where the
interesting finding lives, since a dictionary holds common names and misses rare ones.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator, Sequence

from .inventories import Entry, ListInventory

__all__ = [
    "load_census_surnames",
    "load_given_names",
    "load_geonames_cities",
    "build_inventory",
    "SOURCES",
]

SOURCES: dict[str, dict[str, str]] = {
    "census_surnames": {
        "url": "https://www2.census.gov/topics/genealogy/2010surnames/names.zip",
        "file": "Names_2010Census.csv",
        "licence": "public domain (US Census Bureau)",
    },
    "given_names": {
        "url": "https://archive.ics.uci.edu/static/public/591/gender+by+name.zip",
        "file": "name_gender_dataset.csv",
        "licence": "CC-BY 4.0 (UCI ML Repository, 'Gender by Name')",
    },
    "geonames_cities": {
        "url": "https://download.geonames.org/export/dump/cities15000.zip",
        "file": "cities15000.txt",
        "licence": "CC-BY 4.0 (GeoNames)",
    },
}
"""Provenance for the manifest. Recording where a gazetteer came from is part of reproducibility."""


def load_census_surnames(path: Path | str, limit: int | None = None) -> list[Entry]:
    """US Census 2010 surname table: ``name,rank,count,prop100k,...``.

    ``ALL OTHER NAMES`` is a summary row rather than a name and is dropped.  Counts are the real
    population frequencies, which is what makes frequency-matched surrogates and A1's banding
    possible.
    """
    entries: list[Entry] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("name") or "").strip()
            if not name or name.upper().startswith("ALL OTHER"):
                continue
            try:
                count = float(row["count"])
            except (KeyError, ValueError):
                continue
            entries.append(
                Entry(name.title(), frequency=max(count, 1.0), attributes={"locale": "en-US"})
            )
            if limit and len(entries) >= limit:
                break
    return entries


def load_given_names(path: Path | str, limit: int | None = None) -> list[Entry]:
    """UCI 'Gender by Name': ``Name,Gender,Count,Probability``.

    The ``gender`` attribute is what attribute-matched surrogates (axis C level 3) stratify on, and
    therefore what H4 is tested with.
    """
    entries: list[Entry] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("Name") or "").strip()
            gender = (row.get("Gender") or "").strip().upper()
            if not name or gender not in {"M", "F"}:
                continue
            try:
                count = float(row["Count"])
            except (KeyError, ValueError):
                continue
            entries.append(
                Entry(name.title(), frequency=max(count, 1.0),
                      attributes={"gender": gender, "locale": "en"})
            )
            if limit and len(entries) >= limit:
                break
    return entries


def load_geonames_cities(
    path: Path | str, min_population: int = 0, countries: Sequence[str] | None = None,
    limit: int | None = None,
) -> list[Entry]:
    """GeoNames ``cities15000``: tab-separated, no header.

    Column 1 is the name, 8 the ISO country code, 14 the population.  Population stands in for
    frequency: a surrogate drawn for a capital should not be a village if the distribution is to be
    preserved.
    """
    keep = {c.upper() for c in countries} if countries else None
    entries: list[Entry] = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for parts in csv.reader(handle, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(parts) < 15:
                continue
            name, country, population = parts[1].strip(), parts[8].strip().upper(), parts[14]
            if not name or (keep and country not in keep):
                continue
            try:
                pop = float(population)
            except ValueError:
                continue
            if pop < min_population:
                continue
            entries.append(
                Entry(name, frequency=max(pop, 1.0), attributes={"country": country})
            )
            if limit and len(entries) >= limit:
                break
    return entries


def build_inventory(
    surnames: Sequence[Entry] = (),
    given_names: Sequence[Entry] = (),
    cities: Sequence[Entry] = (),
    language: str = "en",
    frequency_matched: bool = False,
) -> ListInventory:
    """Assemble the loaded tables into one inventory keyed by ``(entity_type, language)``.

    PERSON receives surnames and given names together: the key a mention produces may be a surname
    (``weber``), a full name (``f weber``) or a given name, and the surrogate pool has to cover all
    three.  Given names carry ``gender``, so an attribute-matched surrogate finds a stratum; surnames
    carry only ``locale``, so a gender-stratified draw for a surname falls back to the whole pool,
    which is the documented behaviour of :class:`~pseudonymkit.inventories.ListInventory`.
    """
    return ListInventory(
        {
            ("PERSON", language): tuple(given_names) + tuple(surnames),
            ("LOC", language): tuple(cities),
        },
        frequency_matched=frequency_matched,
    )


def iter_candidates(entries: Sequence[Entry]) -> Iterator[tuple[str, float]]:
    """Adapt inventory entries into A1 candidate pairs."""
    for entry in entries:
        yield entry.surface, entry.frequency
