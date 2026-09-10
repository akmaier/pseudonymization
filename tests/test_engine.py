import pytest

from pseudonymkit.domain import Corpus, Document, Mention, Span
from pseudonymkit.engine import Pseudonymiser
from pseudonymkit.inventories import SyntheticInventory
from pseudonymkit.keys import NORMALISERS
from pseudonymkit.policies import POLICIES
from pseudonymkit.surrogates import SURROGATES
from pseudonymkit.techniques import TECHNIQUES


def make(normaliser="N2", policy="deterministic", technique="hmac", surrogate="tag"):
    kwargs = {} if surrogate == "tag" else {"inventory": SyntheticInventory()}
    return Pseudonymiser(
        NORMALISERS.create(normaliser),
        POLICIES.create(policy),
        TECHNIQUES.create(technique),
        SURROGATES.create(surrogate, **kwargs),
    )


def test_replacement_preserves_surrounding_text(weber_doc):
    out = make().pseudonymise(weber_doc)
    assert " met " in out.text and out.text.endswith(".")
    assert "Weber" not in out.text and "Berlin" not in out.text


def test_deterministic_policy_unifies_normalised_forms(weber_doc):
    """N2 folds 'Dr. Weber' and 'Weber' together; 'F. Weber' still differs, which is fragmentation."""
    out = make(normaliser="N2").pseudonymise(weber_doc)
    person = [a.surface for a in out.assignments if a.entity_type == "PERSON"]
    assert person[0] == person[1] != person[2]


def test_n3_removes_the_remaining_fragmentation(weber_doc):
    out = make(normaliser="N3").pseudonymise(weber_doc)
    person = [a.surface for a in out.assignments if a.entity_type == "PERSON"]
    assert len(set(person)) == 1


def test_document_policy_differs_across_documents(two_doc_corpus):
    result = make(policy="document").pseudonymise_corpus(two_doc_corpus)
    first = {a.entity_key: a.surface for a in result.documents[0].assignments}
    second = {a.entity_key: a.surface for a in result.documents[1].assignments}
    assert set(first) == set(second)
    assert all(first[k] != second[k] for k in first)


def test_deterministic_policy_agrees_across_documents(two_doc_corpus):
    result = make(policy="deterministic").pseudonymise_corpus(two_doc_corpus)
    first = {a.entity_key: a.surface for a in result.documents[0].assignments}
    second = {a.entity_key: a.surface for a in result.documents[1].assignments}
    assert first == second


def test_full_randomisation_differs_per_mention(weber_doc):
    out = make(policy="full").pseudonymise(weber_doc)
    surfaces = [a.surface for a in out.assignments]
    assert len(set(surfaces)) == len(surfaces)


def test_overlapping_spans_are_skipped_and_reported():
    text = "Dr. Weber spoke."
    doc = Document(
        "d1", text, "en",
        (
            Mention("d1", "m0", Span(0, 9, "Dr. Weber", "PERSON")),
            Mention("d1", "m1", Span(4, 9, "Weber", "PERSON")),
        ),
    )
    out = make().pseudonymise(doc)
    assert len(out.assignments) == 1 and len(out.skipped) == 1
    assert out.text.endswith(" spoke.")


def test_tag_surrogate_numbers_from_one(weber_doc):
    out = make(surrogate="tag").pseudonymise(weber_doc)
    assert "[PERSON_1]" in out.text and "[LOC_1]" in out.text


@pytest.mark.parametrize("technique", TECHNIQUES.names())
def test_every_technique_runs_end_to_end(weber_doc, technique):
    out = make(technique=technique, surrogate="realistic").pseudonymise(weber_doc)
    assert len(out.assignments) == 5 and "Weber" not in out.text


def test_empty_document_is_unchanged():
    doc = Document("d0", "nothing here", "en", ())
    assert make().pseudonymise(doc).text == "nothing here"


# ----------------------------------------------------------- the document's language reaches the
# ----------------------------------------------------------- surrogate inventory (§12.2)


class RecordingInventory:
    """An inventory that answers per language and records what it was asked for."""

    def __init__(self, by_language: dict[str, str]):
        self._by_language = by_language
        self.asked: list[str] = []

    def size(self, entity_type, language, stratum=None):
        return 1 if language in self._by_language else 0

    def surface(self, index, entity_type, language, stratum=None):
        self.asked.append(language)
        if language not in self._by_language:
            raise LookupError(f"no surrogates for language={language!r}")
        return self._by_language[language]


def _one_person(doc_id: str, language: str, surface: str = "Weber") -> Document:
    text = f"{surface} called."
    return Document(
        doc_id, text, language,
        (Mention(doc_id, "m0", Span(0, len(surface), surface, "PERSON")),),
    )


def _engine(inventory) -> Pseudonymiser:
    return Pseudonymiser(
        NORMALISERS.create("N2"),
        POLICIES.create("deterministic"),
        TECHNIQUES.create("hmac"),
        SURROGATES.create("realistic", inventory=inventory),
    )


