"""Trained-and-frozen linear scorers for the utility tasks (paper 2, plan §8.5).

**Why these replace the zero-shot gateway scorers** (AM, 2026-09-29).  :mod:`.models` scores the
classification and span tasks by prompting a gateway model.  That was the binding constraint on the
whole second study and it was weak on its own terms: ``base.py`` promises *frozen* models and a
gateway deployment can be updated under us; prompting a foundation model imports the memorisation
confound the plan warns about into the measuring instrument itself; and at roughly three hours per
operating point it put "utility at every point" at about one and a half years per corpus.  A
TF-IDF vectoriser and a logistic regression fitted once, pickled, and loaded back are genuinely
frozen, reproducible from the artefact, free, and cheap enough to run at **every** point rather
than at a dozen.

**What is kept from the old protocol.**  The ports are unchanged — these implement
:class:`~.base.SingleLabelClassifier` and :class:`~.base.SpanExtractor`, so every runner in
:mod:`.runners` drives them without modification and the per-document score vector is the same
artefact it always was.  The closed label set is still supplied by the runner at call time and the
answer is still restricted to it, exactly as the prompted classifier restricted the model's reply.

**The split, and why there has to be one.**  A scorer trained on a document and then asked to score
that same document measures memorisation, not utility: it would be near-perfect on condition A and
would lose points under B and C for having been shown different strings, which reads as a utility
loss caused by pseudonymisation when it is caused by the instrument.  This is the rule the attack
side already states — ``LearnedLinkage``: *"An attacker evaluated on the entities it trained on
measures memorisation, not attack strength"* — and it applies here for the same reason.  So the
instrument is fitted on a **document-disjoint training half of condition A** and every condition is
scored on the complement.  The split is seeded, stored inside the artefact, and recorded in the
result row, so the scored document set is identical in A, B and C and the pairing §8.3 requires
survives.

**Nothing is fitted per condition.**  One artefact scores A, B and C.  Refitting under B would turn
the measurement into a fit, which is the same objection :mod:`.models` raises against tuning a
prompt after seeing a condition's scores.

**The instrument's own ceiling is a reported number, not an assumption.**  ``train_*`` returns the
held-out condition-A score beside the model.  Paper 1 had to drop ``medication_ie:in_narrative``
because the frozen scorer was near chance on the *original* text and therefore could not measure a
loss; that check is made here before anything is scored, rather than discovered afterwards.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import platform
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "TfidfLogisticClassifier",
    "TfidfLogisticTagger",
    "Artefact",
    "CrossFit",
    "Features",
    "build_vectoriser",
    "cross_fit_single_label_classifier",
    "cross_fit_span_tagger",
    "split_folds",
    "bio_tags",
    "decode_bio",
    "split_documents",
    "token_features",
    "tokenise",
    "train_single_label_classifier",
    "train_span_tagger",
    "load_artefact",
    "save_artefact",
]

TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
"""Tokens carry character offsets, so punctuation is its own token rather than glued to a word.

