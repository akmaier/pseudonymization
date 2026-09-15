#!/usr/bin/env python3
"""Build the German name-frequency table §12.1 requires.

The CodEAlltag lists carry no counts, so the weights come from elsewhere and **which source supplied
them is recorded with the build**.  Two sources, chosen because they were measured against real
German counts rather than assumed:

**Surnames — German *ranks* × a count *vector* for magnitude.**  No source gives counts for 53,028
German surnames.  One gives a reliable rank order: the ``nachnamen.csv`` fixture carried by
``abydos``, whose order correlates with the Deutsche-Telekom-2005 counts the Familienatlas publishes
at **Spearman +0.991** (median rank error 1).  Magnitude comes from the US Census count vector, which
supplies a realistic Zipf shape; the German ranks decide *which* name gets which weight, so *Müller*,
*Schmidt* and *Schneider* land in the right order.  Genealogical databases were measured and rejected
— FOKO's submission counts correlate at only **+0.235**, putting *Schulz* (true rank 8) at rank 122,
because genealogists' interest is not population frequency.

**Given names — Bielefeld's residents' register**, the one German open-data given-name source that is
a *population* register rather than a birth register.  Every other municipal set is newborns, which
would put *Mia* and *Noah* on cardiology letters.  It carries sex, and it is stratified by birth
decade, so a patient cohort can be drawn from the decades a cardiology patient would have been born
in.

Licences differ and are honoured differently.  ``abydos`` is **GPL-3**, so its list is *fetched at
build time and never vendored* — the same treatment this repository already gives ChineseNames.  The
US Census data is public domain and Bielefeld is CC-BY 4.0 (attribution: Einwohnermelderegister der
Stadt Bielefeld), both vendorable.

    python experiments/fetch_name_weights.py --out "$PSEUDONYMKIT_WORK/data/cardiode_name_weights.json"
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import sys
import urllib.request
from pathlib import Path

RANKS = ("https://raw.githubusercontent.com/chrislit/abydos/"
         "27e084b364d0329ab334ac3596f741f459168525/tests/corpora/nachnamen.csv")
"""Pinned to a commit: an unpinned raw URL is a moving target and the weights would not reproduce."""

COUNTS = ("https://raw.githubusercontent.com/fivethirtyeight/data/master/"
          "most-common-name/surnames.csv")

GIVEN = "https://open-data.bielefeld.de/sites/default/files/Vornamen_Jahrzehnt.csv"

PATIENT_DECADES = range(1930, 1970)
"""Birth decades a cardiology patient plausibly falls in.  Narrower than the file, on purpose."""


def log(message: str) -> None:
    print(message, flush=True)


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - pinned, documented
        body = response.read()
    if body.lstrip()[:1] in (b"<", b"{") and "csv" in url:
        raise SystemExit(
            f"{url} returned markup, not CSV ({len(body)} bytes). census.gov in particular answers "
            "HTTP 200 with a 247-byte 'Request Rejected' page, so a status-code check is not enough."
        )
    return body


def surname_weights() -> tuple[dict[str, float], str]:
    ranks = [
        row[0].strip()
        for row in csv.reader(io.StringIO(fetch(RANKS).decode("utf-8-sig", "replace")))
        if row and row[0].strip()
    ]
    log(f"  ranks:  {len(ranks)} German surnames, in order")

    counts: list[float] = []
    reader = csv.DictReader(io.StringIO(fetch(COUNTS).decode("utf-8-sig", "replace")))
    field = next((f for f in (reader.fieldnames or []) if f.lower() == "count"), None)
    if field is None:
        raise SystemExit(f"no count column in {reader.fieldnames}")
    for row in reader:
        try:
            counts.append(float(row[field]))
        except (TypeError, ValueError):
            continue
    log(f"  counts: {len(counts)} magnitudes from the US Census vector")
    if len(counts) < len(ranks):
        raise SystemExit("the count vector is shorter than the rank list")

    floor = counts[min(55_891, len(counts) - 1)]
    return {name: counts[i] / floor for i, name in enumerate(ranks)}, floor


def tail_weights(names: list[str], ranked: dict[str, float], counts_floor: float,
                 seed: int = 0) -> dict[str, float]:
    """Weights for the names the rank list does not cover.

    **Assigned by a seeded shuffle, not alphabetically.**  Walking the tail in list order puts a
    detectable A→Z frequency gradient into the corpus, which is an artefact no population has.
    """
    reader = csv.DictReader(io.StringIO(fetch(COUNTS).decode("utf-8-sig", "replace")))
    field = next(f for f in (reader.fieldnames or []) if f.lower() == "count")
    counts = [float(r[field]) for r in reader if r.get(field, "").strip().replace(".", "").isdigit()]
    tail = [n for n in names if n not in ranked]
    random.Random(seed).shuffle(tail)
    out: dict[str, float] = {}
    for index, name in enumerate(tail):
        position = min(len(ranked) + index, len(counts) - 1)
        out[name] = max(counts[position] / counts_floor, 1.0)
    return out


def given_weights() -> tuple[dict[str, float], dict[str, float]]:
    text = fetch(GIVEN).decode("utf-8-sig", "replace")
    male: dict[str, float] = {}
    female: dict[str, float] = {}
    rows = 0
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        rows += 1
        try:
            decade = int(str(row.get("jahrzehnt", "")).strip('" '))
            count = float(str(row.get("anzahl", "")).strip('" '))
        except (TypeError, ValueError):
            continue
        if decade not in PATIENT_DECADES:
            continue
        name = str(row.get("vornamen", "")).strip('" ')
        sex = str(row.get("geschlecht", "")).strip('" ')
        target = male if sex == "1" else female if sex == "2" else None
        if name and target is not None:
            target[name] = target.get(name, 0.0) + count
    log(f"  given:  {rows} rows, {len(male)} male and {len(female)} female names "
        f"in birth decades {PATIENT_DECADES.start}-{PATIENT_DECADES.stop - 1}")
    return male, female


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sublists", type=Path, default=None,
                    help="CodEAlltag sublists, to weight the tail and report coverage")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    log("fetching:")
    ranked, floor = surname_weights()
    male, female = given_weights()

    family = dict(ranked)
    if args.sublists:
        names = json.loads((args.sublists / "family.json").read_text(encoding="utf-8"))
        flat = sorted({n for bucket in names.values() for n in bucket})
        log(f"  list:   {sum(len(v) for v in names.values())} entries, {len(flat)} distinct")
        family.update(tail_weights(flat, ranked, floor, seed=args.seed))
        covered = sum(1 for n in flat if n in ranked)
        mass = sum(ranked.get(n, 0.0) for n in flat)
        total = sum(family.get(n, 1.0) for n in flat)
        log(f"  surname coverage: {covered}/{len(flat)} ranked ({covered/len(flat):.2%}), "
            f"carrying {mass/total:.1%} of the drawn mass")

    payload = {
        "__source__": (
            "surnames: abydos nachnamen.csv ranks (GPL-3, fetched not vendored) x US Census 2010 "
            "count vector (public domain); given names: Stadt Bielefeld Einwohnermelderegister, "
            f"Vornamen nach Jahrzehnt (CC-BY 4.0), birth decades "
            f"{PATIENT_DECADES.start}-{PATIENT_DECADES.stop - 1}"
        ),
        "__fetched__": {"ranks": RANKS, "counts": COUNTS, "given": GIVEN},
        "family": family,
        "male": male,
        "female": female,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload), encoding="utf-8")
    log(f"wrote {args.out} — family {len(family)}, male {len(male)}, female {len(female)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
