"""Surrogate pools for German, Chinese and Arabic.

Condition B needs a *"realistic, locale-appropriate surrogate"* (§7). The §14 gazetteers are English
only, so B raised on CARDIO:DE and on OntoNotes' 1,911 Chinese and 446 Arabic documents. These pools
close that.
"""

from __future__ import annotations

import json

import pytest

from pseudonymkit.domain import Document, Mention, Span
from pseudonymkit.gazetteers_intl import (
    arabic_parts_from_documents,
    build_arabic_inventory,
    build_arabic_pool,
    build_chinese_inventory,
    build_german_inventory,
    load_chinese_names,
    load_codealltag_sublists,
    merge_inventories,
)
from pseudonymkit.inventories import Entry, ListInventory


# ------------------------------------------------------------------------------------- German


@pytest.fixture
def sublists(tmp_path):
    (tmp_path / "family.json").write_text(json.dumps({"A": ["Abt"], "B": ["Bauer", "Brandt"]}))
    (tmp_path / "male.json").write_text(json.dumps({"A": ["Andreas"], "J": ["Jonas"]}))
    (tmp_path / "female.json").write_text(json.dumps({"F": ["Franziska"], "M": ["Miriam"]}))
    (tmp_path / "city.json").write_text(json.dumps({
        "DE": {"E": ["Ellwangen"], "B": ["Bad Nauheim"]},
        "AT": {"W": ["Wien"]},
    }))
    (tmp_path / "street.json").write_text(json.dumps({"A": ["Ameisenstraße"]}))
    (tmp_path / "org.json").write_text(json.dumps({"A": ["Apfelscheune"]}))
    return tmp_path


def test_the_german_lists_load_with_sex_on_given_names(sublists):
    tables = load_codealltag_sublists(sublists)
    assert [e.surface for e in tables["surnames"]] == ["Abt", "Bauer", "Brandt"]
    genders = {e.surface: e.attributes["gender"] for e in tables["given_names"]}
    assert genders == {"Andreas": "M", "Jonas": "M", "Franziska": "F", "Miriam": "F"}


def test_only_german_cities_are_taken(sublists):
    """city.json nests by country; an Austrian city is not a German surrogate."""
    cities = {e.surface for e in load_codealltag_sublists(sublists)["cities"]}
    assert cities == {"Ellwangen", "Bad Nauheim"}
    assert "Wien" not in cities


def test_the_german_inventory_answers_for_de_and_refuses_other_languages(sublists):
    inventory = build_german_inventory(sublists)
    assert inventory.surface(0, "PERSON", "de")
    assert inventory.surface(0, "LOC", "de")
    with pytest.raises(LookupError):
        inventory.surface(0, "PERSON", "en")


def test_german_entries_carry_no_frequency(sublists):
    """Eder et al. drew frequency-independent, so a German draw is uniform — stated, not hidden."""
    tables = load_codealltag_sublists(sublists)
    assert {e.frequency for e in tables["surnames"]} == {1.0}


# ------------------------------------------------------------------------------------ Chinese


@pytest.fixture
def chinese(tmp_path):
    # Real column names and a BOM, as ChineseNames ships them: the BOM lands inside the first
    # column name and made every surname lookup miss silently until the loader used utf-8-sig.
    (tmp_path / "familyname.csv").write_text(
        "\ufeffsurname,compound,initial,initial.rank,n.1930_2008\n"
        "王,0,w,23,88465683\n李,0,l,12,87096536\n张,0,z,7,84800000\n", encoding="utf-8")
    (tmp_path / "givenname.csv").write_text(
        "\ufeffcharacter,pinyin,bihua,n.male,n.female\n"
        "伟,wei3,6,900000,10000\n芳,fang1,7,5000,800000\n", encoding="utf-8")
    return tmp_path


def test_chinese_surnames_carry_true_population_counts(chinese):
    tables = load_chinese_names(chinese)
    wang = next(e for e in tables["surnames"] if e.surface == "王")
    assert wang.frequency == 88465683