Medication gold marks strings like ``5 mg`` and ``1-0-1``; a whitespace tokeniser cannot produce a
boundary inside those and the tagger could then never match a gold span exactly, which is what
:func:`pseudonymkit.metrics.utility.span_f1` scores.
"""

_FEATURE_TOKEN = r"\S+"
"""The per-token feature strings are space-separated, so the vectoriser must not split on anything
else: a feature is ``suf3=rin``, and the default word pattern would tear it into two."""


# -------------------------------------------------------------------------------- the feature set


@dataclass(frozen=True)
class Features:
    """Which TF-IDF features a classifier is fitted on, as one recordable object.

    The default is word unigrams, which is what the first fit used. It is enough for CARDIO:DE's
    fourteen section types (0.9605) and **not** enough for Enron's folder task, where it reached
    0.2530 against a majority-class baseline of 0.2621 — an instrument below the rate of answering
    "All documents" every time, which §8.3 says cannot measure a loss.

    ``char_ngrams`` adds a second vectoriser over character n-grams inside word boundaries and
    unions the two feature spaces. For e-mail that is not a refinement but a different kind of
    evidence: a folder is signalled by addresses, signature blocks, quoted headers and spellings
    that a word tokeniser shatters. The two are unioned rather than swapped so a configuration can
    be compared against the unigram one it replaces.

    Every field lands in the artefact, so a result row says what its instrument was fitted on
    rather than what the module's defaults happened to be on the day.
    """

    word_ngrams: tuple[int, int] = (1, 1)
    char_ngrams: tuple[int, int] | None = None
    min_df: int = 2
    max_features: int = 200_000
    sublinear_tf: bool = True

    def describe(self) -> dict[str, object]:
        return {
            "word_ngrams": list(self.word_ngrams),
            "char_ngrams": list(self.char_ngrams) if self.char_ngrams else None,
            "min_df": self.min_df,
            "max_features": self.max_features,
            "sublinear_tf": self.sublinear_tf,
        }


def build_vectoriser(features: Features, token_pattern: str | None = None) -> Any:
    """The vectoriser for a feature set — one ``TfidfVectorizer``, or a union of two.

    ``token_pattern`` is for the span tagger, whose "documents" are space-separated feature
    strings like ``suf3=rin`` that the default word pattern would tear in two.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    word_kwargs: dict[str, Any] = dict(
        sublinear_tf=features.sublinear_tf, min_df=features.min_df,
        max_features=features.max_features, ngram_range=features.word_ngrams,
    )
    if token_pattern is not None:
        word_kwargs["token_pattern"] = token_pattern
    word = TfidfVectorizer(**word_kwargs)
    if not features.char_ngrams:
        return word

    from sklearn.pipeline import FeatureUnion

    char = TfidfVectorizer(
        analyzer="char_wb", ngram_range=features.char_ngrams, sublinear_tf=features.sublinear_tf,
        min_df=features.min_df, max_features=features.max_features,
    )
    return FeatureUnion([("word", word), ("char", char)])


# ------------------------------------------------------------------------------------- artefacts


@dataclass(frozen=True)
class Artefact:
    """A frozen scorer plus the provenance §13 requires on every row that quotes it.

    ``fingerprint`` is a digest of the pickled estimator, so two runs that quote the same scorer
    name are quoting the same weights.  It is part of :attr:`TfidfLogisticClassifier.name`, which
    means a result row cannot be read without saying which artefact produced it.
    """

    scorer: Any
    task: str
    corpus: str
    seed: int
    train_doc_ids: tuple[str, ...]
    score_doc_ids: tuple[str, ...]
    holdout_score: float
    metadata: Mapping[str, object] = field(default_factory=dict)

    def row(self) -> dict[str, object]:
        """What goes beside a score in the result file."""
        return {
            "scorer": self.scorer.name,
            "task": self.task,
            "corpus": self.corpus,
            "seed": self.seed,
            "trained_on": len(self.train_doc_ids),
            "scored_on": len(self.score_doc_ids),
            "holdout_condition_a": self.holdout_score,
            **dict(self.metadata),
        }


def _fingerprint(*objects: Any) -> str:
    """Eight hex characters over the pickled estimators — stable for identical weights."""
    digest = hashlib.sha256()
    for obj in objects:
        digest.update(pickle.dumps(obj, protocol=4))
    return digest.hexdigest()[:8]


def _versions() -> dict[str, str]:
    import numpy
    import scipy
    import sklearn

    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
    }


def save_artefact(artefact: Artefact, path: Path | str) -> Path:
    """Pickle the artefact and write a readable JSON sidecar beside it.

    The sidecar exists so the provenance can be read without unpickling — a result row cites the
    scorer name, and the reader must be able to see what that name covers without loading a model.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(artefact, protocol=4))
    sidecar = path.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {
                **artefact.row(),
                "train_doc_ids": list(artefact.train_doc_ids),
                "score_doc_ids": list(artefact.score_doc_ids),
            },
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def load_artefact(path: Path | str) -> Artefact:
    loaded = pickle.loads(Path(path).read_bytes())
    if not isinstance(loaded, Artefact):
        raise TypeError(f"{path} does not hold an Artefact but a {type(loaded).__name__}")
    return loaded


def split_documents(
    doc_ids: Sequence[str], *, seed: int = 0, train_fraction: float = 0.5
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Partition document ids into a training half and a scoring half.

    Document-disjoint, seeded, and sorted before shuffling so the split depends on the seed and the
    corpus, never on the order the adapter happened to yield.
    """
    import random

    unique = sorted(set(doc_ids))
    rng = random.Random(seed)
    rng.shuffle(unique)
    cut = int(len(unique) * train_fraction)
    return tuple(sorted(unique[:cut])), tuple(sorted(unique[cut:]))


