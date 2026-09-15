"""The CARDIO:DE condition-A fill.

No corpus text appears here — CARDIO:DE is DUA-restricted.  The fixtures below reproduce the *shapes*
measured over the 500 released letters: a two-token ``B-PER I-PER``, a bare ``B-PER``, a three-token
title, an orphan ``I-ADDR``, and an ``I-`` token that resumes after prose and must not swallow it.
"""

from __future__ import annotations

import pytest

from pseudonymkit.adapters.cardiode import MedicationSpan, SectionSpan
from pseudonymkit.adapters.cardiode_fill import (
    Inventories,
    fill_corpus,
    fill_document,
    find_runs,
)
from pseudonymkit.domain import Document, Mention, Span


@pytest.fixture
def inventories() -> Inventories:
    return Inventories(
        family=["Baumgartner", "Reinhardt", "Kühnel"],
        male=["Andreas", "Jonas", "Til"],
        female=["Franziska", "Miriam", "Siming"],
        city=["Ellwangen", "Bad Nauheim"],
        street=["Am Gründelgraben", "Ameisenstraße"],
    )


LETTER = (
    "Sehr geehrte Frau Kollegin,\n"
    "wir berichten über unsere Patientin B-SALUTE B-PER I-PER, wohnhaft in B-PLZ B-LOC, "
    "B-ADDR I-ADDR, aufgenommen am B-DATE.\n"
    "Die Vorstellung erfolgte über B-ORG I-ORG.\n"
    "Mit freundlichen Grüßen\n"
    "B-TITLE I-TITLE I-TITLE B-PER I-PER\n"
    "B-TITLE B-PER\n"
)


def test_runs_have_the_shapes_the_corpus_has(inventories):
    runs = find_runs(LETTER)
    shapes = [(r.type, r.tokens) for r in runs]
    assert shapes == [
        ("SALUTE", 1), ("PER", 2), ("PLZ", 1), ("LOC", 1), ("ADDR", 2), ("DATE", 1),
        ("ORG", 2), ("TITLE", 3), ("PER", 2), ("TITLE", 1), ("PER", 1),
    ]


def test_a_resuming_I_token_does_not_swallow_the_prose_between():
    """18 runs in the corpus have prose between an ``I-`` token and the one before it."""
    text = "B-ORG I-ORG Radfahren, Schwimmen, I-ORG"
    runs = find_runs(text)
    assert [(r.type, r.tokens) for r in runs] == [("ORG", 2), ("ORG", 1)]
    assert runs[0].text == "B-ORG I-ORG"
    assert "Radfahren" not in runs[0].text and "Radfahren" not in runs[1].text


def test_an_orphan_I_token_still_makes_a_run():
    """265 ADDR and 93 ORG runs in the corpus begin with ``I-`` and no ``B-``.

    The markup is not well formed there.  An orphan is kept rather than dropped, and adjacent
    ``I-`` tokens still join — ``I-ADDR I-ADDR`` is the tail of one address, not two.
    """
    assert [(r.type, r.tokens) for r in find_runs("wohnhaft in I-ADDR I-ADDR")] == [("ADDR", 2)]
    assert [(r.type, r.tokens) for r in find_runs("wohnhaft in I-ADDR")] == [("ADDR", 1)]


def test_a_token_inside_a_hyphenated_word_is_not_a_tag():
    """Without word boundaries this matches the ``B-EKG`` inside ``LSB-EKG``."""
    assert find_runs("Im LSB-EKG zeigte sich") == ()


def test_every_filled_span_lands_exactly_where_it_says(inventories):
    document = Document(doc_id="L1", text=LETTER, language="de", corpus="cardiode")
    filled, mapping = fill_document(document, inventories, seed=0)
    assert mapping
    for entity in mapping:
        assert filled.text[entity.start : entity.end] == entity.surface
    for mention in filled.mentions:
        assert filled.text[mention.span.start : mention.span.end] == mention.span.text


def test_no_markup_survives_the_fill(inventories):
    document = Document(doc_id="L1", text=LETTER, language="de", corpus="cardiode")
    filled, _ = fill_document(document, inventories, seed=0)
    assert find_runs(filled.text) == ()
    assert "B-" not in filled.text and "I-" not in filled.text


