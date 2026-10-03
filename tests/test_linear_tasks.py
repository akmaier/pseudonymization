"""The frozen linear utility scorers (plan §8.5).

Two halves.  The decoding, tokenising and label-masking logic is driven with five-line stand-ins
for the estimator, exactly as ``base.py`` intends — those tests need no scikit-learn and run in the
suite's ordinary budget.  The fitting itself is behind an ``importorskip``: scikit-learn is an
optional dependency (``pyproject.toml``'s ``tasks`` extra) and the suite must stay model-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pytest

from pseudonymkit.metrics.utility import span_f1
from pseudonymkit.tasks.base import SingleLabelClassifier, SpanExtractor
from pseudonymkit.tasks.linear import (
    TfidfLogisticClassifier,
    TfidfLogisticTagger,
    bio_tags,
    decode_bio,
    split_documents,
    token_features,
    tokenise,
)


# ------------------------------------------------------------------------------------ stand-ins


@dataclass
class FakeVectoriser:
    """``transform`` is the identity: the fake model reads the strings straight."""

    def transform(self, rows: Sequence[str]) -> list[str]:
        return list(rows)


@dataclass
class FakeLinear:
    """Scores a class by how often its name occurs in the text, so the argmax is predictable."""

    classes_: list[str]

    def decision_function(self, rows: Sequence[str]) -> list[list[float]]:
        return [[float(row.count(c)) for c in self.classes_] for row in rows]


@dataclass
class FakeBinary:
    """A two-class model with scikit-learn's one-column ``decision_function``."""

    classes_: list[str]

    def decision_function(self, rows: Sequence[str]) -> list[float]:
        return [1.0 if "yes" in row else -1.0 for row in rows]


@dataclass
class FakeTagger:
    """Tags a token ``B-DRUG`` when its feature string carries a known drug word."""

    def predict(self, rows: Sequence[str]) -> list[str]:
        out = []
        for row in rows:
            word = next((p[2:] for p in row.split() if p.startswith("w=")), "")
            out.append("B-DRUG" if word in {"aspirin", "ramipril"} else "O")
        return out


def classifier(classes: list[str]) -> TfidfLogisticClassifier:
    return TfidfLogisticClassifier(
        vectoriser=FakeVectoriser(), model=FakeLinear(classes), task_name="t", fingerprint="abc123"
    )


# ------------------------------------------------------------------------------------- the ports


def test_the_scorers_satisfy_the_ports_the_runners_drive() -> None:
    assert isinstance(classifier(["a", "b"]), SingleLabelClassifier)
    assert isinstance(
        TfidfLogisticTagger(vectoriser=FakeVectoriser(), model=FakeTagger()), SpanExtractor
    )


def test_the_name_carries_the_artefact_fingerprint() -> None:
    assert classifier(["a", "b"]).name == "linear:tfidf-lr/t@abc123"
    assert "unfitted" in TfidfLogisticTagger(vectoriser=None, model=None).name


# -------------------------------------------------------------------------- the closed label set


def test_the_answer_comes_from_the_labels_the_runner_offered() -> None:
    """A class the model knows but the runner did not offer must not be returned."""
    scorer = classifier(["anamnese", "befund", "medikation"])
    text = "befund befund befund medikation"
    assert scorer.classify(text, ["anamnese", "befund", "medikation"]) == "befund"
    assert scorer.classify(text, ["anamnese", "medikation"]) == "medikation"


def test_no_overlap_with_the_offered_set_is_a_wrong_answer_not_a_crash() -> None:
    assert classifier(["a", "b"]).classify("a a a", ["x", "y"]) == ""
    assert classifier(["a", "b"]).classify("a a a", []) == ""


def test_the_binary_decision_function_is_widened_rather_than_indexed() -> None:
    """Two classes give scikit-learn one column; reading it per class would pick the wrong one."""
    scorer = TfidfLogisticClassifier(
        vectoriser=FakeVectoriser(), model=FakeBinary(["no", "yes"]), task_name="t"
    )
    assert scorer.classify("yes please", ["no", "yes"]) == "yes"
    assert scorer.classify("nothing here", ["no", "yes"]) == "no"