# --------------------------------------------------------------------------- single-label scorer


@dataclass
class TfidfLogisticClassifier:
    """A frozen TF-IDF + logistic regression behind the single-label port.

    Section classification (CARDIO:DE) and folder classification (Enron).  ``classify`` is given the
    closed set by the runner and answers from it: a class the model knows but the runner did not
    offer is masked out before the argmax, and an empty intersection returns ``""`` — the same
    "answered off-list, therefore wrong" outcome :class:`~.models.LlmSingleLabelClassifier`
    produces, so the two instruments fail the same way.
    """

    vectoriser: Any
    model: Any
    task_name: str
    fingerprint: str = ""
    max_chars: int = 12_000
    """Matches ``_LlmModel.max_chars``.  It is applied identically in every condition, so it cannot
    bias the comparison, and keeping the two instruments on the same document budget is what lets a
    linear number be read beside a prompted one."""

    @property
    def name(self) -> str:
        return f"linear:tfidf-lr/{self.task_name}@{self.fingerprint or 'unfitted'}"

    def classify(self, text: str, labels: Sequence[str]) -> str:
        offered = list(labels)
        if not offered:
            return ""
        known = list(self.model.classes_)
        allowed = [index for index, label in enumerate(known) if label in set(offered)]
        if not allowed:
            return ""
        scores = self._scores(text[: self.max_chars], len(known))
        best = max(allowed, key=lambda index: (scores[index], -index))
        return str(known[best])

    def _scores(self, text: str, n_classes: int) -> Sequence[float]:
        """Decision values per class, with the binary case widened to two columns.

        ``LogisticRegression.decision_function`` returns one column for two classes and one per
        class above that.  A two-label corpus is a real possibility here — an Enron folder set can
        collapse that far on a small sample — and silently indexing a 1-D array by class would read
        the wrong column rather than fail.
        """
        import numpy as np

        values = np.atleast_2d(self.model.decision_function(self.vectoriser.transform([text])))
        if values.shape[1] == 1 and n_classes == 2:
            column = values[:, 0]
            values = np.column_stack([-column, column])
        return [float(v) for v in values[0]]


def _fit_classifier(
    texts: Mapping[str, str],
    labels: Mapping[str, str],
    train: Sequence[str],
    *,
    task_name: str,
    seed: int,
    features: Features,
    regularisation: float,
    class_weight: str | None,
) -> TfidfLogisticClassifier:
    """Fit one vectoriser and one logistic regression on ``train``, and freeze them.

    Shared by the single-split and the cross-fitted paths so a fold's estimator cannot drift from
    the estimator the single-split diagnostic measured.
    """
    from sklearn.linear_model import LogisticRegression

    vectoriser = build_vectoriser(features)
    matrix = vectoriser.fit_transform([texts[i] for i in train])
    model = LogisticRegression(max_iter=2_000, random_state=seed, C=regularisation,
                               class_weight=class_weight)
    model.fit(matrix, [labels[i] for i in train])
    return TfidfLogisticClassifier(
        vectoriser=vectoriser, model=model, task_name=task_name,
        fingerprint=_fingerprint(vectoriser, model),
    )


