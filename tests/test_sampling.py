"""Sampling schemes, and the property each one is meant to preserve or destroy."""

import pytest

from pseudonymkit.domain import Corpus, Document, Mention, Span
from pseudonymkit.sampling import SAMPLERS, sample


def corpus(n_subjects: int = 10, per_subject: int = 20) -> Corpus:
    docs = []
    for s in range(n_subjects):
        for i in range(per_subject):
            doc_id = f"s{s}-d{i:03d}"
            text = f"person{s} wrote to person{(s + 1) % n_subjects} on day {i}."
            mentions = []
            for who in (s, (s + 1) % n_subjects):
                name = f"person{who}"
                start = text.index(name)
                mentions.append(Mention(doc_id, f"m{who}",
                                        Span(start, start + len(name), name, "PERSON"),
                                        gold_entity_id=name))
            docs.append(Document(doc_id, text, "en", tuple(mentions),
                                 subject_id=f"s{s}", metadata={"date": f"2001-01-{i + 1:02d}"}))
    return Corpus("toy", tuple(docs))


@pytest.mark.parametrize("scheme", sorted(SAMPLERS))
def test_every_scheme_hits_roughly_the_rate(scheme):
    out = sample(corpus(), scheme, 0.25, seed=1)
    assert 0.15 * 200 <= len(out) <= 0.35 * 200


@pytest.mark.parametrize("scheme", sorted(SAMPLERS))
def test_sampling_is_reproducible_and_stamped(scheme):
    a, b = sample(corpus(), scheme, 0.2, seed=7), sample(corpus(), scheme, 0.2, seed=7)
    assert [d.doc_id for d in a] == [d.doc_id for d in b]
    assert f"{scheme}@0.2/seed7" in a.name
    assert all(d.metadata["sampling"] == f"{scheme}@0.2/seed7" for d in a)


def test_by_subject_keeps_whole_subjects():
    """A3, A5 and drift need a subject's documents intact, not a tenth of them."""
    out = sample(corpus(), "subject", 0.3, seed=0)
    kept = {d.subject_id for d in out}
    counts = {s: sum(1 for d in out if d.subject_id == s) for s in kept}
    assert set(counts.values()) == {20}


def test_stratified_keeps_every_subject_represented():
    out = sample(corpus(), "stratified", 0.25, seed=0)
    assert {d.subject_id for d in out} == {f"s{i}" for i in range(10)}


def test_by_time_is_contiguous():
    """The window is a shorter corpus, not a scattered one: the dates it spans have no gaps."""
    full = sorted({d.metadata["date"] for d in corpus()})
    kept = sorted({d.metadata["date"] for d in sample(corpus(), "time", 0.2, seed=3)})
    first = full.index(kept[0])
    assert kept == full[first : first + len(kept)]


def test_subject_sampling_keeps_profiles_whole_while_document_sampling_thins_them():
    """The property the relational attacks depend on: per-entity evidence completeness.

    Both schemes keep a comparable number of documents. Neither keeps a profile whole -- an entity
    spanning several subjects is truncated by whichever of its subjects were dropped -- but subject
    sampling retains markedly more of each profile, which is the trade A3 and A5 want.
    """
    def mentions_per_entity(c):
        counts = {}
        for d in c:
            for m in d.mentions:
                counts[m.gold_entity_id] = counts.get(m.gold_entity_id, 0) + 1
        return counts

    full = corpus(n_subjects=20, per_subject=20)
    base = mentions_per_entity(full)
    doc_counts = mentions_per_entity(sample(full, "document", 0.2, seed=0))
    subj_counts = mentions_per_entity(sample(full, "subject", 0.2, seed=0))

    doc_retention = sum(doc_counts.values()) / sum(base[e] for e in doc_counts)
    subj_retention = sum(subj_counts.values()) / sum(base[e] for e in subj_counts)
    assert doc_retention < subj_retention
    assert subj_retention > 2 * doc_retention


def test_rate_and_scheme_are_validated():
    with pytest.raises(ValueError):
        sample(corpus(), "document", 0.0)
    with pytest.raises(KeyError, match="stratified"):
        sample(corpus(), "nonsense", 0.5)


def test_by_subject_refuses_a_corpus_without_subjects():
    plain = Corpus("x", (Document("d", "text", "en"),))
    with pytest.raises(ValueError, match="subject_id"):
        sample(plain, "subject", 0.5)