def test_the_documents_language_selects_the_surrogate_pool():
    """§12.2: 1,911 Chinese and 446 Arabic OntoNotes documents were given English surrogates."""
    inventory = RecordingInventory({"en": "Powers", "zh": "王", "ar": "علي"})
    corpus = Corpus("mixed", (
        _one_person("en1", "en", "Weber"),
        _one_person("zh1", "zh", "张三"),
        _one_person("ar1", "ar", "محمد"),
    ))
    result = _engine(inventory).pseudonymise_corpus(corpus)
    assert inventory.asked == ["en", "zh", "ar"]
    assert [d.text for d in result.documents] == [
        "Powers called.", "王 called.", "علي called.",
    ]


def test_one_entity_in_two_languages_keeps_one_pseudonym():
    """Stability beats locale under the deterministic policy, and that is the policy's point.

    An entity written identically in two documents of different languages is *one* entity, so it
    gets *one* pseudonym — drawn from the pool of the language it was first seen in. Giving it a
    locale-appropriate surrogate in each language would break the corpus-wide stability §5 says the
    data's usability depends on.
    """
    inventory = RecordingInventory({"en": "Powers", "zh": "王"})
    corpus = Corpus("mixed", (_one_person("en1", "en"), _one_person("zh1", "zh")))
    result = _engine(inventory).pseudonymise_corpus(corpus)
    assert inventory.asked == ["en"]
    assert [d.text for d in result.documents] == ["Powers called.", "Powers called."]


def test_a_mention_attribute_still_overrides_the_document():
    """A quoted foreign name inside an otherwise German letter keeps its own pool."""
    inventory = RecordingInventory({"de": "Bauer", "en": "Powers"})
    engine = _engine(inventory)
    text = "Weber called."
    doc = Document("d1", text, "de", (
        Mention("d1", "m0", Span(0, 5, "Weber", "PERSON"), attributes={"language": "en"}),
    ))
    assert engine.pseudonymise(doc).text == "Powers called."
    assert inventory.asked == ["en"]


def test_a_language_with_no_gazetteer_is_loud_rather_than_silently_english():
    """§1: an impossible cell is reported, never substituted."""
    inventory = RecordingInventory({"en": "Powers"})
    with pytest.raises(LookupError):
        _engine(inventory).pseudonymise(_one_person("zh1", "zh", "张三"))


def test_assign_requires_a_language():
    """No default: the defect being fixed was exactly a default of "en"."""
    engine = make(surrogate="realistic")
    mention = Mention("d1", "m0", Span(0, 5, "Weber", "PERSON"))
    with pytest.raises(TypeError):
        engine.assign(mention)


# ------------------------------------------------ mapping gold offsets onto pseudonymised text


def _replaced() -> tuple[Document, "PseudonymisedDocument"]:
    from pseudonymkit.conditions import build as build_condition

    text = "Dr. Weber met Meyer in Berlin."
    doc = Document("d1", text, "en", (
        Mention("d1", "m0", Span(0, 9, "Dr. Weber", "PERSON")),
        Mention("d1", "m1", Span(14, 19, "Meyer", "PERSON")),
        Mention("d1", "m2", Span(23, 29, "Berlin", "LOC")),
    ))
    return doc, build_condition("C").pseudonymise(doc)


def test_replacements_report_where_each_surrogate_landed():
    from pseudonymkit.engine import replacements

    doc, out = _replaced()
    assert out.text == "[PERSON] met [PERSON] in [LOCATION]."
    for r in replacements(out):
        assert out.text[r.new_start : r.new_end] == r.assignment.surface


def test_offset_map_moves_an_untouched_span_by_the_accumulated_shift():
    from pseudonymkit.engine import offset_map

    doc, out = _replaced()
    mapping = offset_map(out)
    start, end = mapping.span(doc.text.index("met"), doc.text.index("met") + 3)
    assert out.text[start:end] == "met"
    start, end = mapping.span(doc.text.index(" in "), doc.text.index(" in ") + 4)
    assert out.text[start:end] == " in "


def test_offset_map_carries_a_replaced_span_onto_its_surrogate():
    from pseudonymkit.engine import offset_map

    doc, out = _replaced()
    mapping = offset_map(out)
    start, end = mapping.span(0, 9)
    assert out.text[start:end] == "[PERSON]"
    start, end = mapping.span(23, 29)
    assert out.text[start:end] == "[LOCATION]"


def test_offset_map_extends_a_span_that_overlaps_a_replacement():
    """A gold span covering part of a replaced entity keeps the entity, not the characters."""
    from pseudonymkit.engine import offset_map

    doc, out = _replaced()
    mapping = offset_map(out)
    # "Weber met Meyer" starts inside the first replacement and ends inside the second.
    start, end = mapping.span(4, 19)
    assert out.text[start:end] == "[PERSON] met [PERSON]"


def test_offset_map_of_the_unmodified_condition_is_the_identity():
    from pseudonymkit.conditions import build as build_condition
    from pseudonymkit.engine import offset_map

    doc, _ = _replaced()
    out = build_condition("A").pseudonymise(doc)
    mapping = offset_map(out)
    assert all(mapping.span(i, i + 1) == (i, i + 1) for i in range(len(doc.text)))