def train_single_label_classifier(
    texts: Mapping[str, str],
    labels: Mapping[str, str],
    *,
    task_name: str,
    train_ids: Sequence[str],
    score_ids: Sequence[str],
    corpus: str,
    seed: int = 0,
    features: Features | None = None,
    regularisation: float = 1.0,
    class_weight: str | None = "balanced",
    record_ids: tuple[Sequence[str], Sequence[str]] | None = None,
) -> Artefact:
    """Fit on the training half of **condition A** and report the held-out condition-A score.

    ``texts`` and ``labels`` are keyed by the **training unit**, and ids missing a label are
    dropped from both halves and counted, because a unit with no gold can neither train nor score.

    ``class_weight`` is the one fitting choice that is not neutral, and it has to be made per task
    rather than once. Weighting the classes equally is right where the label set is small and the
    instrument should not simply learn the head -- CARDIO:DE's fourteen section types. It is wrong
    where the tail is long and the metric is accuracy: Enron's folder task has 176 labels of which
    32 hold one message each, and balancing them pulled the held-out accuracy down to 0.2028
    against a majority-class baseline of 0.2621, i.e. below the rate of answering "All documents"
    every time. An instrument under its own free baseline cannot measure a loss (§8.3), so the
    choice is recorded in the artefact rather than left implicit.

    The unit is not always the document.  Section classification fits on *sections* — the runner
    classifies each derived section of a letter and scores the letter by how many it got right — so
    its keys are section keys.  ``record_ids`` then carries the **document-level** split, because
    that is what the runner has to filter on: the scored document set must be identical in A, B and
    C for the pairing to survive, and it is documents that are paired.
    """
    features = features or Features()

    def usable(ids: Sequence[str]) -> list[str]:
        return [i for i in ids if texts.get(i) and labels.get(i)]

    train, score = usable(train_ids), usable(score_ids)
    if len({labels[i] for i in train}) < 2:
        raise ValueError(
            f"{task_name}: the training half carries "
            f"{len({labels[i] for i in train})} distinct labels; a classifier needs two"
        )

    scorer = _fit_classifier(texts, labels, train, task_name=task_name, seed=seed,
                             features=features, regularisation=regularisation,
                             class_weight=class_weight)
    offered = sorted({labels[i] for i in list(train) + list(score)})
    correct = sum(scorer.classify(texts[i], offered) == labels[i] for i in score)
    # **The baseline is the majority class, not 1/k.**  §8.3's "near chance on the original" test
    # needs the rate a scorer gets for free, and on a skewed label set that is far above uniform:
    # Enron's folder task is 176 labels of which one holds 26 % of the messages, so a classifier at
    # 0.20 is *worse* than answering "All documents" every time while looking eight times chance.
    majority = 0.0
    if score:
        counts: dict[str, int] = {}
        for i in score:
            counts[labels[i]] = counts.get(labels[i], 0) + 1
        majority = max(counts.values()) / len(score)
    recorded = (
        (tuple(record_ids[0]), tuple(record_ids[1])) if record_ids
        else (tuple(train), tuple(score))
    )
    return Artefact(
        scorer=scorer, task=task_name, corpus=corpus, seed=seed,
        train_doc_ids=recorded[0], score_doc_ids=recorded[1],
        holdout_score=correct / len(score) if score else 0.0,
        metadata={
            "kind": "single-label",
            "features": features.describe(),
            "regularisation": regularisation,
            "unit": "document" if record_ids is None else "section",
            "holdout_metric": "accuracy over the scored units",
            # The runner's per-letter score averages over a letter's sections first; this is the
            # flat unit accuracy, which is the instrument's own ceiling rather than the task's.
            "chance": 1.0 / len(offered) if offered else 0.0,
            "majority_baseline": majority,
            "class_weight": class_weight,
            "train_units": len(train),
            "scored_units": len(score),
            "labels": len(offered),
            "dropped_no_label": len(train_ids) + len(score_ids) - len(train) - len(score),
            "versions": _versions(),
        },
    )


# ----------------------------------------------------------------------------- span tagger (BIO)


def tokenise(text: str) -> list[tuple[int, int, str]]:
    """``(start, end, surface)`` for every token, as character offsets into ``text``."""
    return [(m.start(), m.end(), m.group(0)) for m in TOKEN.finditer(text)]


def _shape(token: str) -> str:
    out = []
    for character in token[:8]:
        if character.isdigit():
            out.append("d")
        elif character.isupper():
            out.append("X")
        elif character.islower():
            out.append("x")
        else:
            out.append(character)
    return "".join(out)