def test_the_patient_is_one_entity_and_the_signature_is_not(inventories):
    document = Document(doc_id="L1", text=LETTER, language="de", corpus="cardiode")
    _, mapping = fill_document(document, inventories, seed=0)
    people = [e for e in mapping if e.type == "PER"]
    assert [e.role for e in people] == ["patient", "signature", "signature"]
    assert people[0].entity_id == "L1:patient"
    assert people[1].entity_id != people[2].entity_id


def test_a_one_token_PER_run_gets_only_the_surname(inventories):
    """``B-PER`` stood for a surname, ``B-PER I-PER`` for a given name and a surname (1,442 / 1,880)."""
    document = Document(doc_id="L1", text=LETTER, language="de", corpus="cardiode")
    _, mapping = fill_document(document, inventories, seed=0)
    short = [e for e in mapping if e.type == "PER" and e.run.tokens == 1][0]
    long_ = [e for e in mapping if e.type == "PER" and e.run.tokens == 2][0]
    assert " " not in short.surface
    assert len(long_.surface.split()) == 2


def test_the_salutation_agrees_with_the_patient(inventories):
    document = Document(doc_id="L1", text=LETTER, language="de", corpus="cardiode")
    _, mapping = fill_document(document, inventories, seed=0)
    salute = [e for e in mapping if e.type == "SALUTE"][0]
    patient = [e for e in mapping if e.entity_id == "L1:patient"][0]
    assert salute.surface == ("Frau" if patient.surface.split()[0] in inventories.female else "Herr")


def test_the_annotation_layers_move_with_the_text(inventories):
    """The medication and section layers are the utility tasks; the fill must not break them."""
    marker = LETTER.index("Vorstellung")
    document = Document(
        doc_id="L1",
        text=LETTER,
        language="de",
        corpus="cardiode",
        task={
            "medications": (
                MedicationSpan(marker, marker + 11, "Vorstellung", "DRUG", True, False, "1"),
            ),
            "sections": (SectionSpan(0, 27, "Anrede", "2"),),
        },
    )
    filled, _ = fill_document(document, inventories, seed=0)
    medication = filled.task["medications"][0]
    assert filled.text[medication.start : medication.end] == "Vorstellung"
    assert medication.text == "Vorstellung"
    section = filled.task["sections"][0]
    assert filled.text[section.start : section.end].startswith("Sehr geehrte")


def test_a_pseudo_marker_is_unwrapped_to_a_german_date(inventories):
    """18,145 markers across the 500 letters. Condition A is a letter, not a marked-up letter."""
    text = "Aufnahmedatum: <[Pseudo] 2032-09-04 >\nGeburtsdatum: <[Pseudo] 04/12/1980>\nB-PER I-PER\n"
    document = Document(doc_id="L1", text=text, language="de", corpus="cardiode")
    filled, _ = fill_document(document, inventories, seed=0)
    assert "<[Pseudo]" not in filled.text and ">" not in filled.text
    dates = [m for m in filled.mentions if m.span.type == "DATETIME"]
    assert [m.span.text for m in dates] == ["04.09.2032", "04.12.1980"]
    for mention in dates:
        assert filled.text[mention.span.start : mention.span.end] == mention.span.text


def test_every_date_is_normalised_to_german_form():
    """The letters are German; the corpus's dates are not.

    Heidelberg emitted ISO (``2032-09-04``), US-style slash (``04/12/1980``) and two-digit-year
    slash (``04/09/32``) — all three in one document, sometimes in adjacent rows of one lab table.
    Normalising them is what makes condition A read as German *and* removes the surface cue that
    separated inserted dates from shipped ones.
    """
    from pseudonymkit.adapters.cardiode_fill import _german_date

    assert _german_date("2032-09-04") == "04.09.2032"
    assert _german_date("04/12/1980") == "04.12.1980"
    assert _german_date("4/9/32") == "04.09.2032"      # two-digit year reads against 2000
    assert _german_date("14.02.2032") == "14.02.2032"  # already German
    assert _german_date("09/2024") == "09/2024"        # a month, not a date — left alone
    assert _german_date("Oktober 2032") == "Oktober 2032"


