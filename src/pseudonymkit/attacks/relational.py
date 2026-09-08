"""A3 and A5 — re-identifying an entity from the facts and relations around it.

Pseudonymisation removes the name and leaves the profile.  These two attacks recover identity from
what is left, and they differ in exactly one respect:

* **A3** compares profiles with a **fixed** similarity — the classical structural baseline.
* **A5** *learns* the similarity, on entities it never sees again — the strongest adversary we build.

They share :mod:`pseudonymkit.attacks.profiles`, so **the A5 − A3 gap is attributable to the
learning** and not to a different representation.  That gap is the study's "frozen defenders,
trained attackers" principle expressed as a number.

A5 is the text analogue of Packhäuser et al., *Deep learning-based patient re-identification is able
to exploit the biometric nature of medical chest X-ray data* (Sci Rep 2022,
``10.1038/s41598-022-19045-3``): a learned embedding decides whether two records belong to the same
individual, and shows that data believed de-identified is not.  The metrics are the
re-identification literature's — Rank-1, Rank-5, mAP — so the numbers sit directly beside it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from .profiles import EntityProfile

__all__ = ["ReIdResult", "StructuralLinkage", "LearnedLinkage", "featurise"]


@dataclass(frozen=True, slots=True)
class ReIdResult:
    """Re-identification performance, in the metrics the imaging literature uses."""

    attack: str
    policy: str
    technique: str
    queries: int
    gallery: int
    rank1: float
    rank5: float
    mean_average_precision: float
    notes: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "attack": self.attack, "policy": self.policy, "technique": self.technique,
            "queries": self.queries, "gallery": self.gallery, "rank1": self.rank1,
            "rank5": self.rank5, "mAP": self.mean_average_precision, "notes": self.notes,
        }


def _vocabulary(profiles: Sequence[Mapping[str, EntityProfile]], top: int) -> list[str]:
    counts: dict[str, int] = {}
    for group in profiles:
        for profile in group.values():
            for term, n in profile.context.items():
                counts[term] = counts.get(term, 0) + n
    return [t for t, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top]]


def featurise(
    profiles: Mapping[str, EntityProfile], vocabulary: Sequence[str]
) -> tuple[list[str], np.ndarray]:
    """Profiles -> L2-normalised feature matrix.

    Context terms dominate the representation because they are what pseudonymisation leaves
    untouched; four structural features are appended so the purely relational signal is available
    too.  Counts are log-damped, since an entity mentioned a thousand times should not be a thousand
    times more similar to everything.
    """
    index = {term: i for i, term in enumerate(vocabulary)}
    keys = sorted(profiles)
    matrix = np.zeros((len(keys), len(vocabulary) + 4), dtype=np.float32)
    for row, key in enumerate(keys):
        profile = profiles[key]
        for term, n in profile.context.items():
            col = index.get(term)
            if col is not None:
                matrix[row, col] = np.log1p(n)
        tail = len(vocabulary)
        matrix[row, tail + 0] = np.log1p(profile.mentions)
        matrix[row, tail + 1] = np.log1p(len(profile.documents))
        matrix[row, tail + 2] = np.log1p(profile.degree)
        matrix[row, tail + 3] = np.log1p(sum(profile.neighbours.values()))
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return keys, matrix / np.maximum(norms, 1e-9)


def _score(
    queries: Mapping[str, EntityProfile],
    gallery: Mapping[str, EntityProfile],
    truth: Mapping[str, str],
    weights: np.ndarray | None,
    vocabulary: Sequence[str],
    attack: str,
    policy: str,
    technique: str,
    notes: str = "",
) -> ReIdResult:
    q_keys, q_matrix = featurise(queries, vocabulary)
    g_keys, g_matrix = featurise(gallery, vocabulary)
    if weights is not None:
        q_matrix = q_matrix * weights
        g_matrix = g_matrix * weights
        q_matrix /= np.maximum(np.linalg.norm(q_matrix, axis=1, keepdims=True), 1e-9)
        g_matrix /= np.maximum(np.linalg.norm(g_matrix, axis=1, keepdims=True), 1e-9)

    scorable = [(i, truth[k]) for i, k in enumerate(q_keys) if k in truth and truth[k] in set(g_keys)]
    if not scorable or not g_keys:
        return ReIdResult(attack, policy, technique, 0, len(g_keys), 0.0, 0.0, 0.0,
                          notes="no scorable queries")

    gallery_index = {k: i for i, k in enumerate(g_keys)}
    similarity = q_matrix @ g_matrix.T
    order = np.argsort(-similarity, axis=1)

    rank1 = rank5 = 0
    average_precisions = []
    for row, gold in scorable:
        target = gallery_index[gold]
        rank = int(np.where(order[row] == target)[0][0]) + 1
        rank1 += rank == 1
        rank5 += rank <= 5
        average_precisions.append(1.0 / rank)
    n = len(scorable)
    return ReIdResult(
        attack=attack, policy=policy, technique=technique, queries=n, gallery=len(g_keys),
        rank1=rank1 / n, rank5=rank5 / n,
        mean_average_precision=float(np.mean(average_precisions)), notes=notes,
    )


class StructuralLinkage:
    """A3 — fixed cosine similarity over the shared profile representation.

    No training, no tuning: the classical baseline against which the learned attacker is measured.
    """

    name = "a3_structural"
    requires_unkeyed = False

    def __init__(self, vocabulary_size: int = 20_000) -> None:
        self._vocabulary_size = vocabulary_size

    def run(
        self,
        queries: Mapping[str, EntityProfile],
        gallery: Mapping[str, EntityProfile],
        truth: Mapping[str, str],
        policy: str,
        technique: str,
    ) -> ReIdResult:
        vocabulary = _vocabulary([queries, gallery], self._vocabulary_size)
        return _score(queries, gallery, truth, None, vocabulary, self.name, policy, technique,
                      notes="fixed cosine, no training")


class LearnedLinkage:
    """A5 — a learned diagonal metric over the same features.

    Trained by a contrastive objective: for a held-out *training* set of entities, push a query
    towards its own gallery entry and away from the hardest wrong one.  The learned object is a
    per-feature weight vector, which is the smallest thing that can be called a learned metric and
    is enough to show what learning buys; it trains on CPU in seconds and adds no dependency beyond
    numpy.

    **Entities are disjoint between training and evaluation.**  An attacker evaluated on the
    entities it trained on measures memorisation, not attack strength, and would not be an attack at
    all.
    """

    name = "a5_learned"
    requires_unkeyed = False

    def __init__(
        self,
        vocabulary_size: int = 20_000,
        train_fraction: float = 0.5,
        epochs: int = 30,
        learning_rate: float = 0.5,
        seed: int = 0,
    ) -> None:
        self._vocabulary_size = vocabulary_size
        self._train_fraction = train_fraction
        self._epochs = epochs
        self._learning_rate = learning_rate
        self._seed = seed

    def run(
        self,
        queries: Mapping[str, EntityProfile],
        gallery: Mapping[str, EntityProfile],
        truth: Mapping[str, str],
        policy: str,
        technique: str,
    ) -> ReIdResult:
        vocabulary = _vocabulary([queries, gallery], self._vocabulary_size)
        pairs = [(q, g) for q, g in truth.items() if q in queries and g in gallery]
        rng = np.random.default_rng(self._seed)
        rng.shuffle(pairs)  # type: ignore[arg-type]
        cut = int(len(pairs) * self._train_fraction)
        train, test = pairs[:cut], pairs[cut:]
        if len(train) < 4 or len(test) < 2:
            return ReIdResult(self.name, policy, technique, 0, len(gallery), 0.0, 0.0, 0.0,
                              notes="too few entities for a disjoint split")

        weights = self._fit(train, queries, gallery, vocabulary, rng)
        eval_queries = {q: queries[q] for q, _ in test}
        eval_gallery = {g: gallery[g] for _, g in test}
        eval_truth = dict(test)
        return _score(
            eval_queries, eval_gallery, eval_truth, weights, vocabulary,
            self.name, policy, technique,
            notes=(f"trained on {len(train)} entities, evaluated on {len(test)} disjoint ones"),
        )

    def _fit(
        self,
        train: Sequence[tuple[str, str]],
        queries: Mapping[str, EntityProfile],
        gallery: Mapping[str, EntityProfile],
        vocabulary: Sequence[str],
        rng: np.random.Generator,
    ) -> np.ndarray:
        q_keys, q_matrix = featurise({q: queries[q] for q, _ in train}, vocabulary)
        g_keys, g_matrix = featurise({g: gallery[g] for _, g in train}, vocabulary)
        q_row = {k: i for i, k in enumerate(q_keys)}
        g_row = {k: i for i, k in enumerate(g_keys)}

        weights = np.ones(q_matrix.shape[1], dtype=np.float32)
        for _ in range(self._epochs):
            gradient = np.zeros_like(weights)
            for q, g in train:
                anchor = q_matrix[q_row[q]]
                positive = g_matrix[g_row[g]]
                scores = (g_matrix * weights) @ (anchor * weights)
                scores[g_row[g]] = -np.inf
                hardest = g_matrix[int(np.argmax(scores))]
                # Raise the weight of features the true pair shares, lower those the impostor shares.
                gradient += anchor * positive - anchor * hardest
            weights += self._learning_rate * gradient / max(len(train), 1)
            np.clip(weights, 0.0, None, out=weights)
        return weights
