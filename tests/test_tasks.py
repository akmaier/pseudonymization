"""The utility task runners of experiment_plan.md §8.3.

Every runner is driven by a stand-in scorer, so no model is loaded and no gateway is called.  What is
tested is the part that decides whether a number means anything: that gold annotated against the
*original* text is carried onto the condition's text before it is scored, that a document nothing
could be scored on is excluded rather than entered as a zero, that the scorer's name reaches the
result row, and that condition A comes out as the no-op it is.
"""

from __future__ import annotations

import math

import pytest

from pseudonymkit.adapters.cardiode import (
    MEDICATION_CLASSES,
    MedicationSpan,
    SectionSpan,
    derive_sections,
)
from pseudonymkit.conditions import build as build_condition
from pseudonymkit.domain import Corpus, Document, Mention, Span
from pseudonymkit.inventories import SyntheticInventory
from pseudonymkit.metrics.utility import UtilityReport, compare
from pseudonymkit.tasks import (
    coreference,
    echr_articles,
    folder_classification,
    formality,
    label_set,
    medication_ie,
    ner_agreement,
    section_classification,
)

KEY = b"\x33" * 32


def condition(name: str):
    if name == "A":
        return build_condition("A")
    return build_condition(name, inventory=SyntheticInventory(pool_size=4096), key=KEY)


# --------------------------------------------------------------------------------------- fixtures


def person_doc(doc_id: str, text: str, entities, **kwargs) -> Document:
    cursor = 0
    mentions = []
    for i, (surface, type_, chain) in enumerate(entities):
        start = text.index(surface, cursor)
        cursor = start + len(surface)
        mentions.append(
            Mention(doc_id, f"m{i}", Span(start, start + len(surface), surface, type_),
                    gold_entity_id=chain)
        )
    return Document(doc_id, text, "en", tuple(mentions), **kwargs)


@pytest.fixture
def tab_like() -> Corpus:
    a = person_doc(
        "t1", "Weber applied. Weber was heard. Berlin refused.",
        [("Weber", "PERSON", "e1"), ("Weber", "PERSON", "e1"), ("Berlin", "LOC", "e2")],
        task={"name": "echr_articles", "label": ("Art.6", "Art.13")},
    )
    b = person_doc(
        "t2", "Meyer applied. Meyer was heard.",
        [("Meyer", "PERSON", "e1"), ("Meyer", "PERSON", "e1")],
        task={"name": "echr_articles", "label": ("Art.6",)},
    )
    return Corpus("tab-like", (a, b))


class GoldResolver:
    """A resolver that returns whatever spans it is told to, per text."""

    name = "stub-coref"

    def __init__(self, clusters_by_text=None, perfect_for=None):
        self._by_text = clusters_by_text or {}
        self._perfect = perfect_for

    def resolve(self, text):
        if self._perfect is not None:
            return self._perfect(text)
        return self._by_text.get(text, [])


def perfect_from(result):
    """Build a resolver that reproduces the mapped gold clusters exactly."""
    from pseudonymkit.engine import OffsetMap

    table = {}
    for pdoc in result.documents:
        mapping = OffsetMap.of(pdoc)
        chains = {}
        for mention in pdoc.document.mentions:
            if mention.gold_entity_id:
                chains.setdefault(mention.gold_entity_id, []).append(
                    mapping.span(mention.span.start, mention.span.end)
                )
        table[pdoc.text] = list(chains.values())
    return GoldResolver(table)


# ------------------------------------------------------------------------------------ co-reference


def test_coreference_scores_one_when_the_resolver_reproduces_the_gold(tab_like):
    result = condition("B").pseudonymise_corpus(tab_like)
    vector = coreference(result, perfect_from(result), condition="B")
    assert vector.task == "coreference"
    assert vector.scores == (1.0, 1.0)
    assert vector.metadata["scorer"] == "stub-coref"


def test_coreference_gold_is_carried_onto_the_condition_text(tab_like):
    """The failure this guards: gold offsets that no longer describe the text being scored."""
    result = condition("C").pseudonymise_corpus(tab_like)
    original = condition("A").pseudonymise_corpus(tab_like)
    # A resolver keyed on the *original* text finds nothing in the placeholder text, and a runner
    # that forgot the offset map would still score above zero by luck.
    stale = perfect_from(original)
    assert coreference(result, stale, condition="C").scores == (0.0, 0.0)
    assert coreference(result, perfect_from(result), condition="C").scores == (1.0, 1.0)