def token_features(tokens: Sequence[tuple[int, int, str]], index: int) -> str:
    """One space-separated feature string per token, for the TF-IDF vectoriser.

    A feature *string* rather than a feature dict keeps the instrument literally what §8.5 names —
    TF-IDF over tokens, then logistic regression — and keeps the vectoriser picklable, which a
    custom analyser callable would not be.
    """
    surface = tokens[index][2]
    low = surface.casefold()
    previous = tokens[index - 1][2].casefold() if index else "<s>"
    following = tokens[index + 1][2].casefold() if index + 1 < len(tokens) else "</s>"
    parts = [
        f"w={low}",
        f"shape={_shape(surface)}",
        f"pre3={low[:3]}",
        f"suf3={low[-3:]}",
        f"suf2={low[-2:]}",
        f"prev={previous}",
        f"next={following}",
        f"bigram={previous}_{low}",
        f"isdigit={surface.isdigit()}",
        f"istitle={surface.istitle()}",
        f"isupper={surface.isupper()}",
    ]
    return " ".join(parts)


def bio_tags(
    tokens: Sequence[tuple[int, int, str]], spans: Iterable[tuple[int, int, str]]
) -> list[str]:
    """BIO tags for the tokens, from character-offset gold spans.

    A token belongs to a span when it overlaps it at all; a gold boundary that falls inside a token
    therefore claims that token, which is the only decodable choice and is reported through the
    exact-match F1 rather than hidden.
    """
    tags = ["O"] * len(tokens)
    for start, end, label in sorted(spans, key=lambda s: (s[0], s[1])):
        first = True
        for index, (t_start, t_end, _) in enumerate(tokens):
            if t_start < end and t_end > start:
                tags[index] = f"{'B' if first else 'I'}-{label}"
                first = False
    return tags


def decode_bio(
    tokens: Sequence[tuple[int, int, str]], tags: Sequence[str]
) -> list[tuple[int, int, str]]:
    """Contiguous ``B``/``I`` runs back into character spans.

    An ``I`` with no ``B`` before it opens a span rather than being dropped: the tagger is a
    per-token classifier with no transition model, so a stray ``I`` is its ordinary way of starting
    one, and dropping those would cost recall for a convention the model was never taught.
    """
    spans: list[tuple[int, int, str]] = []
    start = end = -1
    label = ""
    for (t_start, t_end, _), tag in zip(tokens, tags):
        kind, _, this = tag.partition("-")
        if kind == "O" or not this:
            if label:
                spans.append((start, end, label))
            label = ""
            continue
        if kind == "I" and label == this:
            end = t_end
            continue
        if label:
            spans.append((start, end, label))
        start, end, label = t_start, t_end, this
    if label:
        spans.append((start, end, label))
    return spans


@dataclass
class TfidfLogisticTagger:
    """A frozen per-token linear tagger behind the span port — CARDIO:DE medication IE.

    Scored by exact-match span F1 (``span_f1``), so the decoder has to reproduce gold's boundary
    conventions and not merely find the right words.  It can, because it is fitted on those gold
    spans; what it cannot do is invent a class the runner did not offer, and ``extract`` drops any
    such prediction rather than renaming it.
    """

    vectoriser: Any
    model: Any
    task_name: str = "medication_ie"
    fingerprint: str = ""
    max_chars: int = 12_000

    @property
    def name(self) -> str:
        return f"linear:tfidf-lr/{self.task_name}@{self.fingerprint or 'unfitted'}"

    def extract(self, text: str, classes: Sequence[str]) -> list[tuple[int, int, str]]:
        body = text[: self.max_chars]
        tokens = tokenise(body)
        if not tokens:
            return []
        features = [token_features(tokens, index) for index in range(len(tokens))]
        tags = list(self.model.predict(self.vectoriser.transform(features)))
        allowed = set(classes)
        return [span for span in decode_bio(tokens, tags) if span[2] in allowed]