def test_a_chinese_character_that_is_used_by_both_sexes_yields_two_entries(chinese):
    given = load_chinese_names(chinese)["given_names"]
    wei = [e for e in given if e.surface == "伟"]
    assert {e.attributes["gender"] for e in wei} == {"M", "F"}


def test_the_chinese_inventory_makes_surname_plus_given_names(chinese):
    inventory = build_chinese_inventory(chinese, max_names=50)
    surrogate = inventory.surface(0, "PERSON", "zh")
    assert len(surrogate) >= 2
    assert surrogate[0] in "王李张"


# ------------------------------------------------------------------------------------- Arabic


def _ar(doc_id: str, spans) -> Document:
    text = " ".join(s for s, _ in spans)
    mentions, cursor = [], 0
    out = []
    for index, (surface, type_) in enumerate(spans):
        start = text.index(surface, cursor)
        out.append(Mention(doc_id, f"{doc_id}:{index}",
                           Span(start, start + len(surface), surface, type_)))
        cursor = start + len(surface)
    return Document(doc_id=doc_id, text=text, language="ar", mentions=tuple(out))


ARABIC_DOCS = [
    _ar("d1", [("جُورْج بُوش", "PERSON"), ("إِمِيل لَحُود", "PERSON")]),
    _ar("d2", [("ياسِر عَرَفات", "PERSON"), ("رَفِيق الحَرِيرِيّ", "PERSON")]),
]


def test_the_parts_come_from_the_corpus_with_their_diacritics():
    first, last, report = arabic_parts_from_documents(ARABIC_DOCS)
    assert "جُورْج" in first and "بُوش" in last
    assert report["spans"] == 4
    assert report["spans_with_diacritic"] == 4      # every one is marked, as in the corpus


def test_attested_names_are_excluded_from_the_pool():
    """A surrogate that is a real person in the same corpus makes a leakage number ambiguous."""
    first, last, report = arabic_parts_from_documents(ARABIC_DOCS)
    attested = report["attested"]
    pool = {e.surface for e in build_arabic_pool(first, last, attested)}
    assert "جُورْج بُوش" not in pool
    assert pool                                      # recombination still yields novel names


def test_the_arabic_pool_is_diacritised_because_its_parts_are():
    inventory, report = build_arabic_inventory(ARABIC_DOCS)
    surrogate = inventory.surface(0, "PERSON", "ar")
    assert any(0x064B <= ord(c) <= 0x0652 for c in surrogate)
    assert report["pool"] > 0


def test_tokenisation_punctuation_is_stripped_from_the_parts():
    """OntoNotes ENAMEX spans keep the punctuation inside them; a stray quote in a surrogate would
    be visible to any reader and to any classifier."""
    noisy = _ar("d3", [('" جُورْج -بُوش', "PERSON"), ("، ياسِر صوايا", "PERSON")])
    first, last, _ = arabic_parts_from_documents([noisy])
    assert all(not any(c in p for c in '"،-.,') for p in first + last)
    assert "جُورْج" in first and "صوايا" in last


def test_a_corpus_with_no_arabic_person_spans_is_refused_not_silently_empty():
    english = Document("x", "Anna", "en", mentions=(Mention("x", "m", Span(0, 4, "Anna", "PERSON")),))
    with pytest.raises(ValueError, match="no Arabic PERSON parts"):
        build_arabic_inventory([english])


# -------------------------------------------------------------------------------------- merge


def test_inventories_for_different_languages_merge(sublists, chinese):
    merged = merge_inventories(
        build_german_inventory(sublists),
        build_chinese_inventory(chinese, max_names=20),
        ListInventory({("PERSON", "en"): (Entry("Fiona Clarke"),)}),
    )
    assert merged.surface(0, "PERSON", "de")
    assert merged.surface(0, "PERSON", "zh")
    assert merged.surface(0, "PERSON", "en")


def test_two_inventories_covering_the_same_key_is_an_error_not_a_silent_choice(sublists):
    with pytest.raises(ValueError, match="refusing to pick one"):
        merge_inventories(build_german_inventory(sublists), build_german_inventory(sublists))