def test_coreference_excludes_a_document_with_no_chain():
    corpus = Corpus("x", (
        person_doc("d1", "Weber applied.", [("Weber", "PERSON", "e1")]),
        person_doc("d2", "Meyer applied. Meyer left.",
                   [("Meyer", "PERSON", "e2"), ("Meyer", "PERSON", "e2")]),
    ))
    result = condition("A").pseudonymise_corpus(corpus)
    vector = coreference(result, perfect_from(result), condition="A")
    assert vector.doc_ids == ("d2",)
    assert vector.metadata["skipped"] == {"no_multi_mention_chain": 1}


# ------------------------------------------------------------------------------- ECHR articles


class Classifier:
    name = "stub-classifier"

    def __init__(self, answer):
        self._answer = answer
        self.label_sets = []

    def classify(self, text, labels):
        self.label_sets.append(tuple(labels))
        return self._answer(text) if callable(self._answer) else self._answer


def test_echr_articles_derives_the_label_set_from_the_corpus(tab_like):
    result = condition("A").pseudonymise_corpus(tab_like)
    assert label_set(result) == ("Art.13", "Art.6")
    classifier = Classifier(("Art.6",))
    vector = echr_articles(result, classifier, condition="A")
    assert classifier.label_sets[0] == ("Art.13", "Art.6")
    assert vector.metadata["labels"] == 2


def test_echr_articles_scores_micro_f1_per_case(tab_like):
    result = condition("A").pseudonymise_corpus(tab_like)
    vector = echr_articles(result, Classifier(("Art.6",)), condition="A")
    # t1's gold is two articles, one of them found: P=1, R=0.5, F1=2/3. t2's gold is exactly Art.6.
    assert vector.scores == pytest.approx((2 / 3, 1.0))


def test_echr_articles_excludes_a_case_with_no_label():
    corpus = Corpus("x", (
        person_doc("d1", "Nothing.", [], task={"name": "echr_articles", "label": ()}),
    ))
    result = condition("A").pseudonymise_corpus(corpus)
    vector = echr_articles(result, Classifier(()), condition="A", labels=["Art.6"])
    assert vector.n == 0
    assert vector.metadata["skipped"] == {"no_article_label": 1}


# ------------------------------------------------------------------------------- medication IE


@pytest.fixture
def cardiode_like() -> Corpus:
    text = "Herr Weber erhielt Aspirin 100 mg. Im Verlauf wurde Ramipril gegeben."
    document = Document(
        "c1", text, "de",
        (Mention("c1", "m0", Span(5, 10, "Weber", "PERSON")),),
        corpus="cardiode",
        task={
            "name": "cardiode",
            "medications": (
                MedicationSpan(text.index("Aspirin"), text.index("Aspirin") + 7, "Aspirin",
                               "DRUG", False, False, "1"),
                MedicationSpan(text.index("Ramipril"), text.index("Ramipril") + 8, "Ramipril",
                               "DRUG", True, False, "2"),
            ),
            "sections": (),
        },
    )
    return Corpus("cardiode-like", (document,))


class Extractor:
    name = "stub-extractor"

    def __init__(self, surfaces):
        self._surfaces = surfaces

    def extract(self, text, classes):
        out = []
        for surface, label in self._surfaces:
            start = text.find(surface)
            if start >= 0:
                out.append((start, start + len(surface), label))
        return out


def test_medication_ie_reports_in_narrative_as_a_split_not_a_filter(cardiode_like):
    result = condition("B").pseudonymise_corpus(cardiode_like)
    vectors = medication_ie(
        result, Extractor([("Aspirin", "DRUG"), ("Ramipril", "DRUG")]), condition="B"
    )
    assert set(vectors) == {"medication_ie", "medication_ie:in_narrative", "medication_ie:listed"}
    assert vectors["medication_ie"].scores == (1.0,)
    assert vectors["medication_ie:in_narrative"].n == 1
    assert vectors["medication_ie:listed"].n == 1


def test_medication_ie_gold_is_carried_past_a_replaced_name(cardiode_like):
    """The person's surrogate is a different length, so every following gold offset moves."""
    result = condition("C").pseudonymise_corpus(cardiode_like)
    vectors = medication_ie(result, Extractor([("Aspirin", "DRUG"), ("Ramipril", "DRUG")]),
                            condition="C")
    assert vectors["medication_ie"].scores == (1.0,)


