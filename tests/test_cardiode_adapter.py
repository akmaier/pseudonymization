"""CARDIO:DE adapter — CAS parsing, offset alignment, the date-marker gold layer.

No CARDIO:DE text appears here.  The fixtures are synthetic and reproduce only the *structure* of
the release, which is what the adapter has to get right; the corpus itself is DUA-restricted to
Andreas Maier alone and may not enter a shared artefact.
"""

from __future__ import annotations

import xml.sax.saxutils as saxutils
import zipfile

import pytest

from pseudonymkit.adapters import cardiode

XMI_TEMPLATE = """<?xml version="1.1" encoding="UTF-8"?>
<xmi:XMI xmlns:xmi="http://www.omg.org/XMI"
         xmlns:cas="http:///uima/cas.ecore"
         xmlns:custom="http:///webanno/custom.ecore" xmi:version="2.0">
  <cas:NULL xmi:id="0"/>
  <custom:Medication xmi:id="10" sofa="1" begin="19" end="29" ClassType="ACTIVEING"
                     InNarrative="true" Suggested="false"/>
  <custom:Medication xmi:id="11" sofa="1" begin="30" end="34" ClassType="STRENGTH"
                     InNarrative="false" Suggested="false"/>
  <custom:Sectionsentence xmi:id="20" sofa="1" begin="0" end="18" Sectiontypes="Anrede"/>
  <custom:MedRel xmi:id="30" sofa="1" begin="19" end="34" Dependent="11" Governor="10"/>
  <cas:Sofa xmi:id="1" sofaNum="1" sofaID="_InitialView" mimeType="text"
            sofaString="{text}"/>
  <cas:View sofa="1" members="10 11 20 30"/>
</xmi:XMI>
"""

# The offsets in XMI_TEMPLATE are the real indices into PLAIN, counted below, not guessed.
PLAIN = "Sehr geehrte Frau,\nBisoprolol 5 mg am <[Pseudo] 01/02/2020>."


def write_letter(root, split, stem, plain=PLAIN, sofa=None):
    """Write one letter in the release's shape: a .txt plus a zipped cas.xmi."""
    (root / "txt" / split).mkdir(parents=True, exist_ok=True)
    (root / "cas" / split).mkdir(parents=True, exist_ok=True)
    (root / "txt" / split / f"{stem}.txt").write_text(plain, encoding="utf-8")
    # The release writes literal newlines into the attribute; a conformant parser normalises them
    # to spaces, which is exactly the mismatch the adapter has to tolerate.
    # The release escapes the text into the attribute; the '<' of a <[Pseudo]> marker must be
    # '&lt;' or the file is not well-formed XML.  Newlines stay literal, as the release writes
    # them, so the parser normalises them to spaces — the mismatch the adapter tolerates.
    body = XMI_TEMPLATE.format(text=saxutils.escape(sofa if sofa is not None else plain).replace('"', '&quot;'))
    with zipfile.ZipFile(root / "cas" / split / f"{stem}.zip", "w") as zf:
        zf.writestr("cas.xmi", body)
        zf.writestr("TypeSystem.xml", "<typeSystemDescription/>")


def test_parse_cas_reads_all_three_layers(tmp_path):
    write_letter(tmp_path, "CARDIODE400_main", "1")
    annotations = cardiode.load_cas(tmp_path / "cas" / "CARDIODE400_main" / "1.zip")

    assert [m.class_type for m in annotations.medications] == ["ACTIVEING", "STRENGTH"]
    assert annotations.medications[0].text == "Bisoprolol"
    assert annotations.medications[0].in_narrative is True
    assert annotations.medications[1].in_narrative is False
    assert [s.section_type for s in annotations.sections] == ["Anrede"]
    assert annotations.relations[0].governor == "10"
    assert annotations.relations[0].dependent == "11"


def test_cas_offsets_are_applied_to_the_txt_which_keeps_its_newlines(tmp_path):
    write_letter(tmp_path, "CARDIODE400_main", "1")
    corpus = cardiode.load(tmp_path)
    document = corpus.documents[0]

    # The document text is the .txt — the newline survives, which the section task depends on.
    assert "\n" in document.text
    medications = document.task["medications"]
    assert document.text[medications[0].start : medications[0].end] == "Bisoprolol"
    assert document.text[medications[1].start : medications[1].end] == "5 mg"


