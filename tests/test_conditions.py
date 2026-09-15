"""The three conditions of experiment_plan.md §7.

The tests assert what the plan's table claims about each condition — what identifiers become, what is
linkable, what is reversible — rather than that a factory returns an object.  Condition A's job in
particular is easy to get subtly wrong: it must be byte-identical to the corpus *and* produce a
complete assignment list, because §8.4 runs the relational attacks on it as the ceiling.
"""

from __future__ import annotations

import pytest

from pseudonymkit.conditions import SPECS, Unmodified, build
from pseudonymkit.domain import Corpus, Document, Mention, Span
from pseudonymkit.inventories import SyntheticInventory
from pseudonymkit.surrogates import SURROGATES

KEY = b"\x11" * 32


def build_doc(doc_id: str, text: str, entities: list[tuple[str, str, str | None]]) -> Document:
    cursor = 0
    mentions = []
    for i, (surface, type_, chain) in enumerate(entities):
        start = text.index(surface, cursor)
        cursor = start + len(surface)
        mentions.append(
            Mention(doc_id, f"m{i}", Span(start, start + len(surface), surface, type_),
                    gold_entity_id=chain)
        )
    return Document(doc_id, text, "en", tuple(mentions))


@pytest.fixture
def corpus() -> Corpus:
    a = build_doc(
        "d1", "Dr. Weber met Weber in Berlin.",
        [("Dr. Weber", "PERSON", "e1"), ("Weber", "PERSON", "e1"), ("Berlin", "LOC", "e2")],
    )
    b = build_doc(
        "d2", "Weber wrote from Berlin to Meyer.",
        [("Weber", "PERSON", "e1"), ("Berlin", "LOC", "e2"), ("Meyer", "PERSON", "e3")],
    )
    return Corpus("fixture", (a, b))


def condition(name: str):
    if name == "A":
        return build("A")
    return build(name, inventory=SyntheticInventory(pool_size=4096), key=KEY)


# ------------------------------------------------------------------------------ the specification


def test_there_are_exactly_three_conditions():
    assert sorted(SPECS) == ["A", "B", "C"]


def test_the_specs_match_the_plans_table():
    assert (SPECS["A"].label, SPECS["A"].linkable, SPECS["A"].reversible) == (
        "full data", True, "—")
    assert (SPECS["B"].label, SPECS["B"].linkable, SPECS["B"].reversible) == (
        "pseudonymised", True, "with the key")
    assert (SPECS["C"].label, SPECS["C"].linkable, SPECS["C"].reversible) == (
        "de-identified", False, "no")


def test_b_is_n2_deterministic_hmac_routed():
    """B's surrogate form became ``routed`` on 2026-09-14.

    It was ``realistic``, which was only ever true of the types that have a pool.  Condition B has
    to render all eight harmonised types, and three of them cannot be drawn from a list — CODE is
    constructed, DATETIME/QUANTITY/MISC are deliberately left alone.  Routing keeps that inside the
    surrogate-form axis, so the test below still finds exactly one level of difference against C.
    """
    spec = SPECS["B"]
    assert (spec.normaliser, spec.policy, spec.technique, spec.surrogate) == (
        "N2", "deterministic", "hmac", "routed")


def test_names_places_and_organisations_are_still_rendered_realistically():
    """What the previous assertion was really protecting: B does not degrade to placeholders."""
    engine = build("B", inventory=SyntheticInventory(pool_size=4096), key=KEY)

    def underlying(entity_type):
        form = engine.surrogate.for_type(entity_type)
        return getattr(form, "inner", form).name      # unwrap the consistency check

    for entity_type in ("PERSON", "LOC", "ORG", "DEMOGRAPHIC"):
        assert underlying(entity_type) == "realistic"
    assert underlying("CODE") == "format_preserving"
    for entity_type in ("DATETIME", "QUANTITY", "MISC"):
        assert underlying(entity_type) == "unchanged"


def test_b_and_c_differ_in_exactly_one_axis_level():
    """H2's exchange rate is only attributable if the pair differ in one thing."""
    b, c = SPECS["B"], SPECS["C"]
    differences = {
        field
        for field in ("normaliser", "policy", "technique", "surrogate")
        if getattr(b, field) != getattr(c, field)
    }
    assert differences == {"surrogate"}


def test_stability_is_meaningful_for_b_only():
    """§8.2: under C every identifier of a type is one string, so there is no mapping."""
    assert [SPECS[n].stability_meaningful for n in ("A", "B", "C")] == [False, True, False]


def test_describe_records_the_key_id_and_never_the_key():
    row = SPECS["B"].describe(key_id="hmac-2026-09")
    assert row["key_id"] == "hmac-2026-09"
    assert "\x11" not in repr(row)


def test_an_unknown_condition_is_refused():
    with pytest.raises(KeyError):
        build("D")


# ----------------------------------------------------------------------------------- condition A


def test_a_leaves_the_text_byte_identical(corpus):
    result = condition("A").pseudonymise_corpus(corpus)
    assert [d.text for d in result.documents] == [d.text for d in corpus.documents]


