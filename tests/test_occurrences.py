"""Occurrence-level surrogate/survivor labels (plan §10 item 3).

All names are invented. The fixture is one document in which the defender's detector caught some
mentions, missed others, caught one only in part, and caught one under a type that condition B
renders verbatim — the four cases that decide a label.
"""

from __future__ import annotations

from pseudonymkit.attacks.occurrences import label_document, label_occurrences
from pseudonymkit.conditions import build as build_condition
from pseudonymkit.domain import Corpus, Document, Mention, Span
from pseudonymkit.inventories import SyntheticInventory

KEY = b"\x44" * 32
TEXT = "Weber met Anna Kraus today. Then, Weber wrote to Meyer."


def span(surface: str, nth: int = 0, kind: str = "PERSON", text: str = TEXT) -> Span:
    start = -1
    for _ in range(nth + 1):
        start = text.index(surface, start + 1)
    return Span(start, start + len(surface), surface, kind)


def gold() -> Document:
    golds = [(span("Weber"), "e1"), (span("Anna Kraus"), "e2"), (span("Weber", 1), "e1"),
             (span("Meyer"), "e3")]
    return Document("d1", TEXT, "en", tuple(
        Mention("d1", f"g{i}", s, gold_entity_id=e) for i, (s, e) in enumerate(golds)))


def released(detected_spans, text: str = TEXT):
    """The release a defender produces when it detected exactly ``detected_spans``."""
    detected = Document("d1", text, "en", tuple(
        Mention("d1", f"m{i}", s, gold_entity_id=e) for i, (s, e) in enumerate(detected_spans)))
    condition = build_condition("B", inventory=SyntheticInventory(pool_size=4096), key=KEY)
    return condition.pseudonymise_corpus(Corpus("fixture", (detected,)))


def by_surface(occurrences):
    return {o.surface: o for o in occurrences}


def test_a_replaced_mention_is_a_surrogate_and_carries_its_entity():
    result = released([(span("Weber"), "e1")])
    occurrences = label_occurrences(result, [gold()])
    surrogates = [o for o in occurrences if o.label == "surrogate"]
    assert len(surrogates) == 1
    assert surrogates[0].entity == "e1"
    assert surrogates[0].surface != "Weber"
    assert (surrogates[0].old_start, surrogates[0].old_end) == (span("Weber").start,
                                                                span("Weber").end)


def test_a_missed_mention_is_a_survivor_with_its_offsets_mapped_back():
    result = released([(span("Weber"), "e1")])
    occurrences = label_document(result.documents[0], gold())
    survivors = [o for o in occurrences if o.label == "survivor"]
    surfaces = sorted(o.surface for o in survivors)
    assert surfaces == ["Anna Kraus", "Meyer", "Weber"]
    second = next(o for o in survivors if o.surface == "Weber")
    assert (second.old_start, second.old_end) == (span("Weber", 1).start, span("Weber", 1).end)
    assert result.documents[0].text[second.start:second.end] == "Weber"


def test_the_same_string_is_a_surrogate_at_one_position_and_a_survivor_at_the_next():
    """The defect of surface-keyed tables: a survivor named like another entity's surrogate."""
    surrogate = next(o for o in label_document(released([(span("Weber"), "e1")]).documents[0],
                                               gold()) if o.label == "surrogate").surface
    text = f"Weber met {surrogate} today."
    namesake = Document("d1", text, "en", (
        Mention("d1", "g0", span("Weber", text=text), gold_entity_id="e1"),
        Mention("d1", "g1", span(surrogate, text=text), gold_entity_id="e9"),
    ))
    result = released([(span("Weber", text=text), "e1")], text=text)
    assert result.documents[0].text == f"{surrogate} met {surrogate} today."
    labels = [(o.label, o.entity) for o in label_document(result.documents[0], namesake)
              if o.surface == surrogate]
    assert labels == [("surrogate", "e1"), ("survivor", "e9")]


def test_a_partly_replaced_name_is_split_at_the_boundary():
    result = released([(span("Anna"), "e2")])
    occurrences = label_document(result.documents[0], gold())
    pieces = [(o.label, o.surface, o.entity) for o in occurrences
              if span("Anna Kraus").start <= o.old_start < span("Anna Kraus").end]
    labels = sorted(label for label, _, _ in pieces)
    assert labels == ["surrogate", "survivor"]
    assert ("survivor", "Kraus", "e2") in pieces


def test_a_replacement_that_left_the_text_unchanged_is_not_a_surrogate():
    # MISC is rendered verbatim under B, so a person detected as MISC is still in the release.
    result = released([(span("Meyer", 0, "MISC"), "e3")])
    occurrences = by_surface(label_document(result.documents[0], gold()))
    assert "Meyer" in result.documents[0].text
    assert occurrences["Meyer"].label == "survivor"
    assert occurrences["Meyer"].entity == "e3"


def test_ordinary_capitalised_words_are_other():
    result = released([(span("Weber"), "e1")])
    occurrences = by_surface(label_document(result.documents[0], gold()))
    assert occurrences["Then"].label == "other"
    assert occurrences["Then"].entity is None


def test_offsets_name_the_characters_in_the_release():
    result = released([(span("Weber"), "e1"), (span("Meyer"), "e3")])
    text = result.documents[0].text
    for o in label_document(result.documents[0], gold()):
        assert text[o.start:o.end] == o.surface
