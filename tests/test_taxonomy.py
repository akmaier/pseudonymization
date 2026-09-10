"""The harmonised taxonomy (experiment_plan.md §10).

The tests assert the *semantics* the plan states, not merely that a lookup happens: that every label
set §10 names routes into TAB's eight, that the source label survives, that a label with no route
becomes MISC **and is counted**, and that a label the table sends to MISC on purpose is not counted
as an invention.
"""

from __future__ import annotations

import pytest

from pseudonymkit.domain import Document, Mention, Span
from pseudonymkit.taxonomy import (
    HARMONISED,
    SOURCES,
    Harmoniser,
    TaxonomyMap,
    harmonise,
    harmonise_spans,
    normalise_label,
    source_for,
)


def test_harmonised_set_is_tabs_eight():
    assert HARMONISED == (
        "PERSON", "LOC", "ORG", "DATETIME", "CODE", "DEMOGRAPHIC", "QUANTITY", "MISC",
    )


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_every_table_lands_inside_the_eight(source):
    for target in SOURCES[source].values():
        assert target in HARMONISED, f"{source} routes to {target!r}, which is not one of the eight"


# ----------------------------------------------------------------------------- the §10 label sets


@pytest.mark.parametrize(
    "label,expected",
    [
        # OntoNotes' 18 NE types, exactly as §10 routes them.
        ("PERSON", "PERSON"), ("GPE", "LOC"), ("LOC", "LOC"), ("FAC", "LOC"), ("ORG", "ORG"),
        ("DATE", "DATETIME"), ("TIME", "DATETIME"), ("NORP", "DEMOGRAPHIC"),
        ("MONEY", "QUANTITY"), ("PERCENT", "QUANTITY"), ("QUANTITY", "QUANTITY"),
        ("CARDINAL", "QUANTITY"), ("ORDINAL", "QUANTITY"),
        ("PRODUCT", "MISC"), ("EVENT", "MISC"), ("WORK_OF_ART", "MISC"), ("LAW", "MISC"),
        ("LANGUAGE", "MISC"),
    ],
)
def test_ontonotes_eighteen(label, expected):
    assert harmonise(label, "ontonotes") == (expected, True)


def test_ontonotes_covers_all_eighteen():
    """The 18 are enumerated, so a missing one would show up as an unmapped count in a real run."""
    assert len(SOURCES["ontonotes"]) == 18


@pytest.mark.parametrize(
    "label,expected",
    [("PERSON", "PERSON"), ("LOC", "LOC"), ("ORG", "ORG"), ("DATETIME", "DATETIME"),
     ("EMAIL", "CODE"), ("PHONE", "CODE"), ("ID", "CODE"), ("PROFESSION", "DEMOGRAPHIC")],
)
def test_llm_prompt_eight(label, expected):
    assert harmonise(label, "llm") == (expected, True)


def test_llm_prompt_labels_match_the_prompt_module():
    """The table must cover exactly the types the prompt asks for, or a run silently loses a class."""
    from pseudonymkit.detectors.prompting import DEFAULT_TYPES

    assert set(SOURCES["llm"]) == {normalise_label(t) for t in DEFAULT_TYPES}


@pytest.mark.parametrize(
    "label,expected",
    [("FEMALE", "PERSON"), ("MALE", "PERSON"), ("FAMILY", "PERSON"), ("ORG", "ORG"),
     ("USER", "CODE"), ("DATE", "DATETIME"), ("STREET", "LOC"), ("STREETNO", "LOC"),
     ("CITY", "LOC"), ("ZIP", "LOC"), ("PASS", "CODE"), ("UFID", "CODE"), ("EMAIL", "CODE"),
     ("URL", "CODE"), ("PHONE", "CODE")],
)
def test_privacy_tagger_fifteen(label, expected):
    assert harmonise(label, "privacy_tagger") == (expected, True)


def test_privacy_tagger_has_fifteen_labels():
    assert len(SOURCES["privacy_tagger"]) == 15


