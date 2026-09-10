"""One runner per task in ``experiment_plan.md`` §8.3's table.

===============================  ================  ============================================
task                              corpus            per-document score
===============================  ================  ============================================
co-reference                      TAB, OntoNotes    CoNLL F1 for that document
ECHR article classification       TAB               per-case micro-F1 over 30 labels
medication IE                     CARDIO:DE         span F1 per letter, all nine classes
section classification            CARDIO:DE         per-letter accuracy over derived sections
folder classification             Enron             correct / incorrect
formality                         CodEAlltag        absolute error per document
NER agreement                     all               span F1, original output vs condition output
===============================  ================  ============================================

Every runner takes a :class:`~pseudonymkit.engine.PseudonymisedCorpus` — which condition A also
produces (see :mod:`pseudonymkit.conditions`) — plus one frozen model, and returns a
:class:`~pseudonymkit.metrics.utility.ScoreVector`.  Comparing conditions is
:func:`pseudonymkit.metrics.utility.compare`'s job, not a runner's, and the original-text vector is
required to build a report at all (§8.3).

**Two tasks §8.3's table names have no runner here, and the reason is not effort.**

* *Intent / speech act* (Enron).  No corpus in the study carries a speech-act annotation and no
  adapter produces one, so there is no gold to score against.  §1 says an unrunnable cell is
  reported, not substituted, and inventing a label set would be a substitution.
* *Formality on Enron*.  §8.3's table lists formality for *"Enron, CodEAlltag"*, but the released
  formality scores are CodEAlltag's (Eder et al.); Enron has none.  The runner below is corpus-blind
  and will score Enron the moment a gold formality target exists in ``Document.task``.

Both are recorded here rather than silently omitted.
"""

from __future__ import annotations

from collections import Counter
from typing import Callable, Iterable, Mapping, Sequence

from ..adapters.cardiode import MEDICATION_CLASSES, SECTION_TYPES, derive_sections
from ..detectors.base import Detector
from ..domain import Document, Span
from ..engine import OffsetMap, PseudonymisedCorpus, PseudonymisedDocument
from ..metrics.coref import coref_scores
from ..metrics.utility import ScoreVector, absolute_error, multilabel_micro_f1, span_f1
from .base import (
    CoreferenceResolver,
    MultiLabelClassifier,
    Regressor,
    SingleLabelClassifier,
    SpanExtractor,
    scored,
)

__all__ = [
    "coreference",
    "echr_articles",
    "medication_ie",
    "section_classification",
    "folder_classification",
    "formality",
    "ner_agreement",
    "label_set",
]


def _as_document(document: PseudonymisedDocument) -> Document:
    """The condition's text as a document a detector can read, carrying no gold.

    The mentions are deliberately dropped: they are annotated against the *original* offsets, and a
    detector that received them would be reading annotations that no longer describe its input.
    """
    source = document.document
    return Document(
        doc_id=source.doc_id,
        text=document.text,
        language=source.language,
        corpus=source.corpus,
        domain=source.domain,
        subject_id=source.subject_id,
    )


def label_set(result: PseudonymisedCorpus, key: str = "label") -> tuple[str, ...]:
    """The closed label set a corpus actually carries, for the classification tasks.

    Derived from the corpus rather than written down: a hard-coded list of thirty ECHR articles that
    nobody checked against the release is exactly the kind of number §1's research-integrity rule
    forbids.  The derived set is recorded in the score vector's metadata, so a run says which labels
    it offered the model.
    """
    labels: set[str] = set()
    for document in result.documents:
        value = document.document.task.get(key)
        if isinstance(value, str):
            labels.add(value)
        elif isinstance(value, (list, tuple, set, frozenset)):
            labels.update(str(v) for v in value)
    return tuple(sorted(labels))


# ------------------------------------------------------------------------------------ co-reference


def coreference(
    result: PseudonymisedCorpus,
    resolver: CoreferenceResolver,
    *,
    condition: str,
    include_singletons: bool = False,
    metadata: Mapping[str, object] | None = None,
) -> ScoreVector:
    """CoNLL F1 per document, from the corpus's own chains against the resolver's output.

    This is the sharpest utility measurement in the study and the one that ties §8.2 to §8.3:
    fragmentation *is* chain breakage, so a resolver's CoNLL F1 on pseudonymised text is the utility
    cost of exactly the failure the stability metrics count, on the same documents.

    Gold mentions are the corpus's mentions that carry a ``gold_entity_id``, mapped forward onto the
    condition's text.  A document whose gold holds no chain of more than one mention is **excluded**
    rather than scored zero — on TAB and OntoNotes roughly three quarters of PERSON chains are
    singletons (§8.2), so scoring them as failures would swamp the measurement with documents in
    which nothing could have gone wrong.
    """
    scores: list[tuple[str, float]] = []
    skipped: Counter[str] = Counter()
    for document in result.documents:
        mapping = OffsetMap.of(document)
        gold: dict[str, list[tuple[int, int]]] = {}
        for mention in document.document.mentions:
            if not mention.gold_entity_id:
                continue
            gold.setdefault(mention.gold_entity_id, []).append(
                mapping.span(mention.span.start, mention.span.end)
            )
        predicted = [list(cluster) for cluster in resolver.resolve(document.text)]
        result_scores = coref_scores(gold.values(), predicted, include_singletons)
        conll = result_scores["conll"]
        if conll != conll:                       # NaN: no scorable gold chain in this document
            skipped["no_multi_mention_chain"] += 1
            continue
        scores.append((document.document.doc_id, conll))

    return scored(
        "coreference", condition, scores, model=resolver.name,
        metadata={"include_singletons": include_singletons, **dict(metadata or {})},
        skipped=skipped,
    )


