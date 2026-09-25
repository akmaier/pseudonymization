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


# ---------------------------------------------------------- the consistency check and redraw
# AM, 2026-09-15: a surrogate that is the wrong *kind* of thing does not make sense; draw again.
# The first real CARDIO:DE build produced "42.87.1008" — day 42 of month 87 — for a date-shaped
# CODE span, because format preservation copies the layout and not the meaning.

from pseudonymkit.surrogates import (            # noqa: E402
    Checked,
    SurrogateRejected,
    code_is_consistent,
    differs_from_source,
)


def test_a_date_shaped_code_renders_a_real_date():
    form = Checked(FormatPreserving(), code_is_consistent)
    for index in range(40):                       # many entities, every one must come out valid
        out = form.render(index, mention("04.12.1980", "CODE"), "de")
        day, month, year = (int(p) for p in out.split("."))
        assert 1 <= day <= 31 and 1 <= month <= 12, out
        import calendar
        assert day <= calendar.monthrange(year, month)[1], out


def test_a_time_shaped_code_renders_a_real_time():
    form = Checked(FormatPreserving(), code_is_consistent)
    for index in range(40):
        hour, minute = (int(p) for p in form.render(index, mention("09:45", "CODE"), "de").split(":"))
        assert hour < 24 and minute < 60


def test_an_unshaped_code_is_untouched_by_the_date_rule():
    form = Checked(FormatPreserving(), code_is_consistent)
    out = form.render(7, mention("john.smith@enron.com", "CODE"), "en")
    assert "@" in out and out != "john.smith@enron.com"


def test_the_check_never_returns_the_original():
    form = Checked(FormatPreserving(), code_is_consistent)
    for index in range(60):
        assert form.render(index, mention("4711", "CODE"), "de") != "4711"


def test_redrawing_is_deterministic_so_stability_survives():
    a, b = Checked(FormatPreserving(), code_is_consistent), Checked(FormatPreserving(), code_is_consistent)
    m = mention("04.12.1980", "CODE")
    assert a.render(99, m, "de") == b.render(99, m, "de")


def test_a_pooled_surrogate_never_equals_the_name_it_replaces():
    inventory = SyntheticInventory(pool_size=8)   # small on purpose: collisions are likely
    form = Checked(SURROGATES.create("realistic", inventory=inventory), differs_from_source)
    for index in range(60):
        surface = inventory.surface(index, "PERSON", "en")
        assert form.render(index, mention(surface, "PERSON"), "en") != surface


def test_an_unsatisfiable_check_is_reported_not_papered_over():
    form = Checked(FormatPreserving(), lambda *_: False, attempts=4)
    with pytest.raises(SurrogateRejected):
        form.render(1, mention("abc", "CODE"), "en")


def test_the_number_of_redraws_is_counted_for_reporting():
    """A small pool collides with the original often, so the counter moves.

    Dates deliberately do not appear here: they are generated inside their valid ranges rather than
    retried into them, so they cost zero redraws. The counter is a rate worth reporting — it says
    how often the pool is too small to avoid handing an entity back its own value."""
    inventory = SyntheticInventory(pool_size=4)
    form = Checked(SURROGATES.create("realistic", inventory=inventory), differs_from_source)
    for index in range(40):
        form.render(index, mention(inventory.surface(index, "PERSON", "en"), "PERSON"), "en")
    assert form.redraws > 0


def test_demographic_is_not_identity_checked():
    """A two-valued category forced to differ becomes invertible: every Herr would become Frau."""
    from pseudonymkit.conditions import IDENTITY_CHECKED, POOLED

    assert "DEMOGRAPHIC" in POOLED and "DEMOGRAPHIC" not in IDENTITY_CHECKED


def test_condition_b_routes_each_type_to_a_checked_renderer():
    engine = build("B", inventory=SyntheticInventory(pool_size=4096), key=KEY)
    assert engine.surrogate.for_type("CODE").name == "checked"
    assert engine.surrogate.for_type("PERSON").name == "checked"
    assert engine.surrogate.for_type("DEMOGRAPHIC").name == "realistic"
    assert engine.surrogate.for_type("DATETIME").name == "unchanged"


def test_a_span_with_nothing_substitutable_is_not_required_to_change():
    """The union rule labelled a bare "(" as CODE. Format preservation keeps punctuation, so no
    redraw can ever differ from it — and a span with no letter and no digit hides no identifier."""
    form = Checked(FormatPreserving(), code_is_consistent)
    assert form.render(3, mention("(", "CODE"), "de") == "("
    assert form.render(3, mention(" - ", "CODE"), "de") == " - "


def test_but_anything_with_a_letter_or_digit_must_still_change():
    form = Checked(FormatPreserving(), code_is_consistent)
    for surface in ("A", "7", "(x)"):
        assert form.render(5, mention(surface, "CODE"), "de") != surface


# --- plausible years (AM, 2026-09-15) -----------------------------------------------------------
# "16.01.5628" is a real date but not one a clinical letter carries. The year band is enforced by
# the check and satisfied by construction: a blind retry would exhaust its budget on two thirds of
# date-shaped spans once a 200-year window is required.

from pseudonymkit.surrogates import PLAUSIBLE_YEARS      # noqa: E402


def test_a_four_digit_year_lands_in_the_plausible_band():
    form = Checked(FormatPreserving(), code_is_consistent)
    for index in range(300):
        year = int(form.render(index, mention("04.12.1980", "CODE"), "de").split(".")[2])
        assert PLAUSIBLE_YEARS[0] <= year <= PLAUSIBLE_YEARS[1], year


def test_component_widths_are_preserved_so_length_never_changes():
    form = Checked(FormatPreserving(), code_is_consistent)
    for surface in ("04.12.1980", "1.6.19", "2019-07-04", "9:45", "09:45:07"):
        for index in range(25):
            out = form.render(index, mention(surface, "CODE"), "de")
            assert len(out) == len(surface), (surface, out)


def test_iso_and_slash_dates_are_valid_too():
    import datetime
    form = Checked(FormatPreserving(), code_is_consistent)
    for index in range(60):
        y, m, d = (int(p) for p in form.render(index, mention("2019-07-04", "CODE"), "de").split("-"))
        datetime.date(y, m, d)                       # raises if the surrogate is not a real date


def test_a_two_digit_year_is_not_band_constrained():
    """Every value 00-99 is plausible, and constraining it would shrink the space for nothing."""
    form = Checked(FormatPreserving(), code_is_consistent)
    years = {form.render(i, mention("1.6.19", "CODE"), "de").split(".")[2] for i in range(80)}
    assert len(years) > 10


def test_dates_need_no_redraws_now_that_they_are_generated_directly():
    form = Checked(FormatPreserving(), code_is_consistent)
    for index in range(200):
        form.render(index, mention("04.12.1980", "CODE"), "de")
    assert form.redraws == 0