def test_ties_resolve_to_the_first_class_so_scoring_is_deterministic() -> None:
    scorer = classifier(["alpha", "beta"])
    assert scorer.classify("nothing matches", ["alpha", "beta"]) == "alpha"
    assert scorer.classify("nothing matches", ["beta", "alpha"]) == "alpha"


# ------------------------------------------------------------------------------- tokens and BIO


def test_tokens_carry_character_offsets_that_index_back_into_the_text() -> None:
    text = "Ramipril 5 mg, 1-0-1."
    for start, end, surface in tokenise(text):
        assert text[start:end] == surface


def test_punctuation_is_its_own_token_so_a_gold_boundary_inside_one_is_reachable() -> None:
    assert [s for _, _, s in tokenise("1-0-1")] == ["1", "-", "0", "-", "1"]


def test_bio_round_trips_a_gold_span_exactly() -> None:
    text = "Patient nimmt Ramipril 5 mg taeglich."
    tokens = tokenise(text)
    start = text.index("Ramipril 5 mg")
    gold = [(start, start + len("Ramipril 5 mg"), "DRUG")]
    assert decode_bio(tokens, bio_tags(tokens, gold)) == gold
    assert span_f1(gold, decode_bio(tokens, bio_tags(tokens, gold))) == 1.0


def test_two_adjacent_spans_of_one_class_do_not_merge() -> None:
    text = "Aspirin Ramipril"
    tokens = tokenise(text)
    gold = [(0, 7, "DRUG"), (8, 16, "DRUG")]
    assert decode_bio(tokens, bio_tags(tokens, gold)) == gold


def test_a_token_a_gold_boundary_cuts_through_is_claimed_whole() -> None:
    """``5mg`` is one token; gold marking only ``5`` can still be decoded, as the whole token."""
    text = "Ramipril 5mg"
    tokens = tokenise(text)
    decoded = decode_bio(tokens, bio_tags(tokens, [(9, 10, "DOSE")]))
    assert decoded == [(9, 12, "DOSE")]


def test_a_stray_inside_tag_opens_a_span_rather_than_being_dropped() -> None:
    tokens = tokenise("Aspirin Ramipril")
    assert decode_bio(tokens, ["I-DRUG", "O"]) == [(0, 7, "DRUG")]


def test_the_tagger_drops_a_class_the_runner_did_not_offer() -> None:
    tagger = TfidfLogisticTagger(vectoriser=FakeVectoriser(), model=FakeTagger())
    text = "Aspirin und Ramipril"
    assert len(tagger.extract(text, ["DRUG"])) == 2
    assert tagger.extract(text, ["DOSE"]) == []


def test_the_tagger_returns_nothing_for_an_empty_document() -> None:
    tagger = TfidfLogisticTagger(vectoriser=FakeVectoriser(), model=FakeTagger())
    assert tagger.extract("   ", ["DRUG"]) == []


def test_features_name_the_neighbours_at_both_edges() -> None:
    tokens = tokenise("Aspirin Ramipril")
    assert "prev=<s>" in token_features(tokens, 0)
    assert "next=</s>" in token_features(tokens, 1)


# ------------------------------------------------------------------------------------- the split


def test_the_split_is_document_disjoint_and_covers_everything() -> None:
    ids = [f"d{i}" for i in range(20)]
    train, score = split_documents(ids, seed=0)
    assert not set(train) & set(score)
    assert set(train) | set(score) == set(ids)
    assert len(train) == 10


def test_the_split_depends_on_the_seed_and_not_on_the_input_order() -> None:
    ids = [f"d{i}" for i in range(20)]
    assert split_documents(ids, seed=0) == split_documents(list(reversed(ids)), seed=0)
    assert split_documents(ids, seed=0) != split_documents(ids, seed=1)


# ----------------------------------------------------------------------------- fitting, if it can


def test_a_fitted_classifier_separates_two_obvious_classes() -> None:
    pytest.importorskip("sklearn", reason="scikit-learn is the optional `tasks` extra")
    from pseudonymkit.tasks.linear import train_single_label_classifier

    texts = {f"d{i}": ("fieber husten schnupfen" if i % 2 else "ramipril aspirin dosis")
             for i in range(40)}
    labels = {f"d{i}": ("anamnese" if i % 2 else "medikation") for i in range(40)}
    train, score = split_documents(list(texts), seed=0)

    artefact = train_single_label_classifier(
        texts, labels, task_name="section_classification", train_ids=train, score_ids=score,
        corpus="fixture", min_df=1,
    )
    assert artefact.holdout_score == 1.0
    assert not set(artefact.train_doc_ids) & set(artefact.score_doc_ids)
    assert artefact.scorer.classify("fieber", ["anamnese", "medikation"]) == "anamnese"
    assert "@" in artefact.scorer.name and "unfitted" not in artefact.scorer.name


