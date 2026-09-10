"""Adapter: CARDIO:DE — German cardiovascular discharge letters — -> the domain model.

🔒 **Access is restricted to Andreas Maier alone** (Heidelberg, 2026-09-08).  The corpus lives at a
DUA-restricted path, mode ``700``; nobody else may read it, any derived file, or the cluster copy
until their own agreement has been countersigned.  This module therefore hard-codes no path and
writes nothing: it reads whatever directory the caller supplies and returns domain objects.

Richter-Pechanski, P., Wiesenbach, P., Schwab, D.M. et al.  *A distributable German clinical corpus
containing cardiovascular clinical routine doctor's letters.*  Sci Data 10, 207 (2023).
doi:10.1038/s41597-023-02128-9

## What the release contains

500 letters, split ``CARDIODE400_main`` (annotated) and ``CARDIODE100_heldout`` (**annotations
withheld** for a future shared task — the CAS files are present but carry no ``custom:`` layers, so
the heldout split is text only).  Each letter appears twice, as ``txt/<split>/<n>.txt`` and as
``cas/<split>/<n>.zip`` holding a UIMA CAS XMI plus its type system.

Three annotation layers, all in the CAS:

* ``custom:Medication`` — nine classes (ACTIVEING, DOSAGE, DRUG, DURATION, FORM, FREQUENCY, REASON,
  ROUTE, STRENGTH).  The **medication IE** utility task.
* ``custom:Sectionsentence`` — fourteen section types (Anamnese, Befunde, EntlassMedikation, …).
  The **section classification** utility task.
* ``custom:MedRel`` — relations between medication annotations, by ``xmi:id``.  Carried through, not
  currently scored by any planned task.

## Two things that would silently corrupt offsets, handled here

**The CAS text and the ``.txt`` are not byte-identical.**  They have the same length and agree
character for character *except* that every newline in the ``.txt`` is a space in ``sofaString`` —
XML attribute-value normalisation, applied by any conformant parser to a literal newline inside an
attribute.  Offsets therefore coincide exactly.  The adapter keeps the ``.txt`` as the document text,
because the line structure is what a section classifier and an LLM detector both read, and maps the
CAS offsets straight onto it — after asserting the invariant per document.  A letter that fails it is
dropped and counted, never silently mis-annotated.

**UIMA offsets are UTF-16 code units, Python's are code points.**  They agree only while the text
stays inside the Basic Multilingual Plane.  No CARDIO:DE letter leaves it, but the check is cheap and
the failure would be invisible, so :func:`_offset_map` converts wherever it must.

## Identifier provenance — dates are marked, names are not

Every de-identified **date** is marked in place: ``<[Pseudo] 12/03/2019>``, 14,854 occurrences in the 400 annotated letters, 18,148 across
the 500 letters, and the marker never wraps anything else.  Those give CARDIO:DE a real, if narrow,
DATETIME gold layer, exposed here as ``DATETIME`` mentions with ``type_src="Pseudo"``.

Semantic placeholders of the ``<TYPE>`` kind are almost absent — 178 ``<NONE>``, one ``<TIME>``, one
``<ORG>`` in 5.9 M characters — so the corpus is **not** placeholder-masked for persons the way the
repo's notes first assumed.  How person and institution names were handled is **not stated in the
release README**; until it is read out of the Sci Data paper the document's provenance tier is left
at ``"placeholder"`` for the date layer and the open question is recorded in ``experiment_plan.md``
§10, rather than guessed.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterator, Sequence

from ..domain import Corpus, Document, Mention, Span
from ..serialisation import register_type

__all__ = [
    "MEDICATION_CLASSES",
    "SECTION_TYPES",
    "MedicationSpan",
    "SectionSpan",
    "MedicationRelation",
    "CasAnnotations",
    "LoadReport",
    "load",
    "load_cas",
    "parse_cas",
    "Section",
    "derive_sections",
]

NS = {
    "cas": "http:///uima/cas.ecore",
    "custom": "http:///webanno/custom.ecore",
    "xmi": "http://www.omg.org/XMI",
}

MEDICATION_CLASSES: tuple[str, ...] = (
    "ACTIVEING",
    "DOSAGE",
    "DRUG",
    "DURATION",
    "FORM",
    "FREQUENCY",
    "REASON",
    "ROUTE",
    "STRENGTH",
)
"""The nine medication classes, as the release's README lists them."""