@pytest.mark.parametrize(
    "label,expected",
    [("AGE", "DEMOGRAPHIC"), ("DATE", "DATETIME"), ("EMAIL", "CODE"), ("HOSP", "ORG"),
     ("ID", "CODE"), ("LOC", "LOC"), ("OTHERPHI", "MISC"), ("PATIENT", "PERSON"),
     ("PATORG", "ORG"), ("PHONE", "CODE"), ("STAFF", "PERSON")],
)
def test_obi_deid_eleven(label, expected):
    assert harmonise(label, "obi/deid_roberta_i2b2") == (expected, True)


def test_obi_deid_has_eleven_labels():
    assert len(SOURCES["obi/deid_roberta_i2b2"]) == 11


@pytest.mark.parametrize(
    "label,expected",
    [("DATE", "DATETIME"), ("HCW", "PERSON"), ("HOSPITAL", "ORG"), ("ID", "CODE"),
     ("PATIENT", "PERSON"), ("PHONE", "CODE"), ("VENDOR", "ORG")],
)
def test_stanford_deidentifier_seven(label, expected):
    assert harmonise(label, "StanfordAIMI/stanford-deidentifier-base") == (expected, True)


def test_stanford_deidentifier_has_seven_labels():
    assert len(SOURCES["StanfordAIMI/stanford-deidentifier-base"]) == 7


@pytest.mark.parametrize(
    "label,expected",
    [("DATE", "DATETIME"), ("LOC", "LOC"), ("ORG", "ORG"), ("PER", "PERSON")],
)
def test_xlm_roberta_four(label, expected):
    assert harmonise(label, "Davlan/xlm-roberta-large-ner-hrl") == (expected, True)


def test_xlm_roberta_has_four_labels():
    assert len(SOURCES["Davlan/xlm-roberta-large-ner-hrl"]) == 4


def test_gliner_is_prompted_with_the_eight_directly():
    for name in HARMONISED:
        assert harmonise(name, "gliner") == (name, True)


def test_tab_gold_is_identity_and_knows_dem():
    assert harmonise("DEM", "tab") == ("DEMOGRAPHIC", True)
    for name in HARMONISED:
        assert harmonise(name, "tab")[0] == name


def test_enron_gold_has_person_and_email_only():
    assert harmonise("PERSON", "enron") == ("PERSON", True)
    assert harmonise("EMAIL", "enron") == ("CODE", True)


def test_cardiode_date_marker():
    assert harmonise("Pseudo", "cardiode") == ("DATETIME", True)


def test_presidio_structured_identifiers_go_to_code():
    for label in ("EMAIL_ADDRESS", "PHONE_NUMBER", "IBAN_CODE", "US_SSN", "UK_NHS"):
        assert harmonise(label, "presidio") == ("CODE", True)
    assert harmonise("NRP", "presidio") == ("DEMOGRAPHIC", True)
    assert harmonise("LOCATION", "presidio") == ("LOC", True)


# ------------------------------------------------------------------------- normalisation and BIO


@pytest.mark.parametrize(
    "raw,expected",
    [("B-PER", "PER"), ("I-LOC", "LOC"), ("E-ORG", "ORG"), ("S-PERSON", "PERSON"),
     ("date time", "DATE_TIME"), ("work-of-art", "WORK_OF_ART"), ("  person ", "PERSON")],
)
def test_normalise_label(raw, expected):
    assert normalise_label(raw) == expected


def test_bio_prefixed_output_still_routes():
    """A transformers pipeline without aggregation emits ``B-PER``; it must not become MISC."""
    assert harmonise("B-PER", "Davlan/xlm-roberta-large-ner-hrl") == ("PERSON", True)


# ------------------------------------------------------------------------------ unmapped counting


def test_unmapped_label_becomes_misc_and_is_counted():
    h = Harmoniser("llm")
    assert h.label("FILENAME") == "MISC"
    assert h.label("GENE") == "MISC"
    assert h.label("FILENAME") == "MISC"
    assert h.unmapped == {"FILENAME": 2, "GENE": 1}
    assert h.unmapped_spans == 3
    assert h.seen == 3
    assert h.unmapped_rate == 1.0


def test_a_deliberate_misc_route_is_not_an_invention():
    """``OTHERPHI`` is the model's own residual class: translated, not invented."""
    h = Harmoniser("obi/deid_roberta_i2b2")
    assert h.label("OTHERPHI") == "MISC"
    assert h.unmapped == {}


