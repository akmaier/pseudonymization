"""Gazetteer loaders, against inline fixtures rather than the real tables."""

import pytest

from pseudonymkit import gazetteers
from pseudonymkit.inventories import Entry

CENSUS = (
    "name,rank,count,prop100k,cum_prop100k,pctwhite\n"
    "SMITH,1,2442977,828.19,828.19,70.9\n"
    "JOHNSON,2,1932812,655.24,1483.42,58.97\n"
    "ALL OTHER NAMES,0,29312001,9935.53,100000,66.65\n"
)
GENDER = (
    "Name,Gender,Count,Probability\n"
    "James,M,5304407,0.0145\n"
    "Mary,F,3215520,0.0088\n"
    "Unknown,U,10,0.0\n"
)
CITIES = (
    "3040051\tles Escaldes\tles Escaldes\talt\t42.5\t1.5\tP\tPPLA\tAD\t\t08\t\t\t\t15853\t\t1033\tEurope/Andorra\t2026-04-13\n"
    "2950159\tBerlin\tBerlin\talt\t52.5\t13.4\tP\tPPLC\tDE\t\t16\t\t\t\t3426354\t\t74\tEurope/Berlin\t2026-01-01\n"
)


@pytest.fixture
def files(tmp_path):
    (tmp_path / "census.csv").write_text(CENSUS, encoding="utf-8")
    (tmp_path / "gender.csv").write_text(GENDER, encoding="utf-8")
    (tmp_path / "cities.txt").write_text(CITIES, encoding="utf-8")
    return tmp_path


def test_census_surnames_carry_real_counts(files):
    entries = gazetteers.load_census_surnames(files / "census.csv")
    assert [e.surface for e in entries] == ["Smith", "Johnson"]
    assert entries[0].frequency == 2442977.0


def test_census_summary_row_is_dropped(files):
    """'ALL OTHER NAMES' is an aggregate, not a name; treating it as one would poison A1."""
    assert all("OTHER" not in e.surface.upper()
               for e in gazetteers.load_census_surnames(files / "census.csv"))


def test_given_names_carry_gender(files):
    entries = gazetteers.load_given_names(files / "gender.csv")
    assert {e.surface: e.attributes["gender"] for e in entries} == {"James": "M", "Mary": "F"}


def test_unknown_gender_rows_are_skipped(files):
    assert "Unknown" not in {e.surface for e in gazetteers.load_given_names(files / "gender.csv")}


def test_cities_carry_population_and_country(files):
    entries = gazetteers.load_geonames_cities(files / "cities.txt")
    berlin = next(e for e in entries if e.surface == "Berlin")
    assert berlin.frequency == 3426354.0 and berlin.attributes["country"] == "DE"


def test_city_filters(files):
    assert len(gazetteers.load_geonames_cities(files / "cities.txt", min_population=1_000_000)) == 1
    assert len(gazetteers.load_geonames_cities(files / "cities.txt", countries=["AD"])) == 1


def test_build_inventory_covers_both_types(files):
    inv = gazetteers.build_inventory(
        surnames=gazetteers.load_census_surnames(files / "census.csv"),
        given_names=gazetteers.load_given_names(files / "gender.csv"),
        cities=gazetteers.load_geonames_cities(files / "cities.txt"),
    )
    assert inv.size("PERSON", "en") == 4 and inv.size("LOC", "en") == 2


def test_gender_stratification_selects_within_the_stratum(files):
    inv = gazetteers.build_inventory(given_names=gazetteers.load_given_names(files / "gender.csv"))
    assert inv.size("PERSON", "en", {"gender": "F"}) == 1
    assert inv.surface(0, "PERSON", "en", {"gender": "F"}) == "Mary"


def test_frequency_matching_prefers_common_names(files):
    """The whole point of carrying counts: a frequency-matched draw should land on common names."""
    inv = gazetteers.build_inventory(
        surnames=gazetteers.load_census_surnames(files / "census.csv"), frequency_matched=True
    )
    drawn = [inv.surface(i * (1 << 28), "PERSON", "en") for i in range(16)]
    assert drawn.count("Smith") > drawn.count("Johnson")


def test_sources_record_provenance_and_licence():
    for key in ("census_surnames", "given_names", "geonames_cities"):
        assert gazetteers.SOURCES[key]["licence"]
        assert gazetteers.SOURCES[key]["url"].startswith("https://")


def test_entries_are_usable_as_a1_candidates(files):
    pairs = list(gazetteers.iter_candidates(gazetteers.load_census_surnames(files / "census.csv")))
    assert pairs[0] == ("Smith", 2442977.0)