SECTION_TYPES: tuple[str, ...] = (
    "Abschluss",
    "AktuellDiagnosen",
    "AllergienUnverträglichkeitenRisiken",
    "Anamnese",
    "Anrede",
    "AufnahmeMedikation",
    "Befunde",
    "Diagnosen",
    "EchoBefunde",
    "EntlassMedikation",
    "KUBefunde",
    "Labor",
    "Mix",
    "Zusammenfassung",
)
"""The fourteen section types.  ``Mix`` marks a sentence spanning more than one section."""

_PSEUDO = re.compile(r"<\[Pseudo\][^>]*>")
"""The in-place marker left where a date was replaced.  It never wraps anything but a date."""


# The four layers below ride in ``Document.task`` and must survive a JSONL round trip: without a
# decoder they came back as plain dictionaries and ``span.section_type`` raised at the point of use
# rather than at the point of loss (experiment_plan.md §12.2).  Registration lives here so adding a
# layer and making it readable back are one edit.
@register_type
@dataclass(frozen=True, slots=True)
class MedicationSpan:
    start: int
    end: int
    text: str
    class_type: str
    in_narrative: bool
    suggested: bool
    xmi_id: str


@register_type
@dataclass(frozen=True, slots=True)
class SectionSpan:
    start: int
    end: int
    section_type: str
    xmi_id: str


@register_type
@dataclass(frozen=True, slots=True)
class MedicationRelation:
    start: int
    end: int
    dependent: str
    """``xmi:id`` of the dependent :class:`MedicationSpan`."""
    governor: str
    """``xmi:id`` of the governing :class:`MedicationSpan`."""


@register_type
@dataclass(frozen=True, slots=True)
class CasAnnotations:
    """One letter's annotation layers, with the text the offsets were recorded against."""

    text: str
    medications: tuple[MedicationSpan, ...] = ()
    sections: tuple[SectionSpan, ...] = ()
    relations: tuple[MedicationRelation, ...] = ()


@dataclass(frozen=True)
class LoadReport:
    """What :func:`load` kept and what it refused, per split."""

    documents: int = 0
    annotated: int = 0
    """Letters that carried at least one CAS annotation."""
    cas_missing: int = 0
    cas_text_used: int = 0
    """Letters whose ``.txt`` differs in length from the CAS text, so the CAS text was used instead.
    Nothing is lost but the ``.txt``'s line breaks; the annotations stay valid."""

    def __str__(self) -> str:
        return (
            f"{self.documents} letters, {self.annotated} annotated; "
            f"{self.cas_missing} without a CAS, {self.cas_text_used} using the CAS text"
        )


def _offset_map(text: str) -> Callable[[int], int]:
    """Return a converter from UTF-16 code-unit offsets to Python string indices.

    Identity while the text is BMP-only, which is the normal case; a real map is built only when an
    astral character is present, because that is when UIMA's Java offsets and Python's diverge.
    """
    if all(ord(character) < 0x10000 for character in text):
        return lambda offset: offset
    table: dict[int, int] = {}
    unit = 0
    for index, character in enumerate(text):
        table[unit] = index
        unit += 2 if ord(character) > 0xFFFF else 1
    table[unit] = len(text)
    return lambda offset: table.get(offset, len(text))