def test_medication_ie_covers_all_nine_classes(cardiode_like):
    result = condition("A").pseudonymise_corpus(cardiode_like)
    vectors = medication_ie(result, Extractor([]), condition="A")
    assert vectors["medication_ie"].metadata["classes"] == len(MEDICATION_CLASSES) == 9


def test_medication_ie_skips_a_letter_with_no_gold():
    corpus = Corpus("x", (
        Document("c9", "Nichts.", "de", (), task={"name": "cardiode", "medications": ()}),
    ))
    result = condition("A").pseudonymise_corpus(corpus)
    vectors = medication_ie(result, Extractor([]), condition="A")
    assert vectors["medication_ie"].n == 0
    assert vectors["medication_ie"].metadata["skipped"] == {"no_medication_gold": 1}


# ------------------------------------------------------------------------- section classification


def test_sections_are_derived_by_extending_each_heading_to_the_next():
    """§12.1: `custom:Sectionsentence` marks headings of 4-18 characters, not sections."""
    headings = [SectionSpan(0, 7, "Anamnese", "1"), SectionSpan(50, 57, "Befunde", "2")]
    sections = derive_sections(headings, 120)
    assert [(s.start, s.end, s.section_type) for s in sections] == [
        (0, 50, "Anamnese"), (50, 120, "Befunde")
    ]


def test_a_section_task_on_the_raw_headings_would_cover_almost_nothing():
    headings = [SectionSpan(0, 7, "Anamnese", "1"), SectionSpan(50, 57, "Befunde", "2")]
    heading_chars = sum(h.end - h.start for h in headings)
    derived = sum(s.end - s.start for s in derive_sections(headings, 120))
    assert heading_chars == 14 and derived == 120


def test_section_classification_is_per_letter_accuracy():
    text = "Anamnese\nDer Patient klagt.\nBefunde\nEKG unauffaellig.\n"
    document = Document(
        "c1", text, "de", (),
        task={
            "name": "cardiode",
            "medications": (),
            "sections": (
                SectionSpan(0, 8, "Anamnese", "1"),
                SectionSpan(text.index("Befunde"), text.index("Befunde") + 7, "Befunde", "2"),
            ),
        },
    )
    result = condition("A").pseudonymise_corpus(Corpus("x", (document,)))
    always_anamnese = Classifier("Anamnese")
    vector = section_classification(result, always_anamnese, condition="A")
    assert vector.scores == (0.5,)
    assert vector.metadata["types"] == 14


def test_section_classification_skips_a_letter_with_no_headings():
    document = Document("c2", "Text.", "de", (),
                        task={"name": "cardiode", "sections": ()})
    result = condition("A").pseudonymise_corpus(Corpus("x", (document,)))
    vector = section_classification(result, Classifier("Anamnese"), condition="A")
    assert vector.n == 0
    assert vector.metadata["skipped"] == {"no_section_headings": 1}


# ------------------------------------------------------------------------ folder classification


def test_folder_classification_is_binary_for_mcnemar():
    corpus = Corpus("x", (
        Document("e1", "About the deal.", "en", (), task={"name": "enron_folder",
                                                          "label": "deals"}),
        Document("e2", "Lunch?", "en", (), task={"name": "enron_folder", "label": "personal"}),
    ))
    result = condition("A").pseudonymise_corpus(corpus)
    vector = folder_classification(result, Classifier("deals"), condition="A")
    assert vector.kind == "binary"
    assert vector.scores == (1.0, 0.0)
    assert vector.metadata["labels"] == 2


# ------------------------------------------------------------------------------------ formality


class Regressor:
    name = "stub-regressor"

    def __init__(self, value):
        self._value = value

    def predict(self, text):
        return self._value


def test_formality_is_an_error_so_lower_is_better():
    corpus = Corpus("x", (
        Document("f1", "Sehr geehrte Damen und Herren,", "de", (),
                 task={"name": "codealltag_utility", "formality": 0.8}),
    ))
    result = condition("A").pseudonymise_corpus(corpus)
    vector = formality(result, Regressor(0.5), condition="A")
    assert vector.higher_is_better is False
    assert vector.scores == pytest.approx((0.3,))