def test_a_still_produces_one_assignment_per_mention(corpus):
    """§8.4 runs A3/A4/A5 on A as the ceiling, and they read the assignment list."""
    result = condition("A").pseudonymise_corpus(corpus)
    assert [len(d.assignments) for d in result.documents] == [3, 3]
    assert [a.surface for a in result.documents[0].assignments] == ["Dr. Weber", "Weber", "Berlin"]


def test_a_does_not_reuse_one_surface_for_an_entitys_other_forms(corpus):
    """'Dr. Weber' and 'Weber' are one entity under N2; reusing one surface would rewrite the text."""
    result = condition("A").pseudonymise_corpus(corpus)
    first = result.documents[0]
    assert first.assignments[0].surface != first.assignments[1].surface
    assert first.text == corpus.documents[0].text


def test_a_skips_overlaps_exactly_as_b_does():
    text = "Dr. Weber spoke."
    doc = Document("d1", text, "en", (
        Mention("d1", "m0", Span(0, 9, "Dr. Weber", "PERSON")),
        Mention("d1", "m1", Span(4, 9, "Weber", "PERSON")),
    ))
    a = condition("A").pseudonymise(doc)
    b = condition("B").pseudonymise(doc)
    assert [m.mention_id for m in a.skipped] == [m.mention_id for m in b.skipped] == ["m1"]
    assert a.text == text


# ----------------------------------------------------------------------------------- condition B


def test_b_replaces_every_identifier_with_something_realistic(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    assert all("Weber" not in d.text and "Berlin" not in d.text for d in result.documents)
    assert all("[" not in d.text for d in result.documents)


def test_b_gives_one_entity_one_surrogate_corpus_wide(corpus):
    """The stability §5 says the data's usability depends on."""
    result = condition("B").pseudonymise_corpus(corpus)
    weber = {
        a.surface
        for d in result.documents
        for a in d.assignments
        if a.entity_key == "PERSON\x1fweber"
    }
    assert len(weber) == 1


def test_b_keeps_distinct_people_distinct(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    surfaces = {
        a.entity_key: a.surface
        for d in result.documents for a in d.assignments if a.entity_type == "PERSON"
    }
    assert len(set(surfaces.values())) == len(surfaces)


def test_b_needs_an_inventory_and_a_key():
    with pytest.raises(ValueError, match="inventory"):
        build("B", key=KEY)
    with pytest.raises(ValueError, match="key material"):
        build("B", inventory=SyntheticInventory())


def test_b_is_reproducible_from_its_configuration(corpus):
    one = condition("B").pseudonymise_corpus(corpus)
    two = condition("B").pseudonymise_corpus(corpus)
    assert [d.text for d in one.documents] == [d.text for d in two.documents]


def test_b_depends_on_the_key(corpus):
    other = build("B", inventory=SyntheticInventory(pool_size=4096), key=b"\x22" * 32)
    assert [d.text for d in condition("B").pseudonymise_corpus(corpus).documents] != [
        d.text for d in other.pseudonymise_corpus(corpus).documents
    ]


# ----------------------------------------------------------------------------------- condition C


def test_c_makes_every_person_the_same_string(corpus):
    result = condition("C").pseudonymise_corpus(corpus)
    assert result.documents[0].text == "[PERSON] met [PERSON] in [LOCATION]."
    assert result.documents[1].text == "[PERSON] wrote from [LOCATION] to [PERSON]."


def test_c_carries_no_index(corpus):
    """§7: a typed placeholder *without* an index, so all persons look alike."""
    result = condition("C").pseudonymise_corpus(corpus)
    assert "[PERSON_1]" not in result.documents[0].text
    assert "_" not in result.documents[0].text


def test_c_is_not_linkable_because_the_index_is_discarded(corpus):
    result = condition("C").pseudonymise_corpus(corpus)
    surfaces = {a.surface for d in result.documents for a in d.assignments
                if a.entity_type == "PERSON"}
    assert surfaces == {"[PERSON]"}


def test_c_needs_no_key_because_the_index_goes_nowhere(corpus):
    result = build("C").pseudonymise_corpus(corpus)
    assert result.documents[0].text == "[PERSON] met [PERSON] in [LOCATION]."


def test_placeholder_uses_the_harmonised_name_except_for_loc():
    placeholder = SURROGATES.create("placeholder")
    mention = Mention("d1", "m0", Span(0, 1, "x", "ORG"))
    assert placeholder.render(7, mention, "en") == "[ORG]"
    loc = Mention("d1", "m1", Span(0, 1, "x", "LOC"))
    assert placeholder.render(7, loc, "en") == "[LOCATION]"


def test_the_placeholder_ignores_the_index_entirely():
    placeholder = SURROGATES.create("placeholder")
    mention = Mention("d1", "m0", Span(0, 1, "x", "PERSON"))
    assert placeholder.render(1, mention, "en") == placeholder.render(9_999_999, mention, "en")


# --------------------------------------------------------------------- all three, one interface


@pytest.mark.parametrize("name", ["A", "B", "C"])
def test_every_condition_offers_the_same_interface(name, corpus):
    result = condition(name).pseudonymise_corpus(corpus)
    assert len(result.documents) == len(corpus)
    assert all(isinstance(d.text, str) for d in result.documents)
    assert result.mapping is not None


def test_unmodified_is_the_condition_a_object():
    assert isinstance(build("a"), Unmodified)
    assert build("a").spec is SPECS["A"]
