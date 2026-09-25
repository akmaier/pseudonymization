"""External name-frequency priors — what an adversary can look up, per language.

The realistic half of A2 (:mod:`pseudonymkit.attacks.frequency`) needs a distribution over real
names that does **not** come from the corpus under attack.  These are the public lists that supply
it, and each loader records where its numbers came from, which column it used and what it dropped,
because a prior is an experimental factor here rather than a convenience.

## What each source actually is, including where it is weaker than it looks

``en`` — **US Census 2010 surnames**, 162,253 names covering 90 % of recorded surnames, plus UCI
"Gender by Name" (CC BY 4.0, DOI ``10.24432/C55G7X``) for given names.  The Census file's
``ALL OTHER NAMES`` row holds 29.3 M bearers — roughly a tenth of the mass — and is dropped before
normalising: it is not a name, and leaving it in steals probability from every real one.  Given-name
weights come from ``Count`` and not the file's own ``Probability`` column, which sums to one across
both sexes at once and would misweight a sex-stratified prior.  Public-domain status rests on
17 U.S.C. §105 rather than on any statement the Census Bureau prints; it is recorded that way.

``de`` — the weights built for CARDIO:DE's own fill.  Given names are genuine Bielefeld resident
counts for birth decades 1930–1969, which is what makes the *age* axis of the Bindschaedler sweep
real rather than simulated.  **The surname half is not German counts**: it is the German rank order
from abydos paired with the US Census count vector, so it carries a US Zipf shape on German ranks.
That is a real limitation of the prior and belongs in the paper, not only here.

``zh`` — surname bearer counts, and given-name frequencies **per character** by birth cohort.  A
Chinese given name is composed of one or two characters, and these data do not supply the
composition, so the given-name prior is over characters and is labelled as such.

## Why the three are not interchangeable

Top-ten surname mass is 4.9 % in the US and 43.5 % in China.  The same attack therefore has
radically different headroom by language before any detector or policy enters, which is why
:func:`describe` reports entropy and head mass beside every prior: a lift over chance means
something different when chance itself differs by an order of magnitude.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from ..attacks.frequency import Prior, reference_from_counts
from ..keys import NORMALISERS, Normaliser

__all__ = ["load_census_surnames", "load_uci_given_names", "load_german_weights",
           "load_chinese_surnames", "load_chinese_given_characters",
           "build_prior", "describe", "PRIOR_SOURCES"]

CENSUS_SUMMARY_ROW = "ALL OTHER NAMES"


def _rows(path: Path, delimiter: str = ",") -> Iterable[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle, delimiter=delimiter)


def load_census_surnames(path: Path) -> dict[str, float]:
    """``Names_2010Census.csv`` → ``{surname: bearer count}``, summary row dropped."""
    out: dict[str, float] = {}
    for row in _rows(path):
        name = (row.get("name") or "").strip()
        if not name or name.upper() == CENSUS_SUMMARY_ROW:
            continue
        try:
            count = float(row.get("count") or 0)
        except ValueError:
            continue
        if count > 0:
            out[name.title()] = count
    return out


def load_uci_given_names(path: Path, gender: str | None = None) -> dict[str, float]:
    """``name_gender_dataset.csv`` → ``{given name: count}``, optionally one sex only."""
    out: Counter[str] = Counter()
    for row in _rows(path):
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        if gender and (row.get("Gender") or "").strip().upper() != gender.upper():
            continue
        try:
            count = float(row.get("Count") or 0)
        except ValueError:
            continue
        if count > 0:
            out[name.title()] += count
    return dict(out)


def load_german_weights(path: Path, part: str) -> dict[str, float]:
    """``cardiode_name_weights.json`` → one of ``family`` / ``male`` / ``female``."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {k: float(v) for k, v in (payload.get(part) or {}).items() if float(v) > 0}


def load_chinese_surnames(path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in _rows(path):
        name = (row.get("surname") or "").strip()
        try:
            count = float(row.get("n.1930_2008") or 0)
        except ValueError:
            continue
        if name and count > 0:
            out[name] = count
    return out


def load_chinese_given_characters(path: Path, cohort: str = "n.1960_1969") -> dict[str, float]:
    """One cohort column, never a mixture — two cohorts on one list are not comparable."""
    out: dict[str, float] = {}
    for row in _rows(path):
        name = (row.get("character") or "").strip()
        try:
            count = float(row.get(cohort) or 0)
        except ValueError:
            continue
        if name and count > 0:
            out[name] = count
    return out


@dataclass(frozen=True, slots=True)
class PriorSource:
    """One public list, with everything needed to rebuild it and to cite it."""

    language: str
    part: str
    filename: str
    column: str
    url: str
    licence: str
    vintage: str | None = None


PRIOR_SOURCES: tuple[PriorSource, ...] = (
    PriorSource("en", "family", "Names_2010Census.csv", "count",
                "https://www2.census.gov/topics/genealogy/2010surnames/names.zip",
                "US Government work; public domain under 17 U.S.C. §105 — the Census Bureau "
                "prints no explicit statement", vintage="2010"),
    PriorSource("en", "given", "name_gender_dataset.csv", "Count",
                "https://archive.ics.uci.edu/dataset/591/gender+by+name",
                "CC BY 4.0 (DOI 10.24432/C55G7X)", vintage="1880-2019"),
    PriorSource("de", "family", "cardiode_name_weights.json", "family",
                "abydos nachnamen.csv ranks x US Census 2010 counts",
                "GPL-3 rank list, public-domain count vector; CAVEAT: a US Zipf shape on German "
                "rank order, not German counts", vintage="2010"),
    PriorSource("de", "given", "cardiode_name_weights.json", "male|female",
                "Stadt Bielefeld Einwohnermelderegister, Vornamen nach Jahrzehnt",
                "CC BY 4.0", vintage="1930-1969"),
    PriorSource("zh", "family", "familyname.csv", "n.1930_2008", "chinese_names gazetteer",
                "as distributed with the gazetteer", vintage="1930-2008"),
    PriorSource("zh", "given", "givenname.csv", "n.1960_1969", "chinese_names gazetteer",
                "as distributed; CAVEAT: per character, not per whole given name",
                vintage="1960-1969"),
)


def describe(weights: Mapping[str, float]) -> dict[str, float]:
    """Entropy and head mass — what makes two priors comparable across languages.

    A lift over chance is not the same achievement against a distribution whose top ten names carry
    4.9 % of the mass as against one where they carry 43.5 %.
    """
    total = sum(weights.values())
    if not total:
        return {"entropy_bits": 0.0, "top10_mass": 0.0, "names": 0}
    probabilities = sorted((v / total for v in weights.values()), reverse=True)
    entropy = -sum(p * math.log2(p) for p in probabilities if p > 0)
    return {"entropy_bits": entropy, "top10_mass": sum(probabilities[:10]), "names": len(weights)}


def build_prior(
    weights: Mapping[str, float],
    entity_type: str,
    *,
    label: str,
    provenance: str,
    vintage: str | None = None,
    normaliser: Normaliser | None = None,
) -> Prior:
    """Lift a raw name list into the corpus's key space, merging collisions by summing.

    The Census edit rules already collapsed ``O'HARA`` and ``O HARA`` to one entry, and the study's
    own normaliser collapses more, so two source names can land on one key.  Summing is the only
    correct merge: last-wins would silently discard bearers.
    """
    return Prior.from_names(
        weights.items(), entity_type, normaliser or NORMALISERS.create("N2"),
        label=label, provenance=provenance, vintage=vintage,
    )
