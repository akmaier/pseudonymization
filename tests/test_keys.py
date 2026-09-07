import pytest

from pseudonymkit.keys import NORMALISERS, entity_key


def test_all_levels_registered():
    assert NORMALISERS.names() == ["N0", "N1", "N2", "N3", "N4"]


@pytest.mark.parametrize(
    "level,surface,expected",
    [
        ("N0", "Dr. Weber", "Dr. Weber"),
        ("N1", "  Dr.   WEBER ", "dr. weber"),
        ("N2", "Dr. Weber", "weber"),
        ("N2", "Prof. F. Weber", "f weber"),
        ("N3", "Prof. F. Weber", "weber"),
        ("N4", "Angela Dorothea Merkel", "merkel"),
    ],
)
def test_normalisation(level, surface, expected):
    assert NORMALISERS.create(level)(surface, "PERSON") == expected


def test_normalisers_are_monotone_in_aggressiveness():
    """Each level unifies at least as much as the previous one."""
    forms = ["Dr. Weber", "Weber", "F. Weber", "weber"]
    sizes = [len({NORMALISERS.create(n)(f, "PERSON") for f in forms}) for n in NORMALISERS.names()]
    assert sizes == sorted(sizes, reverse=True)


def test_entity_type_is_part_of_the_key():
    n = NORMALISERS.create("N2")
    assert entity_key("Berlin", "PERSON", n) != entity_key("Berlin", "LOC", n)


def test_unknown_level_names_the_alternatives():
    with pytest.raises(KeyError, match="N0"):
        NORMALISERS.create("N9")