# --------------------------------------------------------------------------- multi-label: articles


def echr_articles(
    result: PseudonymisedCorpus,
    classifier: MultiLabelClassifier,
    *,
    condition: str,
    labels: Sequence[str] | None = None,
    metadata: Mapping[str, object] | None = None,
) -> ScoreVector:
    """Per-case micro-F1 on TAB's ECHR articles, whose labels ride in the corpus's ``meta.articles``.

    The legal utility task needs no join to an external judgment-prediction dataset, which is one
    reason TAB is a *full*-role corpus (§11).  A case with no article label is excluded: micro-F1
    against an empty gold rewards predicting nothing.
    """
    label_list = list(labels) if labels is not None else list(label_set(result))
    scores: list[tuple[str, float]] = []
    skipped: Counter[str] = Counter()
    for document in result.documents:
        gold = document.document.task.get("label") or ()
        if not gold:
            skipped["no_article_label"] += 1
            continue
        predicted = classifier.classify(document.text, label_list)
        scores.append(
            (document.document.doc_id, multilabel_micro_f1(gold, predicted))
        )
    return scored(
        "echr_articles", condition, scores, model=classifier.name,
        metadata={"labels": len(label_list), **dict(metadata or {})}, skipped=skipped,
    )


# ------------------------------------------------------------------------------ CARDIO:DE, spans


def medication_ie(
    result: PseudonymisedCorpus,
    extractor: SpanExtractor,
    *,
    condition: str,
    classes: Sequence[str] = MEDICATION_CLASSES,
    typed: bool = True,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, ScoreVector]:
    """Span F1 per letter over CARDIO:DE's nine medication classes.

    Returns **three** vectors from one set of predictions:

    ``medication_ie``
        every gold span, which is the headline number.
    ``medication_ie:in_narrative``
        the spans the CAS marks ``InNarrative`` — a medication mentioned in running prose rather than
        in a medication list.
    ``medication_ie:listed``
        the rest.

    §12.1 requires ``InNarrative`` to be **reported as a split, not filtered**: dropping it would
    quietly restrict the task to the tabular part of the letter, which is the part pseudonymisation
    disturbs least, and would flatter every condition.
    """
    splits: dict[str, list[tuple[str, float]]] = {
        "medication_ie": [], "medication_ie:in_narrative": [], "medication_ie:listed": [],
    }
    skipped: Counter[str] = Counter()
    keep = set(classes)

    for document in result.documents:
        gold_spans = [
            m for m in document.document.task.get("medications", ()) if m.class_type in keep
        ]
        if not gold_spans:
            skipped["no_medication_gold"] += 1
            continue
        mapping = OffsetMap.of(document)
        predicted = list(extractor.extract(document.text, list(classes)))
        doc_id = document.document.doc_id
        for name, subset in (
            ("medication_ie", gold_spans),
            ("medication_ie:in_narrative", [m for m in gold_spans if m.in_narrative]),
            ("medication_ie:listed", [m for m in gold_spans if not m.in_narrative]),
        ):
            if not subset:
                continue
            gold = [(*mapping.span(m.start, m.end), m.class_type) for m in subset]
            splits[name].append((doc_id, span_f1(gold, predicted, typed=typed)))

    return {
        name: scored(
            name, condition, pairs, model=extractor.name,
            metadata={"classes": len(keep), "typed": typed, **dict(metadata or {})},
            skipped=skipped if name == "medication_ie" else None,
        )
        for name, pairs in splits.items()
    }


# --------------------------------------------------------------------------- CARDIO:DE, sections


def section_classification(
    result: PseudonymisedCorpus,
    classifier: SingleLabelClassifier,
    *,
    condition: str,
    types: Sequence[str] = SECTION_TYPES,
    metadata: Mapping[str, object] | None = None,
) -> ScoreVector:
    """Per-letter accuracy over the sections **derived by extending each heading to the next**.

    ``custom:Sectionsentence`` marks headings of 4-18 characters, not sections (§12.1): a task built
    on the annotations as they stand classifies about 1.3 % of the corpus and reports it as if it had
    classified the letter.  :func:`pseudonymkit.adapters.cardiode.derive_sections` does the
    extension, and each derived section's text is classified into the fourteen types.

    **A note on the score's kind.**  §8.3's table calls this *"per-letter accuracy"*, which is a
    proportion and continuous, while the same section lists section classification under McNemar,
    which is for binary correctness.  A letter has many sections, so the per-letter score is
    continuous and Wilcoxon applies; ``kind`` is exposed so the other reading can be produced without
    a second implementation, and the conflict is recorded here rather than resolved silently.
    """
    type_list = list(types)
    scores: list[tuple[str, float]] = []
    skipped: Counter[str] = Counter()
    for document in result.documents:
        headings = document.document.task.get("sections", ())
        sections = derive_sections(headings, len(document.document.text))
        if not sections:
            skipped["no_section_headings"] += 1
            continue
        mapping = OffsetMap.of(document)
        correct = 0
        for section in sections:
            start, end = mapping.span(section.start, section.end)
            predicted = classifier.classify(document.text[start:end], type_list)
            correct += predicted == section.section_type
        scores.append((document.document.doc_id, correct / len(sections)))

    return scored(
        "section_classification", condition, scores, model=classifier.name,
        metadata={"types": len(type_list), **dict(metadata or {})}, skipped=skipped,
    )