def test_a_letter_whose_cas_does_not_align_is_dropped_and_counted(tmp_path):
    write_letter(tmp_path, "CARDIODE400_main", "1")
    write_letter(tmp_path, "CARDIODE400_main", "2", sofa="a completely different string")
    report: dict[str, cardiode.LoadReport] = {}
    corpus = cardiode.load(tmp_path, report=report)

    assert len(corpus) == 1  # never mis-annotated, and never silently
    assert report["CARDIODE400_main"].offset_mismatch == 1
    assert report["CARDIODE400_main"].annotated == 1


def test_whitespace_differences_alone_do_not_count_as_misalignment(tmp_path):
    # sofaString with the newline normalised to a space is the *normal* case, not a mismatch.
    write_letter(tmp_path, "CARDIODE400_main", "1", sofa=PLAIN.replace("\n", " "))
    report: dict[str, cardiode.LoadReport] = {}
    corpus = cardiode.load(tmp_path, report=report)
    assert len(corpus) == 1
    assert report["CARDIODE400_main"].offset_mismatch == 0


def test_pseudo_markers_become_datetime_gold(tmp_path):
    write_letter(tmp_path, "CARDIODE400_main", "1")
    document = cardiode.load(tmp_path).documents[0]

    assert [m.type for m in document.mentions] == ["DATETIME"]
    mention = document.mentions[0]
    assert mention.surface == "<[Pseudo] 01/02/2020>"
    assert document.text[mention.span.start : mention.span.end] == mention.surface
    assert mention.span.type_src == "Pseudo"


def test_a_letter_without_a_cas_still_loads_as_text(tmp_path):
    (tmp_path / "txt" / "CARDIODE100_heldout").mkdir(parents=True)
    (tmp_path / "txt" / "CARDIODE100_heldout" / "9.txt").write_text(PLAIN, encoding="utf-8")
    report: dict[str, cardiode.LoadReport] = {}
    corpus = cardiode.load(tmp_path, splits=("CARDIODE100_heldout",), report=report)

    assert len(corpus) == 1
    assert corpus.documents[0].metadata["annotation"] == "none"
    assert report["CARDIODE100_heldout"].cas_missing == 1
    # The date layer does not depend on the CAS, so the heldout split still carries gold DATETIME.
    assert len(corpus.documents[0].mentions) == 1


def test_the_default_split_is_the_annotated_one(tmp_path):
    write_letter(tmp_path, "CARDIODE400_main", "1")
    write_letter(tmp_path, "CARDIODE100_heldout", "2")
    corpus = cardiode.load(tmp_path)
    assert [d.metadata["split"] for d in corpus.documents] == ["CARDIODE400_main"]


def test_documents_are_marked_restricted(tmp_path):
    write_letter(tmp_path, "CARDIODE400_main", "1")
    document = cardiode.load(tmp_path).documents[0]
    assert document.metadata["restricted"] == "dua:cardiode:AM-only"
    assert document.language == "de"
    assert document.corpus == "cardiode"


def test_numeric_ordering_makes_a_prefix_limit_reproducible(tmp_path):
    for stem in ("1", "2", "10", "100"):
        write_letter(tmp_path, "CARDIODE400_main", stem)
    corpus = cardiode.load(tmp_path, limit=3)
    assert [d.doc_id.rsplit("/", 1)[-1] for d in corpus.documents] == ["1", "2", "10"]


def test_utf16_offsets_are_converted_outside_the_bmp():
    # UIMA counts UTF-16 code units; an astral character costs two, Python's index costs one.
    text = "\U0001F600 Bisoprolol"
    convert = cardiode._offset_map(text)
    assert convert(0) == 0
    assert convert(3) == 2  # after the emoji (2 units) and the space, "B" is at index 2
    assert text[convert(3)] == "B"
    # BMP-only text needs no conversion at all.
    assert cardiode._offset_map("Bisoprolol")(4) == 4


@pytest.mark.parametrize("marker", ["<[Pseudo] 01/02/2020>", "<[Pseudo] 2020>", "<[Pseudo] 01/02>"])
def test_every_observed_marker_shape_is_recognised(tmp_path, marker):
    write_letter(tmp_path, "CARDIODE400_main", "1", plain=f"Termin am {marker}.")
    document = cardiode.load(tmp_path).documents[0]
    assert [m.surface for m in document.mentions] == [marker]
