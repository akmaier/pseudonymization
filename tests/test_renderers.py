"""The renderers for the types condition B cannot draw from a name list.

Three of the eight harmonised types have no surrogate pool, for a different reason each:

* ``CODE`` — 35.2 % of the study's mentions and all 444,332 of Enron's — has no finite list to draw
  from; a phone number or an e-mail address has to be *constructed*.
* ``DEMOGRAPHIC`` has a pool, but one compiled from the corpora rather than fetched.
* ``DATETIME``, ``QUANTITY`` and ``MISC`` are deliberately not pseudonymised (AM, 2026-09-13).

Until these existed, condition B could not be built for a single document in any of the four corpora:
one unrenderable mention raises, and 100 % of CARDIO:DE, TAB and Enron documents carry at least one.
"""

from __future__ import annotations

import pytest

from pseudonymkit.conditions import CONSTRUCTED, POOLED, UNCHANGED, build
from pseudonymkit.domain import Document, Mention, Span
from pseudonymkit.gazetteers_intl import attested_pool, build_attested_inventory
from pseudonymkit.inventories import SyntheticInventory
from pseudonymkit.surrogates import SURROGATES, FormatPreserving, PassThrough, TypeRouted

KEY = b"\x22" * 32


def mention(surface: str, type_: str, doc_id: str = "d1") -> Mention:
    return Mention(doc_id, "m0", Span(0, len(surface), surface, type_))


def render(form, surface: str, type_: str, index: int = 12345, language: str = "en") -> str:
    return form.render(index, mention(surface, type_), language)


# ------------------------------------------------------------------------------- pass-through


def test_pass_through_returns_the_surface_untouched():
    form = PassThrough()
    for surface in ("16.01.2013", "3.5 %", "EUR 40,000", "a birthmark"):
        assert render(form, surface, "DATETIME") == surface


def test_pass_through_ignores_the_index_entirely():
    form = PassThrough()
    assert render(form, "2013", "DATETIME", index=1) == render(form, "2013", "DATETIME", index=99999)


# ---------------------------------------------------------------------------- format preserving


@pytest.fixture
def code() -> FormatPreserving:
    return FormatPreserving()


def test_length_and_layout_survive(code):
    for surface in ("+49 9131 85-27775", "john.smith@enron.com", "AB-1234/99"):
        out = render(code, surface, "CODE")
        assert len(out) == len(surface)
        for original, rendered in zip(surface, out):
            assert original.isdigit() == rendered.isdigit()
            assert original.isalpha() == rendered.isalpha()
            assert original.isupper() == rendered.isupper()
            if not original.isalnum():
                assert rendered == original, f"{original!r} should be kept in place"


def test_the_content_does_not_survive(code):
    # i2b2 and Eder both overwrite the whole string; Carrell keeps a true prefix. We follow i2b2.
    surface = "john.smith@enron.com"
    out = render(code, surface, "CODE")
    assert out != surface
    assert "enron" not in out
    assert "john" not in out


def test_a_url_scheme_and_www_are_kept_but_nothing_after_them(code):
    surface = "https://www.example.org/a1"
    out = render(code, surface, "CODE")
    assert out.startswith("https://www.")      # Eder et al. keep the scheme and the subdomain
    assert "example" not in out and "org" not in out
    assert len(out) == len(surface)
    assert out.count("/") == 3 and out.count(".") == 2   # separators stay where they were


def test_the_same_entity_renders_the_same_code_every_time(code):
    first = render(code, "0170 1234567", "CODE", index=777)
    assert first == render(code, "0170 1234567", "CODE", index=777)


def test_a_different_entity_renders_a_different_code(code):
    assert render(code, "0170 1234567", "CODE", index=1) != render(
        code, "0170 1234567", "CODE", index=2)


def test_non_ascii_alphanumerics_are_counted_rather_than_silently_kept(code):
    # Measured 2026-09-14: zero such characters in the study's 448,774 CODE spans. The counter is
    # here so a corpus that breaks that assumption reports itself instead of leaking.
    assert code.unsubstitutable == 0
    render(code, "AZ-٣٤٥", "CODE")
    assert code.unsubstitutable == 3


# ------------------------------------------------------------------------------------ routing


def test_routing_sends_each_type_to_its_own_renderer():
    pooled, constructed, unchanged = (
        SURROGATES.create("realistic", inventory=SyntheticInventory(pool_size=64)),
        SURROGATES.create("format_preserving"),
        SURROGATES.create("unchanged"),
    )
    routed = TypeRouted({"CODE": constructed, "DATETIME": unchanged}, default=pooled)
    assert routed.for_type("CODE") is constructed
    assert routed.for_type("DATETIME") is unchanged
    assert routed.for_type("PERSON") is pooled


def test_the_three_type_groups_partition_the_taxonomy():
    from pseudonymkit.taxonomy import HARMONISED

    assert set(POOLED) | set(CONSTRUCTED) | set(UNCHANGED) == set(HARMONISED)
    assert not (set(POOLED) & set(CONSTRUCTED))
    assert not (set(POOLED) & set(UNCHANGED))
    assert not (set(CONSTRUCTED) & set(UNCHANGED))


# ------------------------------------------------------------------ condition B, end to end


