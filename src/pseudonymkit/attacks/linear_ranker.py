"""A4's statistical twin: TF-IDF and logistic regression over the same candidate lists.

AM, 2026-09-29. It does not replace :class:`LlmCandidateRanker` and must not be read as a
substitute for it. A linear ranker over context features is A5 with a different similarity, and it
sees near-identical features under B and C because only the replaced span differs -- so on its own
the surrogate-versus-placeholder contrast, which is the paper's central question, would go
unmeasured. What the pair buys is the question a reviewer asks first: *how much does the LLM add
over a linear model on identical inputs?*

Its second job is to be cheap enough to run at all 2,154 operating points, so its score can
stratify the 1 % sample at which the LLM is actually run (plan §8.5c).

No gateway, no GPU, deterministic given a seed.

**It is never trained on condition A** (AM, 2026-09-29). An earlier draft of this module fitted on
condition-A items, which hands the attacker the defender's original text -- knowledge no attacker
has. It trains on the **released** text under the condition being attacked, with **entities
disjoint between training and evaluation**, which is the discipline `LearnedLinkage` already
states: *"An attacker evaluated on the entities it trained on measures memorisation, not attack
strength, and would not be an attack at all."* One model per (corpus, condition, fold), so the
B and C rankers are different models over different text, as they must be.

Condition A remains in the study as the **ceiling** -- what the attack recovers with nothing
replaced -- because without it a rate on B or C has no scale (`experiment_plan.md`:593). That is a
reference measurement, not attacker knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .candidates import CandidateSet

__all__ = ["LinearCandidateRanker", "train_linear_ranker"]

_TOKEN = r"(?u)\b\w\w+\b"


@dataclass
class LinearCandidateRanker:
    """Ranks candidates by a logistic model over document/candidate feature overlap.

    The features are deliberately the ones a linear model can see: character and word n-grams of
    the marked document and of each candidate's auxiliary context, reduced to their cosine, plus
    the candidate's surface frequency in the corpus. Nothing here reads the marked span itself,
    which is exactly why it is blind to the B/C difference and why the LLM is kept.
    """

    vectoriser: object
    model: object
    name: str = "linear-tfidf-lr"
    seed: int = 0
    _fallback: bool = field(default=False, repr=False)

    def features(self, item: CandidateSet) -> np.ndarray:
        doc = self.vectoriser.transform([item.text])
        contexts = [c.context or c.surface for c in item.candidates]
        cand = self.vectoriser.transform(contexts)
        cosine = np.asarray((cand @ doc.T).todense()).ravel()
        length = np.array([len(c.context or "") for c in item.candidates], dtype=float)
        length = length / (length.max() or 1.0)
        return np.column_stack([cosine, length])

    def rank(self, item: CandidateSet) -> Sequence[int]:
        if not item.candidates:
            return []
        scores = self.model.decision_function(self.features(item))
        scores = np.atleast_1d(scores)
        # Ties broken by index so the ranking is deterministic and never accidentally favours the
        # true candidate, which build_items places first before shuffling.
        return list(np.lexsort((np.arange(len(scores)), -scores)))


def split_entities(items: Sequence[CandidateSet], *, seed: int = 0,
                   train_fraction: float = 0.5) -> tuple[list[CandidateSet], list[CandidateSet]]:
    """Partition items so no identity appears in both halves."""
    import random

    identities = sorted({i.truth for i in items})
    rng = random.Random(seed)
    rng.shuffle(identities)
    cut = int(len(identities) * train_fraction)
    train_ids = set(identities[:cut])
    train = [i for i in items if i.truth in train_ids]
    test = [i for i in items if i.truth not in train_ids]
    return train, test


def train_linear_ranker(items: Sequence[CandidateSet], *, seed: int = 0
                        ) -> LinearCandidateRanker:
    """Fit on RELEASED items -- the condition under attack, never condition A.

    Pass only the training half from :func:`split_entities`; evaluating on the entities it was
    fitted on would measure memorisation rather than attack strength.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    corpus_text = [i.text for i in items]
    corpus_text += [c.context or c.surface for i in items for c in i.candidates]
    vectoriser = TfidfVectorizer(token_pattern=_TOKEN, sublinear_tf=True, min_df=2,
                                 max_features=200_000)
    vectoriser.fit(corpus_text)

    ranker = LinearCandidateRanker(vectoriser=vectoriser, model=None, seed=seed)
    rows, labels = [], []
    for item in items:
        try:
            truth = item.truth_index
        except ValueError:
            continue
        feats = ranker.features(item)
        for index in range(len(item.candidates)):
            rows.append(feats[index])
            labels.append(1 if index == truth else 0)
    if not rows or len(set(labels)) < 2:
        raise ValueError("cannot train the linear ranker: no positive and negative examples")
    model = LogisticRegression(max_iter=1000, random_state=seed, class_weight="balanced")
    model.fit(np.vstack(rows), np.asarray(labels))
    ranker.model = model
    return ranker