def test_report_carries_the_finding():
    h = Harmoniser("llm")
    for label in ("PERSON", "PERSON", "COPYRIGHT", "<[PSEUDO] 15/10/39>"):
        h.label(label)
    report = h.report()
    assert report["spans"] == 4
    assert report["routed"] == 2
    assert report["unmapped_spans"] == 2
    assert report["unmapped_labels"] == 2
    assert report["unmapped_rate"] == 0.5
    assert "COPYRIGHT" in report["unmapped"]


def test_merge_folds_two_passes_together():
    a, b = Harmoniser("llm"), Harmoniser("llm")
    a.label("FILENAME")
    b.label("FILENAME")
    b.label("PERSON")
    a.merge(b)
    assert a.seen == 3
    assert a.unmapped == {"FILENAME": 2}
    with pytest.raises(ValueError):
        a.merge(Harmoniser("gliner"))


# ------------------------------------------------------------------------------- spans and reuse


def _span(type_: str, type_src: str | None = None) -> Span:
    return Span(0, 4, "Kate", type_, type_src=type_src, source="d", score=0.75)


def test_span_keeps_the_source_label_and_the_detector_metadata():
    h = Harmoniser("Davlan/xlm-roberta-large-ner-hrl")
    out = h.span(_span("PER"))
    assert (out.type, out.type_src) == ("PERSON", "PER")
    assert (out.start, out.end, out.text, out.source, out.score) == (0, 4, "Kate", "d", 0.75)


def test_a_cached_record_with_no_type_src_is_read_through_type():
    """§12.2: the cache holds the model's raw string in ``type`` and nothing in ``type_src``."""
    h = Harmoniser("llm")
    assert h.span(_span("PROFESSION")).type == "DEMOGRAPHIC"


def test_harmonisation_is_idempotent():
    """A detector that already harmonised keeps its raw label, so a second pass changes nothing."""
    h = Harmoniser("privacy_tagger")
    once = h.span(_span("PERSON", type_src="FEMALE"))
    twice = Harmoniser("privacy_tagger").span(once)
    assert once == twice
    assert twice.type_src == "FEMALE"


def test_document_harmonisation_leaves_offsets_alone():
    text = "Kate lives in Bonn."
    document = Document(
        "d1", text, "en",
        (
            Mention("d1", "m0", Span(0, 4, "Kate", "PER")),
            Mention("d1", "m1", Span(14, 18, "Bonn", "LOC")),
        ),
    )
    out = Harmoniser("Davlan/xlm-roberta-large-ner-hrl").document(document)
    assert [m.type for m in out.mentions] == ["PERSON", "LOC"]
    assert [(m.span.start, m.span.end) for m in out.mentions] == [(0, 4), (14, 18)]
    assert out.text == text


# ------------------------------------------------------------------------- detector -> source map


@pytest.mark.parametrize(
    "detector,expected",
    [
        ("llm:gpt-oss-120b", "llm"),
        ("local:Qwen/Qwen3.6-35B-A3B-FP8", "llm"),
        ("gliner:urchade/gliner_multi_pii-v1", "gliner"),
        ("presidio", "presidio"),
        ("privacy_tagger", "privacy_tagger"),
        ("hf:obi/deid_roberta_i2b2", "obi/deid_roberta_i2b2"),
        ("hf:StanfordAIMI/stanford-deidentifier-base", "StanfordAIMI/stanford-deidentifier-base"),
    ],
)
def test_source_for_detector(detector, expected):
    assert source_for(detector) == expected


def test_gold_needs_the_corpus():
    assert source_for("gold", corpus="ontonotes") == "ontonotes"
    assert source_for("gold:tab") == "tab"
    with pytest.raises(KeyError):
        source_for("gold")


def test_taxonomy_map_is_a_value_object():
    table = TaxonomyMap.for_source("gliner")
    assert table.source == "gliner"
    assert table("PERSON") == ("PERSON", True)
    assert "PERSON" in table.labels


def test_harmonise_spans_returns_the_tally_with_the_spans():
    spans, harmoniser = harmonise_spans(
        (_span("PER"), _span("FILENAME")), "hf:Davlan/xlm-roberta-large-ner-hrl"
    )
    assert [s.type for s in spans] == ["PERSON", "MISC"]
    assert harmoniser.unmapped == {"FILENAME": 1}