TEXT = ("Weber called 0170 1234567 on 16.01.2013 about a 3.5 % share, "
        "writing to weber@example.org as the senior consultant.")
ENTITIES = [
    ("Weber", "PERSON"),
    ("0170 1234567", "CODE"),
    ("16.01.2013", "DATETIME"),
    ("3.5 %", "QUANTITY"),
    ("weber@example.org", "CODE"),
    ("senior consultant", "DEMOGRAPHIC"),
]


def document() -> Document:
    cursor = 0
    mentions = []
    for i, (surface, type_) in enumerate(ENTITIES):
        start = TEXT.index(surface, cursor)
        cursor = start + len(surface)
        mentions.append(Mention("d1", f"m{i}", Span(start, start + len(surface), surface, type_)))
    return Document("d1", TEXT, "en", tuple(mentions))


@pytest.fixture
def condition_b():
    return build("B", inventory=SyntheticInventory(pool_size=4096), key=KEY)


def test_condition_b_no_longer_raises_on_a_document_with_every_type(condition_b):
    # Before routing existed this raised LookupError on the first CODE mention, which is why 100 %
    # of CARDIO:DE, TAB and Enron documents were unbuildable.
    assert condition_b.pseudonymise(document()).text


def test_dates_and_quantities_come_through_verbatim(condition_b):
    out = condition_b.pseudonymise(document()).text
    assert "16.01.2013" in out
    assert "3.5 %" in out


def test_codes_are_replaced_but_keep_their_shape(condition_b):
    out = condition_b.pseudonymise(document()).text
    assert "0170 1234567" not in out
    assert "weber@example.org" not in out
    assert "@example.org" not in out           # the domain is overwritten too
    assert "@" in out                           # but the address still looks like one


def test_the_person_is_replaced_from_the_pool(condition_b):
    out = condition_b.pseudonymise(document()).text
    assert "Weber called" not in out


def test_b_is_still_reversible_through_the_mapping(condition_b):
    result = condition_b.pseudonymise(document())
    surfaces = {a.entity_key: a.surface for a in result.assignments}
    assert len(surfaces) == len(ENTITIES)       # every mention got an assignment, codes included


# ------------------------------------------------------------------------ demographic pool


def demo_doc(doc_id: str, surfaces: list[str], language: str = "en") -> Document:
    text = " ".join(surfaces)
    cursor = 0
    mentions = []
    for i, surface in enumerate(surfaces):
        start = text.index(surface, cursor)
        cursor = start + len(surface)
        mentions.append(
            Mention(doc_id, f"m{i}", Span(start, start + len(surface), surface, "DEMOGRAPHIC")))
    return Document(doc_id, text, language, tuple(mentions))


def test_the_pool_is_built_from_values_the_corpus_attests():
    docs = [demo_doc("d1", ["nurse", "teacher"]), demo_doc("d2", ["nurse", "teacher"])]
    entries, report = attested_pool(docs, "DEMOGRAPHIC", "en")
    assert sorted(e.surface for e in entries) == ["nurse", "teacher"]
    assert report["mentions"] == 4 and report["distinct_attested"] == 2


def test_a_value_attested_once_is_replaced_but_never_used_as_a_replacement():
    # Carrell: an attribute identifies when it is "extremely rare". Putting a singleton in the pool
    # would let the pipeline insert a rare identifying attribute into a document that lacked one.
    docs = [demo_doc("d1", ["nurse", "retired chair of OB/GYN"]), demo_doc("d2", ["nurse"])]
    entries, report = attested_pool(docs, "DEMOGRAPHIC", "en")
    assert [e.surface for e in entries] == ["nurse"]
    assert report["dropped_below_min_count"] == 1


def test_frequency_is_carried_so_common_attributes_stay_common():
    docs = [demo_doc("d1", ["nurse", "nurse", "nurse"]), demo_doc("d2", ["teacher", "teacher"])]
    entries, _ = attested_pool(docs, "DEMOGRAPHIC", "en")
    by_surface = {e.surface: e.frequency for e in entries}
    assert by_surface["nurse"] == 3.0 and by_surface["teacher"] == 2.0


def test_a_language_the_corpus_does_not_attest_is_omitted_not_invented():
    docs = [demo_doc("d1", ["nurse", "teacher"], language="en"),
            demo_doc("d2", ["nurse", "teacher"], language="en")]
    inventory, reports = build_attested_inventory(docs, [("DEMOGRAPHIC", "en"), ("DEMOGRAPHIC", "de")])
    assert inventory.size("DEMOGRAPHIC", "en") == 2
    assert reports["DEMOGRAPHIC/de"]["pool"] == 0
    with pytest.raises(LookupError):
        inventory.surface(0, "DEMOGRAPHIC", "de")


def test_an_attested_pool_makes_condition_b_render_that_type():
    docs = [demo_doc("d1", ["nurse", "teacher"]), demo_doc("d2", ["nurse", "teacher"])]
    inventory, _ = build_attested_inventory(docs, [("DEMOGRAPHIC", "en")])
    form = SURROGATES.create("realistic", inventory=inventory)
    assert render(form, "senior consultant", "DEMOGRAPHIC") in {"nurse", "teacher"}
