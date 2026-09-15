"""Corpus-level identity for CARDIO:DE (§12.1, AM 2026-09-15).

The fill used to mint a fresh person per uncued run, giving 2,038 entities over 400 letters with
nobody appearing twice. That is not a cardiology department's correspondence, and it removed every
measurement needing cross-document identity: drift, A3, A5, and the (name, DOB) pair.
"""

from __future__ import annotations

import random

import pytest

from pseudonymkit.adapters.cardiode_population import (
    Population,
    PopulationSpec,
    WeightedNames,
)

LETTERS = [f"L{i:03d}" for i in range(400)]


@pytest.fixture
def population() -> Population:
    return Population(
        LETTERS,
        WeightedNames([f"F{i}" for i in range(500)]),
        WeightedNames([f"M{i}" for i in range(50)]),
        WeightedNames([f"W{i}" for i in range(50)]),
        PopulationSpec(),
    )


# ----------------------------------------------------------------------------- patients recur


def test_patients_recur_across_letters(population):
    counts = [len(v) for v in population.letters_of.values()]
    assert sum(c > 1 for c in counts) > 0, "no patient held two letters"
    assert len(population.letters_of) < len(LETTERS), "every letter was a new patient"


def test_a_returning_patient_is_the_same_person_in_every_letter(population):
    for patient_id, letters in population.letters_of.items():
        if len(letters) < 2:
            continue
        people = {population.patient(d).entity_id for d in letters}
        assert people == {patient_id}, patient_id


def test_a_follow_up_comes_later_not_next(population):
    """A follow-up arrives after a gap; adjacent letters about one patient are not how it works."""
    gap = population.spec.follow_up_gap
    order = {d: i for i, d in enumerate(LETTERS)}
    for letters in population.letters_of.values():
        positions = sorted(order[d] for d in letters)
        for a, b in zip(positions, positions[1:]):
            assert b - a >= gap, (a, b)


def test_every_letter_has_exactly_one_patient(population):
    assert set(population.patient_of) == set(LETTERS)


# -------------------------------------------------------------------------- physicians turn over


def test_signatories_come_from_a_bounded_pool(population):
    used = {population.physician(d, s).entity_id for d in LETTERS for s in range(4)}
    assert len(used) <= len(population.roster)
    assert len(used) < len(LETTERS), "a pool means far fewer people than letters"


def test_one_consultant_signs_many_letters(population):
    from collections import Counter

    load = Counter(population.physician(d, 0).entity_id for d in LETTERS)
    assert max(load.values()) > 5


def test_turnover_is_visible_and_one_way(population):
    """Staff arrive and leave; a consultant who has left does not come back."""
    early = {population.physician(d, s).entity_id for d in LETTERS[:20] for s in range(4)}
    late = {population.physician(d, s).entity_id for d in LETTERS[-20:] for s in range(4)}
    assert early - late, "nobody left"
    assert late - early, "nobody arrived"


def test_no_turnover_keeps_the_whole_roster_in_post():
    spec = PopulationSpec(physician_turnover=0.0)
    pop = Population(LETTERS, WeightedNames(["F"]), WeightedNames(["M"]), WeightedNames(["W"]), spec)
    assert len(pop.roster) == spec.physicians
    assert pop.active_physicians(LETTERS[0]) == pop.active_physicians(LETTERS[-1])


# ------------------------------------------------------------------------------- reproducibility


def test_the_construction_is_a_function_of_the_seed(population):
    twin = Population(
        LETTERS,
        WeightedNames([f"F{i}" for i in range(500)]),
        WeightedNames([f"M{i}" for i in range(50)]),
        WeightedNames([f"W{i}" for i in range(50)]),
        PopulationSpec(),
    )
    assert {d: population.patient(d).entity_id for d in LETTERS} == \
           {d: twin.patient(d).entity_id for d in LETTERS}
    assert population.physician(LETTERS[7], 1) == twin.physician(LETTERS[7], 1)


def test_a_different_seed_gives_a_different_population(population):
    other = Population(
        LETTERS,
        WeightedNames([f"F{i}" for i in range(500)]),
        WeightedNames([f"M{i}" for i in range(50)]),
        WeightedNames([f"W{i}" for i in range(50)]),
        PopulationSpec(seed=1),
    )
    mine = {d: population.patient(d).entity_id for d in LETTERS}
    theirs = {d: other.patient(d).entity_id for d in LETTERS}
    assert mine != theirs


def test_the_parameters_are_recorded_not_hidden(population):
    report = population.report()
    assert report["spec"]["physicians"] == 30
    assert "patient_return_rate" in report["spec"]
    assert report["family_names"]["source"] == "uniform"


# ------------------------------------------------------------------------- frequency weighting


def test_an_unweighted_pool_says_so_rather_than_implying_a_weighting():
    pool = WeightedNames(["a", "b", "c"])
    assert pool.source == "uniform" and pool.covered == 0


def test_weights_make_a_common_name_common():
    pool = WeightedNames(["Müller", "Zörgiebel"], {"Müller": 1000.0, "Zörgiebel": 1.0}, "test")
    rng = random.Random(0)
    drawn = [pool.draw(rng) for _ in range(500)]
    assert drawn.count("Müller") > drawn.count("Zörgiebel") * 10


def test_a_name_the_source_never_heard_of_keeps_a_floor_weight():
    """The fill must not fail on a name absent from the frequency table, and a long tail of rare
    names is part of a realistic distribution rather than an error."""
    pool = WeightedNames(["Müller", "Unbekannt"], {"Müller": 100.0}, "partial")
    assert pool.covered == 1
    rng = random.Random(1)
    assert "Unbekannt" in {pool.draw(rng) for _ in range(2000)}


def test_an_empty_pool_is_refused():
    with pytest.raises(ValueError, match="empty"):
        WeightedNames([])