def _fit_tagger(
    rows: Sequence[str],
    tags: Sequence[str],
    *,
    task_name: str,
    seed: int,
    features: Features,
    regularisation: float,
) -> TfidfLogisticTagger:
    """Fit the BIO tagger on per-token feature strings, and freeze it.

    ``class_weight`` is fixed at ``balanced`` here rather than exposed: the classes are BIO tags
    over tokens, where ``O`` is the overwhelming majority by construction rather than by the
    corpus, so it is not a judgement call the way it is for a label set.
    """
    from sklearn.linear_model import LogisticRegression

    vectoriser = build_vectoriser(features, token_pattern=_FEATURE_TOKEN)
    matrix = vectoriser.fit_transform(rows)
    model = LogisticRegression(max_iter=2_000, random_state=seed, C=regularisation,
                               class_weight="balanced")
    model.fit(matrix, list(tags))
    return TfidfLogisticTagger(
        vectoriser=vectoriser, model=model, task_name=task_name,
        fingerprint=_fingerprint(vectoriser, model),
    )


def train_span_tagger(
    texts: Mapping[str, str],
    spans: Mapping[str, Sequence[tuple[int, int, str]]],
    *,
    train_ids: Sequence[str],
    score_ids: Sequence[str],
    corpus: str,
    classes: Sequence[str],
    task_name: str = "medication_ie",
    seed: int = 0,
    features: Features | None = None,
    regularisation: float = 1.0,
) -> Artefact:
    """Fit the BIO tagger on the training half of condition A; report held-out span F1.

    The held-out score is the mean over documents of
    :func:`pseudonymkit.metrics.utility.span_f1`, which is exactly what the runner computes, so the
    number returned here is the instrument's own ceiling in the units the results are reported in.
    """
    from ..metrics.utility import span_f1

    features = features or Features(min_df=1, max_features=1_000_000)
    keep = set(classes)
    rows: list[str] = []
    tags: list[str] = []
    for doc_id in train_ids:
        text = texts.get(doc_id)
        if not text:
            continue
        tokens = tokenise(text)
        gold = [s for s in spans.get(doc_id, ()) if s[2] in keep]
        document_tags = bio_tags(tokens, gold)
        rows.extend(token_features(tokens, index) for index in range(len(tokens)))
        tags.extend(document_tags)
    if len(set(tags)) < 2:
        raise ValueError(f"{task_name}: the training half carries no gold span of any kept class")

    scorer = _fit_tagger(rows, tags, task_name=task_name, seed=seed, features=features,
                         regularisation=regularisation)
    scored_ids = [i for i in score_ids if texts.get(i) and spans.get(i)]
    held = [
        span_f1([s for s in spans[i] if s[2] in keep], scorer.extract(texts[i], list(classes)))
        for i in scored_ids
    ]
    return Artefact(
        scorer=scorer, task=task_name, corpus=corpus, seed=seed,
        train_doc_ids=tuple(train_ids), score_doc_ids=tuple(scored_ids),
        holdout_score=sum(held) / len(held) if held else 0.0,
        metadata={
            "kind": "bio-tagger",
            "holdout_metric": "mean exact-match span F1 over the scored documents",
            # Exact-match span F1 has no free baseline worth printing: a tagger that predicts
            # nothing scores 0 on every document that has gold. The reference is the gateway
            # extractor's own original-text score, which paper 1 measured at 0.371 +/- 0.182.
            "chance": None,
            "classes": len(keep),
            "tags": len(set(tags)),
            "train_tokens": len(rows),
            "features": features.describe(),
            "regularisation": regularisation,
            "versions": _versions(),
        },
    )

# ------------------------------------------------------------------------------------ cross-fitting


def split_folds(
    doc_ids: Sequence[str], *, k: int = 5, seed: int = 0
) -> tuple[tuple[str, ...], ...]:
    """Partition document ids into ``k`` document-disjoint folds.

    Sorted before shuffling, so the folds depend on the seed and the corpus and never on the order
    the adapter happened to yield.
    """
    import random

    if k < 2:
        raise ValueError(f"cross-fitting needs at least two folds, not {k}")
    unique = sorted(set(doc_ids))
    rng = random.Random(seed)
    rng.shuffle(unique)
    return tuple(tuple(sorted(unique[index::k])) for index in range(k))


