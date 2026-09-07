import pytest

from pseudonymkit.techniques import SPACE, TECHNIQUES


@pytest.mark.parametrize("name", TECHNIQUES.names())
def test_deterministic_within_an_instance(name):
    t = TECHNIQUES.create(name)
    assert t.index(("PERSON\x1fweber",), "PERSON") == t.index(("PERSON\x1fweber",), "PERSON")


@pytest.mark.parametrize("name", TECHNIQUES.names())
def test_index_in_range(name):
    t = TECHNIQUES.create(name)
    assert 0 <= t.index(("PERSON\x1fweber",), "PERSON") < SPACE


@pytest.mark.parametrize("name", ["hash", "hmac", "aes_siv"])
def test_stateless_techniques_reproduce_across_instances(name):
    """hash, hmac and aes_siv need no stored table: a fresh instance agrees with the old one."""
    a, b = TECHNIQUES.create(name), TECHNIQUES.create(name)
    assert a.index(("PERSON\x1fweber",), "PERSON") == b.index(("PERSON\x1fweber",), "PERSON")


def test_keyed_flag_matches_the_threat_model():
    """A1 is only defined against unkeyed techniques; the flag is what the attack dispatches on."""
    assert TECHNIQUES.create("hash").keyed is False
    assert TECHNIQUES.create("counter").keyed is False
    assert TECHNIQUES.create("hmac").keyed is True
    assert TECHNIQUES.create("aes_siv").keyed is True


def test_hmac_depends_on_the_key():
    a = TECHNIQUES.create("hmac", key=b"\x01" * 32)
    b = TECHNIQUES.create("hmac", key=b"\x02" * 32)
    assert a.index(("PERSON\x1fweber",), "PERSON") != b.index(("PERSON\x1fweber",), "PERSON")


def test_aes_siv_separates_entity_types():
    t = TECHNIQUES.create("aes_siv")
    assert t.index(("x",), "PERSON") != t.index(("x",), "LOC")


def test_counter_is_ordinal_and_per_type():
    t = TECHNIQUES.create("counter")
    assert t.index(("a",), "PERSON") == 0
    assert t.index(("b",), "PERSON") == 1
    assert t.index(("a",), "PERSON") == 0
    assert t.index(("c",), "LOC") == 0


def test_table_seed_reproduces():
    a = TECHNIQUES.create("table", seed=7)
    b = TECHNIQUES.create("table", seed=7)
    assert [a.index((k,), "PERSON") for k in "abc"] == [b.index((k,), "PERSON") for k in "abc"]


def test_table_without_replacement_cannot_collide():
    """ENISA warns about collisions; testing that warning needs a mode where they can occur."""
    without = TECHNIQUES.create("table", seed=1, replacement=False, space=8)
    values = [without.index((f"k{i}",), "PERSON") for i in range(8)]
    assert len(set(values)) == 8

    with_repl = TECHNIQUES.create("table", seed=1, replacement=True, space=4)
    drawn = [with_repl.index((f"k{i}",), "PERSON") for i in range(40)]
    assert len(set(drawn)) < 40  # collisions are possible, and observed