def test_a_training_half_with_one_label_is_refused_rather_than_fitted() -> None:
    pytest.importorskip("sklearn", reason="scikit-learn is the optional `tasks` extra")
    from pseudonymkit.tasks.linear import train_single_label_classifier

    texts = {f"d{i}": "same text" for i in range(10)}
    labels = {f"d{i}": "one" for i in range(10)}
    train, score = split_documents(list(texts), seed=0)
    with pytest.raises(ValueError, match="distinct labels"):
        train_single_label_classifier(
            texts, labels, task_name="t", train_ids=train, score_ids=score, corpus="fixture",
            min_df=1,
        )


def test_a_fitted_tagger_recovers_a_memorable_span_and_reports_it_in_span_f1() -> None:
    pytest.importorskip("sklearn", reason="scikit-learn is the optional `tasks` extra")
    from pseudonymkit.tasks.linear import train_span_tagger

    texts, spans = {}, {}
    for i in range(40):
        text = f"Patient {i} nimmt Ramipril taeglich."
        texts[f"d{i}"] = text
        start = text.index("Ramipril")
        spans[f"d{i}"] = [(start, start + len("Ramipril"), "DRUG")]
    train, score = split_documents(list(texts), seed=0)

    artefact = train_span_tagger(
        texts, spans, train_ids=train, score_ids=score, corpus="fixture", classes=["DRUG"],
    )
    assert artefact.holdout_score == 1.0
    assert artefact.metadata["kind"] == "bio-tagger"


def test_an_artefact_round_trips_through_disk_with_its_provenance_readable(tmp_path) -> None:
    pytest.importorskip("sklearn", reason="scikit-learn is the optional `tasks` extra")
    import json

    from pseudonymkit.tasks.linear import (
        load_artefact, save_artefact, train_single_label_classifier,
    )

    texts = {f"d{i}": ("a a a" if i % 2 else "b b b") for i in range(20)}
    labels = {f"d{i}": ("A" if i % 2 else "B") for i in range(20)}
    train, score = split_documents(list(texts), seed=0)
    artefact = train_single_label_classifier(
        texts, labels, task_name="t", train_ids=train, score_ids=score, corpus="fixture", min_df=1,
    )
    path = save_artefact(artefact, tmp_path / "t.pkl")
    again = load_artefact(path)

    assert again.scorer.name == artefact.scorer.name
    assert again.score_doc_ids == artefact.score_doc_ids
    sidecar = json.loads((tmp_path / "t.json").read_text())
    assert sidecar["scorer"] == artefact.scorer.name
    assert sidecar["scored_on"] == len(artefact.score_doc_ids)
    assert "scikit-learn" in sidecar["versions"]


# --------------------------------------------------------------------------------- cross-fitting


def test_folds_are_document_disjoint_and_cover_everything() -> None:
    from pseudonymkit.tasks.linear import split_folds

    ids = [f"d{i}" for i in range(23)]
    folds = split_folds(ids, k=5, seed=0)
    assert len(folds) == 5
    flat = [d for fold in folds for d in fold]
    assert sorted(flat) == sorted(ids)
    assert len(flat) == len(set(flat))


def test_folds_depend_on_the_seed_not_on_the_input_order() -> None:
    from pseudonymkit.tasks.linear import split_folds

    ids = [f"d{i}" for i in range(20)]
    assert split_folds(ids, seed=0) == split_folds(list(reversed(ids)), seed=0)
    assert split_folds(ids, seed=0) != split_folds(ids, seed=1)


def test_one_fold_is_refused_there_is_nothing_to_hold_out() -> None:
    from pseudonymkit.tasks.linear import split_folds

    with pytest.raises(ValueError, match="at least two folds"):
        split_folds(["a", "b"], k=1)