@dataclass
class CrossFit:
    """One instrument made of ``k`` estimators and the fold each document belongs to.

    **Why cross-fitting rather than one held-out half** (AM, 2026-10-03). A scorer must not be
    asked to score a document it was fitted on — that measures memorisation, and under B and C it
    would read as a utility loss the pseudonymisation did not cause. A single 50/50 split obeys
    that by scoring only half the corpus, which halves *n* for every paired test. Cross-fitting
    obeys it while scoring **every** document: fold *f* is scored by the estimator fitted on the
    other *k−1* folds, so no document is ever seen by the model that scores it.

    **It is still one fixed instrument, which is what §8.3 requires.** The section promises "one
    fixed scorer model named in every result row". A cross-fitted estimator is a single frozen
    object: *k* sets of weights plus a fold assignment by document id. The assignment depends on
    the corpus and the seed and **not** on the condition, so the same weights score A, B and C for
    any given document — which is the property that makes a difference between conditions
    attributable to the condition. :attr:`name` carries one fingerprint over all *k* estimators,
    so two rows quoting the same name are quoting the same instrument.

    The port is not implemented here on purpose. ``classify`` and ``extract`` take text and no
    document id, so a :class:`CrossFit` cannot know which estimator to use; the caller scores
    fold by fold with :meth:`scorer_for` and concatenates. That is exactly as cheap as one pass,
    because each fold's estimator only scores its own fold.
    """

    scorers: tuple[Any, ...]
    folds: tuple[tuple[str, ...], ...]
    task_name: str
    fingerprint: str = ""

    @property
    def name(self) -> str:
        return (f"linear:tfidf-lr/{self.task_name}@{len(self.scorers)}fold-"
                f"{self.fingerprint or 'unfitted'}")

    def scorer_for(self, fold: int) -> Any:
        return self.scorers[fold]

    def fold_of(self, doc_id: str) -> int:
        for index, members in enumerate(self.folds):
            if doc_id in members:
                return index
        raise KeyError(f"{doc_id} is in none of the {len(self.folds)} folds")

    def documents(self) -> tuple[str, ...]:
        return tuple(sorted(d for fold in self.folds for d in fold))


def _pooled(scores: Sequence[float]) -> float:
    return sum(scores) / len(scores) if scores else 0.0


def cross_fit_single_label_classifier(
    texts: Mapping[str, str],
    labels: Mapping[str, str],
    *,
    task_name: str,
    folds: Sequence[Sequence[str]],
    corpus: str,
    seed: int = 0,
    features: Features | None = None,
    regularisation: float = 1.0,
    class_weight: str | None = "balanced",
    units_of: Any = None,
) -> Artefact:
    """Cross-fit a single-label classifier over document folds; score every document out of fold.

    ``folds`` are **document** ids. ``units_of`` maps a set of document ids to the unit keys of
    ``texts``/``labels`` for those documents, and exists because the unit is not always the
    document: section classification fits on sections. Without it the unit keys are the document
    ids themselves.

    The reported score is pooled over every unit, each scored by the estimator that never saw its
    document — so it covers the whole corpus and is still honest.
    """
    features = features or Features()
    folds = [tuple(f) for f in folds]
    unit_keys = units_of or (lambda ids: [i for i in ids if i in texts])

    scorers: list[Any] = []
    offered = sorted({v for v in labels.values() if v})
    per_unit: list[float] = []
    gold: list[str] = []

    for index, fold in enumerate(folds):
        rest = [d for other, members in enumerate(folds) if other != index for d in members]
        train = [i for i in unit_keys(rest) if texts.get(i) and labels.get(i)]
        score = [i for i in unit_keys(fold) if texts.get(i) and labels.get(i)]
        if len({labels[i] for i in train}) < 2:
            raise ValueError(
                f"{task_name}: fold {index} leaves "
                f"{len({labels[i] for i in train})} distinct labels to train on; a classifier "
                f"needs two"
            )
        scorer = _fit_classifier(texts, labels, train, task_name=task_name, seed=seed,
                                 features=features, regularisation=regularisation,
                                 class_weight=class_weight)
        scorers.append(scorer)
        for key in score:
            per_unit.append(float(scorer.classify(texts[key], offered) == labels[key]))
            gold.append(labels[key])

    counts: dict[str, int] = {}
    for label in gold:
        counts[label] = counts.get(label, 0) + 1
    majority = (max(counts.values()) / len(gold)) if gold else 0.0

    cross = CrossFit(scorers=tuple(scorers), folds=tuple(folds), task_name=task_name,
                     fingerprint=_fingerprint(*scorers))
    return Artefact(
        scorer=cross, task=task_name, corpus=corpus, seed=seed,
        train_doc_ids=(),          # every document trains k-1 of the k estimators; see `folds`
        score_doc_ids=cross.documents(),
        holdout_score=_pooled(per_unit),
        metadata={
            "kind": "single-label",
            "cross_fitted": len(folds),
            "fold_sizes": [len(f) for f in folds],
            "unit": "document" if units_of is None else "section",
            "holdout_metric": "out-of-fold accuracy over every scored unit",
            "chance": 1.0 / len(offered) if offered else 0.0,
            "majority_baseline": majority,
            "scored_units": len(per_unit),
            "labels": len(offered),
            "features": features.describe(),
            "regularisation": regularisation,
            "class_weight": class_weight,
            "versions": _versions(),
        },
    )


