"""The TAB adapter, exercised against an inline fixture so tests never need the corpus."""

import json

import pytest

from pseudonymkit.adapters import tab

RECORD = {
    "doc_id": "001-90194",
    "text": "Dr. Weber applied. Weber lives in Berlin.",
    "dataset_type": "train",
    "quality_checked": True,
    "meta": {"year": 2008, "countries": "DNK", "legal_branch": "CHAMBER", "articles": [6, 41]},
    "annotations": {
        "annotator1": {
            "entity_mentions": [
                {"entity_mention_id": "a1_em1", "entity_type": "PERSON", "start_offset": 0,
                 "end_offset": 9, "entity_id": "e1", "identifier_type": "DIRECT",
                 "confidential_status": "NOT_CONFIDENTIAL"},
                {"entity_mention_id": "a1_em2", "entity_type": "PERSON", "start_offset": 19,
                 "end_offset": 24, "entity_id": "e1", "identifier_type": "DIRECT",
                 "confidential_status": "NOT_CONFIDENTIAL"},
                {"entity_mention_id": "a1_em3", "entity_type": "LOC", "start_offset": 34,
                 "end_offset": 40, "entity_id": "e2", "identifier_type": "QUASI",
                 "confidential_status": "NOT_CONFIDENTIAL"},
            ]
        },
        "annotator2": {
            "entity_mentions": [
                {"entity_mention_id": "a2_em1", "entity_type": "PERSON", "start_offset": 4,
                 "end_offset": 9, "entity_id": "e1", "identifier_type": "DIRECT",
                 "confidential_status": "NOT_CONFIDENTIAL"},
            ]
        },
    },
}


@pytest.fixture
def split_file(tmp_path):
    path = tmp_path / "echr_train.json"
    path.write_text(json.dumps([RECORD]), encoding="utf-8")
    return path


def test_offsets_agree_with_the_text(split_file):
    doc = next(tab.load_split(split_file))
    for m in doc.mentions:
        assert doc.text[m.span.start : m.span.end] == m.span.text


def test_types_are_harmonised(split_file):
    doc = next(tab.load_split(split_file))
    assert [m.type for m in doc.mentions] == ["PERSON", "PERSON", "LOC"]
    assert doc.mentions[0].span.type_src == "PERSON"


def test_dem_is_renamed_but_the_source_label_is_kept():
    assert tab.TYPE_MAP["DEM"] == "DEMOGRAPHIC"


def test_coreference_chains_survive(split_file):
    doc = next(tab.load_split(split_file))
    assert {m.gold_entity_id for m in doc.mentions if m.type == "PERSON"} == {"e1"}


def test_article_labels_become_the_downstream_task(split_file):
    doc = next(tab.load_split(split_file))
    assert doc.task == {"name": "echr_articles", "label": (6, 41)}


def test_no_cross_document_identity_is_claimed(split_file):
    """TAB's entity_id is document-scoped; asserting otherwise would silently corrupt drift."""
    assert next(tab.load_split(split_file)).subject_id is None


def test_annotator_choice_changes_the_mentions(split_file):
    first = next(tab.load_split(split_file, annotator="first"))
    checked = next(tab.load_split(split_file, annotator="quality_checked"))
    merged = next(tab.load_split(split_file, annotator="all"))
    assert len(first.mentions) == 3
    assert len(checked.mentions) == 1      # quality_checked prefers the second annotator here
    assert len(merged.mentions) == 4       # every annotator's spans, duplicates included


def test_type_filter(split_file):
    doc = next(tab.load_split(split_file, types=["PERSON"]))
    assert {m.type for m in doc.mentions} == {"PERSON"}


def test_identifier_class_is_carried_as_an_attribute(split_file):
    doc = next(tab.load_split(split_file))
    assert doc.mentions[2].attributes["identifier_type"] == "QUASI"


def test_provenance_and_domain_are_recorded(split_file):
    doc = next(tab.load_split(split_file))
    assert (doc.corpus, doc.domain, doc.provenance) == ("tab", "legal", "real")