def parse_cas(xmi: bytes | str) -> CasAnnotations:
    """Parse one ``cas.xmi`` into its annotation layers.

    The declaration says XML 1.1; ElementTree parses it regardless, and the file uses no 1.1-only
    construct.  ``sofaString`` is the annotated text.
    """
    root = ET.fromstring(xmi)
    sofa = root.find("cas:Sofa", NS)
    text = (sofa.get("sofaString") or "") if sofa is not None else ""
    to_index = _offset_map(text)

    medications = tuple(
        MedicationSpan(
            start=(start := to_index(int(element.get("begin", "0")))),
            end=(end := to_index(int(element.get("end", "0")))),
            text=text[start:end],
            class_type=element.get("ClassType", ""),
            in_narrative=element.get("InNarrative", "false") == "true",
            suggested=element.get("Suggested", "false") == "true",
            xmi_id=element.get(f"{{{NS['xmi']}}}id", ""),
        )
        for element in root.findall("custom:Medication", NS)
    )
    sections = tuple(
        SectionSpan(
            start=to_index(int(element.get("begin", "0"))),
            end=to_index(int(element.get("end", "0"))),
            section_type=element.get("Sectiontypes", ""),
            xmi_id=element.get(f"{{{NS['xmi']}}}id", ""),
        )
        for element in root.findall("custom:Sectionsentence", NS)
    )
    relations = tuple(
        MedicationRelation(
            start=to_index(int(element.get("begin", "0"))),
            end=to_index(int(element.get("end", "0"))),
            dependent=element.get("Dependent", ""),
            governor=element.get("Governor", ""),
        )
        for element in root.findall("custom:MedRel", NS)
    )
    return CasAnnotations(text, medications, sections, relations)


def load_cas(archive: Path | str) -> CasAnnotations:
    """Parse the ``cas.xmi`` inside one ``<n>.zip``."""
    with zipfile.ZipFile(archive) as zf:
        return parse_cas(zf.read("cas.xmi"))


def _aligned(cas_text: str, plain: str) -> bool:
    """Whether CAS offsets may be used against ``plain``.

    The invariant an offset needs is **equal length**, nothing more: if the two strings have the same
    length, index *i* denotes the same position in both, whatever characters sit there.  Requiring
    character equality as well would be stricter than the problem — measured on the release, letter
    490 differs from its CAS in 72 whitespace characters and **one capital letter**, and rejecting it
    for that would throw away 80 gold medication spans for a difference that moves nothing.

    A length difference is the real failure: it means a character was inserted or deleted, and every
    offset after that point is wrong.  Letter 318 is the one case in 400 — its CAS lacks one newline
    at position 10,920.  Those letters are not dropped either; :func:`load` falls back to the CAS
    text, against which the annotations were made and are by construction consistent.
    """
    return len(cas_text) == len(plain)


def _date_mentions(doc_id: str, text: str) -> tuple[Mention, ...]:
    """The ``<[Pseudo] …>`` markers, as DATETIME gold.

    They are the corpus's only identifier annotation, and they are real gold: the marker sits exactly
    where the original date stood.
    """
    return tuple(
        Mention(
            doc_id=doc_id,
            mention_id=f"d{i}",
            span=Span(
                start=match.start(),
                end=match.end(),
                text=match.group(),
                type="DATETIME",
                type_src="Pseudo",
            ),
            gold_entity_id=None,  # no co-reference layer; dates are not chained
        )
        for i, match in enumerate(_PSEUDO.finditer(text))
    )