def test_an_inserted_date_lands_in_the_letters_own_shifted_timeline(inventories):
    """A global 2004-2020 range put 2014 lab dates under a 2032 admission — separable by year alone."""
    text = ("Aufnahmedatum: <[Pseudo] 2032-09-04 >\nKontrolle <[Pseudo] 2033-01-11 >\n"
            "Befund vom B-DATE\n")
    filled, mapping = fill_document(
        Document(doc_id="L1", text=text, language="de", corpus="cardiode"), inventories, seed=3
    )
    inserted = [e for e in mapping if e.type == "DATE"][0]
    year = int(inserted.surface.rsplit(".", 1)[1])
    assert 2032 <= year <= 2033
    assert inserted.surface.count(".") == 2            # German form too


def test_the_fill_is_reproducible_from_the_seed_and_the_document_id(inventories):
    document = Document(doc_id="L1", text=LETTER, language="de", corpus="cardiode")
    first, _ = fill_document(document, inventories, seed=7)
    second, _ = fill_document(document, inventories, seed=7)
    third, _ = fill_document(document, inventories, seed=8)
    assert first.text == second.text
    assert first.text != third.text


def test_the_report_counts_what_was_filled(inventories):
    documents = [
        Document(doc_id=f"L{i}", text=LETTER, language="de", corpus="cardiode") for i in range(3)
    ]
    filled, mapping, report = fill_corpus(documents, inventories, seed=0)
    assert report.documents == 3
    assert report.runs == len(mapping) == 3 * 11
    assert report.by_type["PER"] == 9
    assert all(d.provenance == "inserted" for d in filled)


def test_an_empty_inventory_is_refused_rather_than_silently_reused():
    with pytest.raises(ValueError, match="family"):
        Inventories(family=[], male=["A"], female=["B"], city=["C"], street=["D"])


def test_the_patient_stays_one_person_through_the_body(inventories):
    """One letter had the same man as Marcel Bremert, then Frau Walers, Herr Schwamberger, Herr
    Ganslmaier, Herr Opden-oordt and Herr Örtl — six names across six sentences about one
    admission. A fresh person per uncued run is not a conservative over-count, it is an incoherent
    document, and a co-reference model reads six people where there is one."""
    text = ("über Ihren Patienten B-SALUTE B-PER I-PER geboren am B-DATE\n"
            "Anamnese:\nDie Vorstellung von B-PER erfolgt zur Kontrolle. B-PER berichtet stabil.\n"
            "Mit freundlichen Grüßen\nB-TITLE B-PER I-PER\n")
    _, mapping = fill_document(
        Document(doc_id="L1", text=text, language="de", corpus="cardiode"), inventories, seed=0
    )
    people = [e for e in mapping if e.type == "PER"]
    body = [e for e in people if e.role in ("patient", "patient_body")]
    signers = [e for e in people if e.role == "signature"]
    assert len(body) == 3                                   # header mention plus both body mentions
    assert len({e.entity_id for e in body}) == 1            # and all one person
    assert signers                                          # the signer is still someone else
    assert {e.entity_id for e in body}.isdisjoint({e.entity_id for e in signers})


def test_an_org_head_agrees_with_the_article_in_front_of_it(inventories):
    """`unsere Notfallambulanz` became `unsere Herzzentrum Oberdorfelden` — feminine article, neuter
    noun, and one more surface cue marking exactly the spans we inserted."""
    feminine = fill_document(
        Document(doc_id="L1", text="Vorstellung in unserer B-ORG I-ORG erfolgte.",
                 language="de", corpus="cardiode"), inventories, seed=0)[1][0]
    assert feminine.surface.lower().endswith(("klinik", "praxis")) or \
        feminine.surface.split()[0] in ("Kreisklinik", "Herzklinik", "Kardiologische", "Medizinische")
    neuter = fill_document(
        Document(doc_id="L2", text="Vorstellung im B-ORG I-ORG erfolgte.",
                 language="de", corpus="cardiode"), inventories, seed=0)[1][0]
    assert not neuter.surface.lower().endswith(("klinik", "praxis"))


