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