# ------------------------------------------------------------------------------- Enron, folders


def folder_classification(
    result: PseudonymisedCorpus,
    classifier: SingleLabelClassifier,
    *,
    condition: str,
    labels: Sequence[str] | None = None,
    metadata: Mapping[str, object] | None = None,
) -> ScoreVector:
    """Klimt & Yang's (ECML 2004) folder task, scored zero-shot against the mailbox folder.

    Binary per document, so the paired test is McNemar (§8.3).

    The label is the mailbox folder, and ``X-Folder`` names it — which is why the Enron adapter
    excludes that header from the document text (§12.1).  A runner cannot check that for itself; if
    the header ever came back, this task would score near-perfectly in every condition and the
    result would be meaningless rather than good.
    """
    label_list = list(labels) if labels is not None else list(label_set(result))
    scores: list[tuple[str, float]] = []
    skipped: Counter[str] = Counter()
    for document in result.documents:
        gold = document.document.task.get("label")
        if not isinstance(gold, str) or not gold:
            skipped["no_folder_label"] += 1
            continue
        predicted = classifier.classify(document.text, label_list)
        scores.append((document.document.doc_id, float(predicted == gold)))

    return scored(
        "folder_classification", condition, scores, model=classifier.name, kind="binary",
        metadata={"labels": len(label_list), **dict(metadata or {})}, skipped=skipped,
    )


# --------------------------------------------------------------------------------- formality


def formality(
    result: PseudonymisedCorpus,
    regressor: Regressor,
    *,
    condition: str,
    key: str = "formality",
    metadata: Mapping[str, object] | None = None,
) -> ScoreVector:
    """Absolute error per document against the released formality score.

    CodEAlltag ships per-document formality in ``[-1, +1]`` from Eder et al.'s transformer scorers;
    they are the gold, and the frozen model's prediction is scored against them.

    Note the sign: this is an **error**, so lower is better and ``higher_is_better`` is ``False``.  A
    *positive* median difference against the original-text vector therefore means the condition did
    worse.  §8.3 also offers Spearman rho per batch as an alternative; that is a corpus-level summary
    and is computed from these same predictions by
    :func:`pseudonymkit.metrics.utility.spearman`, never as a per-document score.
    """
    scores: list[tuple[str, float]] = []
    skipped: Counter[str] = Counter()
    for document in result.documents:
        gold = document.document.task.get(key)
        if not isinstance(gold, (int, float)):
            skipped["no_formality_score"] += 1
            continue
        scores.append(
            (document.document.doc_id, absolute_error(float(gold), regressor.predict(document.text)))
        )
    return scored(
        "formality", condition, scores, model=regressor.name, higher_is_better=False,
        metadata=dict(metadata or {}), skipped=skipped,
    )


# ------------------------------------------------------------------------------- NER agreement


def ner_agreement(
    result: PseudonymisedCorpus,
    detector: Detector,
    *,
    condition: str,
    reference: Mapping[str, Sequence[Span]] | None = None,
    typed: bool = True,
    metadata: Mapping[str, object] | None = None,
) -> ScoreVector:
    """Span F1 between one detector's output on the original text and on the condition's text.

    Applies to every corpus, because it needs no gold at all — it asks whether pseudonymisation
    changed what a downstream NER model finds, which is the utility question for every pipeline that
    consumes entities rather than labels.

    ``reference`` lets a caller pass the original-text output in, which matters: without it the
    detector is re-run on the original once per condition, and detection is the only step in the
    study that costs model time.  Condition A scores 1.0 by construction — the two texts are the same
    — and that is a useful check that the map and the detector are behaving.
    """
    scores: list[tuple[str, float]] = []
    for document in result.documents:
        source = document.document
        original = (
            list(reference[source.doc_id])
            if reference is not None and source.doc_id in reference
            else list(detector.detect(source).spans)
        )
        mapping = OffsetMap.of(document)
        before = [(*mapping.span(s.start, s.end), s.type) for s in original]
        after = [
            (s.start, s.end, s.type)
            for s in detector.detect(_as_document(document)).spans
        ]
        scores.append((source.doc_id, span_f1(before, after, typed=typed)))

    return scored(
        "ner_agreement", condition, scores, model=detector.name,
        metadata={"typed": typed, **dict(metadata or {})},
    )