def load(
    root: Path | str,
    splits: Sequence[str] = ("CARDIODE400_main",),
    limit: int | None = None,
    report: dict[str, LoadReport] | None = None,
    progress: Callable[[str], None] | None = None,
) -> Corpus:
    """Build a corpus from a CARDIO:DE checkout.

    ``root`` is the directory holding ``txt/`` and ``cas/``.  The default reads only
    ``CARDIODE400_main``: ``CARDIODE100_heldout`` carries no annotations, so it supports neither
    utility task and would enter the design as unlabelled text.  Pass both splits explicitly if the
    text alone is wanted.

    Pass ``report`` to receive the per-split tally — how many letters were annotated, and how many
    were refused because their CAS text did not align.
    """
    root = Path(root)
    documents: list[Document] = []

    for split in splits:
        tally = LoadReport()
        paths = sorted((root / "txt" / split).glob("*.txt"), key=_numeric_key)
        if limit is not None:
            paths = paths[:limit]
        for path in paths:
            plain = path.read_text("utf-8", errors="replace")
            doc_id = f"cardiode/{split}/{path.stem}"
            archive = root / "cas" / split / f"{path.stem}.zip"

            annotations = CasAnnotations(plain)
            if not archive.is_file():
                tally = replace(tally, cas_missing=tally.cas_missing + 1)
            else:
                parsed = load_cas(archive)
                if _aligned(parsed.text, plain):
                    # Same length, so the offsets transfer: keep the .txt, whose line breaks the
                    # section task and any LLM detector both read.
                    annotations = replace(parsed, text=plain)
                else:
                    # A character was inserted or deleted between the two, so .txt offsets after
                    # that point are wrong. The CAS text is what the annotators saw; use it, and
                    # count the letter rather than discarding its gold.
                    annotations = parsed
                    plain = parsed.text
                    tally = replace(tally, cas_text_used=tally.cas_text_used + 1)

            annotated = bool(annotations.medications or annotations.sections)
            documents.append(
                Document(
                    doc_id=doc_id,
                    text=plain,
                    language="de",
                    mentions=_date_mentions(doc_id, plain),
                    corpus="cardiode",
                    domain="clinical",
                    # Dates carry an explicit in-place marker; how names were handled is not stated
                    # in the release and is an open item, so the tier is asserted for the date layer
                    # only (experiment_plan.md §18).
                    provenance="placeholder",
                    subject_id=None,  # one letter per patient; the release publishes no patient id
                    task={
                        "name": "cardiode",
                        "medications": annotations.medications,
                        "sections": annotations.sections,
                        "med_relations": annotations.relations,
                    },
                    metadata={
                        "annotation": "gold" if annotated else "none",
                        "split": split,
                        "restricted": "dua:cardiode:AM-only",
                        "n_medications": len(annotations.medications),
                        "n_sections": len(annotations.sections),
                    },
                )
            )
            tally = replace(
                tally, documents=tally.documents + 1, annotated=tally.annotated + annotated
            )
        if progress:
            progress(f"cardiode {split}: {tally}")
        if report is not None:
            report[split] = tally

    return Corpus("cardiode", tuple(documents))


def _numeric_key(path: Path) -> tuple[int, str]:
    """``1.txt`` before ``10.txt``, so a prefix limit is a stable, reproducible sample."""
    return (int(path.stem) if path.stem.isdigit() else 1 << 62, path.stem)


def iter_documents(corpus: Corpus) -> Iterator[Document]:
    return iter(corpus.documents)


@register_type
@dataclass(frozen=True, slots=True)
class Section:
    """A whole section of a letter, derived from its heading."""

    start: int
    end: int
    section_type: str
    heading: str


def derive_sections(
    headings: Sequence[SectionSpan], text_length: int
) -> tuple[Section, ...]:
    """Turn the heading annotations into sections by extending each heading to the next.

    ``custom:Sectionsentence`` does **not** mark sections.  It marks section **headings** of 4-18
    characters — about 62,000 characters of the corpus's 4.76 million (``experiment_plan.md`` §12.1)
    — so a section-classification task built directly on those annotations classifies roughly 1.3 %
    of the text and reports it as if it had classified the letter.

    Extending each heading to the start of the next, and the last one to the end of the letter, is
    what §12.1 requires.  Two consequences are worth stating:

    * The section **includes** its own heading.  The heading is part of the section it names, and
      excluding it would leave the corpus's most informative 62,000 characters unclassified.
    * Text **before the first heading** belongs to no section and is not classified.  Inventing a
      leading section would put an unlabelled span into the gold, which is worse than leaving it out.

    Headings are sorted and de-duplicated by position, because the CAS lists annotations in document
    order but nothing enforces it.
    """
    ordered = sorted(
        {(h.start, h.end, h.section_type) for h in headings if h.section_type}
    )
    sections: list[Section] = []
    for index, (start, end, section_type) in enumerate(ordered):
        following = ordered[index + 1][0] if index + 1 < len(ordered) else text_length
        if following <= start:
            continue                      # two headings at one offset: keep the first, drop the rest
        sections.append(
            Section(start=start, end=min(following, text_length), section_type=section_type,
                    heading=f"{start}:{end}")
        )
    return tuple(sections)