def test_a_none_marker_is_blanked_not_filled_with_an_invented_value(inventories):
    """178 of them mark a value the de-identifier removed. Inventing one would be fabricated
    clinical data; a blank field is what a missing measurement looks like."""
    filled, _ = fill_document(
        Document(doc_id="L1", text="CK <NONE> !H\nLDH 254 U/l\n", language="de",
                 corpus="cardiode"), inventories, seed=0)
    assert "<NONE>" not in filled.text and "NONE" not in filled.text
    assert "CK" in filled.text and "!H" in filled.text and "254" in filled.text


def test_penn_treebank_brackets_are_unescaped(inventories):
    """Not one literal parenthesis survives in the 5.9 M characters the corpus ships: every bracket
    is escaped as -LRB-/-RRB-, and no clinician writes that."""
    filled, _ = fill_document(
        Document(doc_id="L1", text="LV Funktion -LRB- EF 25% -RRB- stabil\n", language="de",
                 corpus="cardiode"), inventories, seed=0)
    assert filled.text.startswith("LV Funktion ( EF 25% ) stabil")
    assert "-LRB-" not in filled.text and "-RRB-" not in filled.text


def test_unk_is_flattened_to_a_hyphen(inventories):
    """AM, 2026-09-13. 4,801 of the 5,554 start a line where a sub-bullet stood, and `-` is what the
    letters already use for a bullet. The ~700 in-line cases lose information the hyphen cannot
    carry — `Ramipril 5 mg 1 -UNK- -0-0` is a dosing schedule — which is a stated cost, not a fix."""
    filled, _ = fill_document(
        Document(doc_id="L1", text="-UNK- Initial eingeschränkt\nRamipril 1 -UNK- -0-0\n",
                 language="de", corpus="cardiode"), inventories, seed=0)
    assert "-UNK-" not in filled.text
    assert filled.text.startswith("- Initial eingeschränkt")


def test_a_tag_word_without_its_prefix_is_still_filled(inventories):
    """325 of these: `vom DATE`, `unserer ORG`, `Telefon: PHONE`, `SALUTE PER`."""
    filled, mapping = fill_document(
        Document(doc_id="L1", text="Befund vom DATE aus unserer ORG, Telefon: PHONE\n",
                 language="de", corpus="cardiode"), inventories, seed=0)
    assert {e.type for e in mapping} == {"DATE", "ORG", "PHONE"}
    for word in ("DATE", "ORG", "PHONE"):
        assert word not in filled.text


def test_a_roman_numeral_is_not_mistaken_for_a_tag(inventories):
    """`II` appears 438 times unprefixed and is nearly always GOLD II / AV-Block II / NYHA II."""
    text = "COPD GOLD II mit AV-Block II Grad\n"
    filled, mapping = fill_document(
        Document(doc_id="L1", text=text, language="de", corpus="cardiode"), inventories, seed=0)
    assert filled.text == text and not mapping


# --- the formal "Sie" is not evidence about the patient ------------------------------------------
# A discharge letter is written *to* the referring physician, so "wie Sie dem Befund entnehmen"
# addresses the reader, not the patient.  Matched case-insensitively, that pronoun made 11 of the 400
# letters female whose own text calls the patient *der Patient* (measured 2026-09-14); every one of
# the 11 carried the masculine noun and none were ambiguous.

_MALE_LETTER_ADDRESSED_FORMALLY = (
    "Sehr geehrter Herr Kollege,\n"
    "wir berichten über unseren Patienten B-SALUTE B-PER I-PER.\n"
    "Wie Sie dem beiliegenden Befund entnehmen können, war der Patient beschwerdefrei.\n"
    "Mit freundlichen Grüßen\n"
    "B-TITLE B-PER\n"
)


def _patient_of(text: str, inventories, doc_id: str = "L1"):
    document = Document(doc_id=doc_id, text=text, language="de", corpus="cardiode")
    _, mapping = fill_document(document, inventories, seed=0)
    return [e for e in mapping if e.entity_id == f"{doc_id}:patient"][0]


def test_a_formally_addressed_male_patient_does_not_become_female(inventories):
    patient = _patient_of(_MALE_LETTER_ADDRESSED_FORMALLY, inventories)
    assert patient.surface.split()[0] in inventories.male, patient.surface


def test_the_salutation_follows_that_patient_too(inventories):
    document = Document(doc_id="L1", text=_MALE_LETTER_ADDRESSED_FORMALLY,
                        language="de", corpus="cardiode")
    _, mapping = fill_document(document, inventories, seed=0)
    assert [e for e in mapping if e.type == "SALUTE"][0].surface == "Herr"


