"""Five-fold cross-validation for the one trained component (AM, 2026-09-15).

A5 is "the only trained model in the study" (§8.4), so this is where cross-validation lands. What
makes it k-fold rather than repeated subsampling is that the k test sets partition the entities:
every entity is tested exactly once and trained on k-1 times, which is what lets the k results be
averaged.
"""

from __future__ import annotations

import pytest

from pseudonymkit.attacks.relational import LearnedLinkage


def _folds_of(n_pairs: int, folds: int):
    """The (train, test) partition each fold would take, without running the attack."""
    import numpy as np

    out = []
    for fold in range(folds):
        pairs = [(f"q{i}", f"g{i}") for i in range(n_pairs)]
        rng = np.random.default_rng(0)
        rng.shuffle(pairs)
        size, extra = divmod(len(pairs), folds)
        bounds, start = [], 0
        for index in range(folds):
            stop = start + size + (1 if index < extra else 0)
            bounds.append((start, stop))
            start = stop
        low, high = bounds[fold]
        out.append((pairs[:low] + pairs[high:], pairs[low:high]))
    return out


def test_the_five_test_sets_partition_the_entities():
    tests = [set(t) for _, t in _folds_of(400, 5)]
    assert sum(len(t) for t in tests) == 400
    assert set().union(*tests) == {(f"q{i}", f"g{i}") for i in range(400)}
    for a in range(5):
        for b in range(a + 1, 5):
            assert not (tests[a] & tests[b]), "test sets must not overlap"


def test_train_and_test_are_disjoint_in_every_fold():
    for train, test in _folds_of(400, 5):
        assert not (set(train) & set(test))
        assert len(train) + len(test) == 400


def test_an_uneven_count_is_split_without_losing_anyone():
    tests = [set(t) for _, t in _folds_of(403, 5)]
    assert sum(len(t) for t in tests) == 403
    assert {len(t) for t in tests} == {80, 81}


def test_a_fold_outside_the_range_is_refused():
    with pytest.raises(ValueError, match="outside"):
        LearnedLinkage(folds=5, fold=5)
    with pytest.raises(ValueError, match="outside"):
        LearnedLinkage(folds=5, fold=-1)


def test_folds_are_opt_in_so_the_old_behaviour_is_unchanged():
    attack = LearnedLinkage()
    assert attack._folds is None
    assert attack._train_fraction == 0.5