def cross_fit_span_tagger(
    texts: Mapping[str, str],
    spans: Mapping[str, Sequence[tuple[int, int, str]]],
    *,
    folds: Sequence[Sequence[str]],
    corpus: str,
    classes: Sequence[str],
    task_name: str = "medication_ie",
    seed: int = 0,
    features: Features | None = None,
    regularisation: float = 1.0,
) -> Artefact:
    """Cross-fit the BIO tagger over document folds; score every document out of fold.

    The reported score is the mean of :func:`pseudonymkit.metrics.utility.span_f1` over every
    document that carries gold, each scored by the estimator that never saw it — the same metric
    the runner computes, so the number is the instrument's ceiling in the units of the results.
    """
    from ..metrics.utility import span_f1

    features = features or Features(min_df=1, max_features=1_000_000)
    folds = [tuple(f) for f in folds]
    keep = set(classes)
    scorers: list[Any] = []
    held: list[float] = []

    for index, fold in enumerate(folds):
        rest = [d for other, members in enumerate(folds) if other != index for d in members]
        rows: list[str] = []
        tags: list[str] = []
        for doc_id in rest:
            text = texts.get(doc_id)
            if not text:
                continue
            tokens = tokenise(text)
            rows.extend(token_features(tokens, position) for position in range(len(tokens)))
            tags.extend(bio_tags(tokens, [s for s in spans.get(doc_id, ()) if s[2] in keep]))
        if len(set(tags)) < 2:
            raise ValueError(
                f"{task_name}: fold {index} leaves no gold span of any kept class to train on")
        scorer = _fit_tagger(rows, tags, task_name=task_name, seed=seed, features=features,
                             regularisation=regularisation)
        scorers.append(scorer)
        del rows, tags
        for doc_id in fold:
            text = texts.get(doc_id)
            gold = [s for s in spans.get(doc_id, ()) if s[2] in keep]
            if not text or not gold:
                continue
            held.append(span_f1(gold, scorer.extract(text, list(classes))))

    cross = CrossFit(scorers=tuple(scorers), folds=tuple(folds), task_name=task_name,
                     fingerprint=_fingerprint(*scorers))
    return Artefact(
        scorer=cross, task=task_name, corpus=corpus, seed=seed,
        train_doc_ids=(),
        score_doc_ids=cross.documents(),
        holdout_score=_pooled(held),
        metadata={
            "kind": "bio-tagger",
            "cross_fitted": len(folds),
            "fold_sizes": [len(f) for f in folds],
            "holdout_metric": "mean out-of-fold exact-match span F1",
            "chance": None,
            "classes": len(keep),
            "scored_documents": len(held),
            "features": features.describe(),
            "regularisation": regularisation,
            "versions": _versions(),
        },
    )