def test_the_crossfit_name_carries_the_fold_count_and_one_fingerprint() -> None:
    from pseudonymkit.tasks.linear import CrossFit

    cross = CrossFit(scorers=(1, 2, 3), folds=(("a",), ("b",), ("c",)),
                     task_name="t", fingerprint="dead99")
    assert cross.name == "linear:tfidf-lr/t@3fold-dead99"
    assert cross.documents() == ("a", "b", "c")
    assert cross.fold_of("b") == 1
    with pytest.raises(KeyError):
        cross.fold_of("zzz")


def test_a_crossfit_classifier_scores_every_document_out_of_fold() -> None:
    pytest.importorskip("sklearn", reason="scikit-learn is the optional `tasks` extra")
    from pseudonymkit.tasks.linear import cross_fit_single_label_classifier, split_folds

    texts = {f"d{i}": ("fieber husten schnupfen" if i % 2 else "ramipril aspirin dosis")
             for i in range(40)}
    labels = {f"d{i}": ("anamnese" if i % 2 else "medikation") for i in range(40)}
    folds = split_folds(list(texts), k=5, seed=0)

    artefact = cross_fit_single_label_classifier(
        texts, labels, task_name="section_classification", folds=folds, corpus="fixture",
        features=None, regularisation=1.0,
    )
    # Every document is scored, which is the whole reason for cross-fitting.
    assert len(artefact.score_doc_ids) == 40
    assert artefact.metadata["scored_units"] == 40
    assert artefact.metadata["cross_fitted"] == 5
    assert artefact.holdout_score == 1.0
    assert artefact.train_doc_ids == ()
    assert "5fold-" in artefact.scorer.name


def test_a_crossfit_tagger_scores_every_document_that_carries_gold() -> None:
    pytest.importorskip("sklearn", reason="scikit-learn is the optional `tasks` extra")
    from pseudonymkit.tasks.linear import cross_fit_span_tagger, split_folds

    texts, spans = {}, {}
    for i in range(40):
        text = f"Patient {i} nimmt Ramipril taeglich."
        texts[f"d{i}"] = text
        start = text.index("Ramipril")
        spans[f"d{i}"] = [(start, start + len("Ramipril"), "DRUG")]
    folds = split_folds(list(texts), k=5, seed=0)

    artefact = cross_fit_span_tagger(
        texts, spans, folds=folds, corpus="fixture", classes=["DRUG"])
    assert artefact.metadata["scored_documents"] == 40
    assert artefact.holdout_score == 1.0


def test_a_crossfit_artefact_round_trips_and_names_its_features(tmp_path) -> None:
    pytest.importorskip("sklearn", reason="scikit-learn is the optional `tasks` extra")
    import json

    from pseudonymkit.tasks.linear import (
        Features, cross_fit_single_label_classifier, load_artefact, save_artefact, split_folds,
    )

    texts = {f"d{i}": ("a a a" if i % 2 else "b b b") for i in range(20)}
    labels = {f"d{i}": ("A" if i % 2 else "B") for i in range(20)}
    features = Features(word_ngrams=(1, 2), char_ngrams=(3, 4), min_df=1)
    artefact = cross_fit_single_label_classifier(
        texts, labels, task_name="t", folds=split_folds(list(texts), k=4, seed=0),
        corpus="fixture", features=features,
    )
    path = save_artefact(artefact, tmp_path / "t.pkl")
    again = load_artefact(path)

    assert again.scorer.name == artefact.scorer.name
    assert len(again.scorer.scorers) == 4
    sidecar = json.loads((tmp_path / "t.json").read_text())
    assert sidecar["features"] == {"word_ngrams": [1, 2], "char_ngrams": [3, 4], "min_df": 1,
                                  "max_features": 200_000, "sublinear_tf": True}


def test_a_char_ngram_feature_set_unions_two_vectorisers() -> None:
    pytest.importorskip("sklearn", reason="scikit-learn is the optional `tasks` extra")
    from pseudonymkit.tasks.linear import Features, build_vectoriser

    word_only = build_vectoriser(Features(min_df=1))
    both = build_vectoriser(Features(char_ngrams=(3, 4), min_df=1))
    rows = ["alpha beta", "gamma delta", "alpha gamma"]
    assert both.fit_transform(rows).shape[1] > word_only.fit_transform(rows).shape[1]