def test_formality_skips_a_document_with_no_released_score():
    corpus = Corpus("x", (
        Document("f2", "Hallo", "de", (), task={"name": "codealltag_utility"}),
    ))
    result = condition("A").pseudonymise_corpus(corpus)
    vector = formality(result, Regressor(0.0), condition="A")
    assert vector.n == 0
    assert vector.metadata["skipped"] == {"no_formality_score": 1}


# --------------------------------------------------------------------------------- NER agreement


class SurfaceDetector:
    """Finds fixed surfaces wherever they appear — a detector whose behaviour is knowable."""

    name = "stub-ner"
    family = "rule"

    def __init__(self, surfaces):
        self._surfaces = surfaces

    def detect(self, document):
        from pseudonymkit.detectors.base import DetectorOutput

        spans = []
        for surface, type_ in self._surfaces:
            start = 0
            while (start := document.text.find(surface, start)) >= 0:
                spans.append(Span(start, start + len(surface), surface, type_))
                start += len(surface)
        return DetectorOutput(document.doc_id, self.name, tuple(spans))


def test_ner_agreement_is_one_on_condition_a(tab_like):
    result = condition("A").pseudonymise_corpus(tab_like)
    detector = SurfaceDetector([("Weber", "PERSON"), ("Berlin", "LOC")])
    vector = ner_agreement(result, detector, condition="A")
    assert vector.scores == (1.0, 1.0)
    assert vector.metadata["scorer"] == "stub-ner"


def test_ner_agreement_falls_when_the_detector_misses_the_surrogate(tab_like):
    """The detector only knows the original surfaces, so under C it finds nothing."""
    result = condition("C").pseudonymise_corpus(tab_like)
    detector = SurfaceDetector([("Weber", "PERSON"), ("Meyer", "PERSON"), ("Berlin", "LOC")])
    vector = ner_agreement(result, detector, condition="C")
    assert vector.scores == (0.0, 0.0)


def test_ner_agreement_scores_one_when_neither_text_had_anything_to_find(tab_like):
    """Right that there was nothing there is not the same failure as finding nothing."""
    result = condition("C").pseudonymise_corpus(tab_like)
    vector = ner_agreement(result, SurfaceDetector([("Nobody", "PERSON")]), condition="C")
    assert vector.scores == (1.0, 1.0)


def test_ner_agreement_accepts_a_precomputed_reference(tab_like):
    """Detection is the only step that costs model time; the original must not be re-run per cell."""
    result = condition("A").pseudonymise_corpus(tab_like)
    detector = SurfaceDetector([("Weber", "PERSON")])
    reference = {d.doc_id: detector.detect(d).spans for d in tab_like}

    class Counting(SurfaceDetector):
        def __init__(self, surfaces):
            super().__init__(surfaces)
            self.calls = 0

        def detect(self, document):
            self.calls += 1
            return super().detect(document)

    counting = Counting([("Weber", "PERSON")])
    ner_agreement(result, counting, condition="A", reference=reference)
    assert counting.calls == len(tab_like)          # the condition text only, not the original too


# ------------------------------------------------------- the runners feed the statistics layer


def test_a_runners_output_goes_straight_into_a_utility_report(tab_like):
    original = condition("A").pseudonymise_corpus(tab_like)
    pseudonymised = condition("C").pseudonymise_corpus(tab_like)
    detector = SurfaceDetector([("Weber", "PERSON"), ("Meyer", "PERSON"), ("Berlin", "LOC")])

    reference = ner_agreement(original, detector, condition="original")
    condition_c = ner_agreement(pseudonymised, detector, condition="C")
    report = UtilityReport.build(reference, [condition_c])

    assert report.task == "ner_agreement"
    assert report.comparisons[0].condition == "C"
    assert report.comparisons[0].median_difference == -1.0
    assert not math.isnan(report.comparisons[0].p_value)


def test_compare_refuses_to_mix_a_binary_and_a_continuous_vector():
    """Applying a rank test to 0/1 correctness gives a p-value that answers a different question."""
    from pseudonymkit.metrics.utility import ScoreVector

    binary = ScoreVector("t", "original", ("a", "b"), (1.0, 0.0), kind="binary")
    continuous = ScoreVector("t", "C", ("a", "b"), (0.4, 0.9), kind="continuous")
    with pytest.raises(ValueError, match="kind mismatch"):
        compare(binary, continuous)