def test_the_lower_case_pronoun_still_marks_a_female_patient(inventories):
    text = _MALE_LETTER_ADDRESSED_FORMALLY.replace(
        "war der Patient beschwerdefrei", "war sie beschwerdefrei")
    assert _patient_of(text, inventories).surface.split()[0] in inventories.female


def test_patientin_marks_a_female_patient_wherever_it_is_capitalised(inventories):
    for variant in ("unsere Patientin", "Patientin", "PATIENTIN"):
        text = _MALE_LETTER_ADDRESSED_FORMALLY.replace("unseren Patienten", variant)
        assert _patient_of(text, inventories).surface.split()[0] in inventories.female, variant


def test_only_real_date_markers_become_datetime_gold(inventories):
    """A restored bracket is not an identifier.

    ``is_date`` was built from ``dates + blanks + unescaped + flattened``, so every PTB bracket
    restored to "(", every ``-UNK-`` flattened to "-" and every ``<NONE>`` blanked to " " was
    emitted as a DATETIME gold mention. On the 400 letters that was 23,818 single-character gold
    spans — 43.2 % of the whole layer (measured 2026-09-15).
    """
    text = ("Befund -LRB- normal -RRB- vom <[Pseudo] 16.01.2013>, Wert <none>, Rest -UNK-.\n")
    document = Document(doc_id="L9", text=text, language="de", corpus="cardiode")
    filled, _ = fill_document(document, inventories, seed=0)
    datetimes = [m for m in filled.mentions if m.type == "DATETIME"]
    assert len(datetimes) == 1, [m.span.text for m in datetimes]
    assert datetimes[0].span.text == "16.01.2013"
    # and the substitutions still happened in the text
    assert "(" in filled.text and ")" in filled.text and "-LRB-" not in filled.text
    assert "<none>" not in filled.text.lower() and "-UNK-" not in filled.text


def test_no_gold_mention_is_a_single_punctuation_character(inventories):
    document = Document(doc_id="L9", text=LETTER, language="de", corpus="cardiode")
    filled, _ = fill_document(document, inventories, seed=0)
    bad = [m for m in filled.mentions
           if m.span.end - m.span.start == 1 and not m.span.text.isalnum()]
    assert not bad, [m.span.text for m in bad]


def test_the_same_institution_is_one_entity_across_letters(inventories):
    """AM, 2026-09-15: the fill draws institutions from a small template pool on purpose, so the
    same hospital appears in many letters. That recurrence is the cross-document identity A3 and A5
    need, and a per-document id threw it away — one institution carried 138 ids over 98 letters."""
    a = Document(doc_id="L1", text=LETTER, language="de", corpus="cardiode")
    b = Document(doc_id="L2", text=LETTER, language="de", corpus="cardiode")
    fa, _ = fill_document(a, inventories, seed=0)
    fb, _ = fill_document(b, inventories, seed=0)
    orgs_a = {m.span.text: m.gold_entity_id for m in fa.mentions if m.type == "ORG"}
    orgs_b = {m.span.text: m.gold_entity_id for m in fb.mentions if m.type == "ORG"}
    shared = set(orgs_a) & set(orgs_b)
    assert shared, "the fixture should produce at least one ORG"
    for surface in shared:
        assert orgs_a[surface] == orgs_b[surface], surface
        assert "L1" not in orgs_a[surface] and "L2" not in orgs_a[surface]


def test_two_patients_with_the_same_name_stay_two_entities(inventories):
    """A name collision is a §8.2 collision defect, not an identity. Merging PERSON on surface would
    define that defect out of existence."""
    a = Document(doc_id="L1", text=LETTER, language="de", corpus="cardiode")
    b = Document(doc_id="L2", text=LETTER, language="de", corpus="cardiode")
    fa, _ = fill_document(a, inventories, seed=0)
    fb, _ = fill_document(b, inventories, seed=0)
    ids_a = {m.gold_entity_id for m in fa.mentions if m.type == "PERSON"}
    ids_b = {m.gold_entity_id for m in fb.mentions if m.type == "PERSON"}
    assert not (ids_a & ids_b), "person identity must stay letter-scoped"
