"""Turning a stored patch set back into the shape the metrics and attacks consume.

Detection, construction and evaluation are three separate runs. Only construction holds a
PseudonymisedCorpus in memory, and everything in §8.2 and §8.4 takes one — so without this the
conditions already on disk could not be evaluated at all.
"""

from __future__ import annotations

import pytest

from pseudonymkit.conditions import build
from pseudonymkit.construction import (
    NOT_PERSISTED,
    check_roundtrip,
    construct,
    materialise_corpus,
    read_patchset,
    to_pseudonymised_corpus,
    write_patchset,
)
from pseudonymkit.domain import Document, Mention, Span
from pseudonymkit.engine import replacements
from pseudonymkit.inventories import SyntheticInventory
from pseudonymkit.metrics.stability import evaluate_stability

KEY = b"\x33" * 32
TEXT = "Weber met Meyer in Berlin, then Weber wrote to Meyer again."
ENTS = [("Weber", "PERSON", "e1"), ("Meyer", "PERSON", "e2"), ("Berlin", "LOC", "e3"),
        ("Weber", "PERSON", "e1"), ("Meyer", "PERSON", "e2")]


def document(doc_id="d1"):
    mentions, cursor = [], 0
    for i, (surface, type_, chain) in enumerate(ENTS):
        start = TEXT.index(surface, cursor)
        cursor = start + len(surface)
        mentions.append(Mention(doc_id, f"m{i}", Span(start, start + len(surface), surface, type_),
                                gold_entity_id=chain))
    return Document(doc_id, TEXT, "en", tuple(mentions))


@pytest.fixture
def built():
    docs = [document("d1"), document("d2")]
    sets = construct(docs, corpus="fixture",
                     inventory=SyntheticInventory(pool_size=512), key=KEY)
    return docs, sets


def test_the_rebuilt_corpus_reproduces_the_engines_own_offsets(built):
    docs, sets = built
    for condition, patchset in sets.items():
        corpus = to_pseudonymised_corpus(docs, patchset)     # check=True asserts internally
        assert len(corpus.documents) == 2, condition


def test_the_rebuilt_text_equals_the_materialised_text(built):
    docs, sets = built
    rebuilt = {d.document.doc_id: d.text for d in to_pseudonymised_corpus(docs, sets["B"]).documents}
    direct = {d.doc_id: d.text for d in materialise_corpus(docs, sets["B"]).documents}
    assert rebuilt == direct


def test_it_survives_a_trip_through_disk(built, tmp_path):
    docs, sets = built
    path = tmp_path / "fixture_B.patch.jsonl"
    assert write_patchset(sets["B"], path) == 2      # returns the patch count, not the path
    corpus = to_pseudonymised_corpus(docs, read_patchset(path))
    assert [r.assignment.surface for d in corpus.documents for r in replacements(d)]


def test_the_gold_chain_is_joined_back_on_so_stability_is_computable(built):
    docs, sets = built
    corpus = to_pseudonymised_corpus(docs, sets["B"])
    chains = {m.gold_entity_id for d in corpus.documents for m in d.document.mentions}
    assert chains == {"e1", "e2", "e3"}
    report = evaluate_stability(corpus, entity_type="PERSON", policy="deterministic")
    assert report.collisions == 0        # two people, two surrogates, no key collapsed them


def test_without_attach_gold_there_is_no_chain(built):
    docs, sets = built
    corpus = to_pseudonymised_corpus(docs, sets["B"], attach_gold=False)
    assert all(m.gold_entity_id is None for d in corpus.documents for m in d.document.mentions)


def test_the_technique_index_is_marked_absent_rather_than_invented(built):
    docs, sets = built
    corpus = to_pseudonymised_corpus(docs, sets["B"])
    assert all(a.index == NOT_PERSISTED for d in corpus.documents for a in d.assignments)


def test_one_entity_keeps_one_surrogate_through_the_round_trip(built):
    """B's whole claim. If the adapter lost it, every stability number would be wrong."""
    docs, sets = built
    corpus = to_pseudonymised_corpus(docs, sets["B"])
    by_key: dict[str, set[str]] = {}
    for d in corpus.documents:
        for a in d.assignments:
            by_key.setdefault(a.entity_key, set()).add(a.surface)
    assert all(len(v) == 1 for v in by_key.values()), by_key


def test_a_corrupted_patch_is_caught_rather_than_silently_misaligned(built):
    from dataclasses import replace as _replace
    docs, sets = built
    patch = sets["B"].patches[0]
    broken = _replace(patch, entries=tuple(
        _replace(e, new_start=e.new_start + 3) if i == 0 else e
        for i, e in enumerate(patch.entries)))
    rebuilt = to_pseudonymised_corpus([docs[0]], _replace(sets["B"], patches=(broken,)), check=False)
    with pytest.raises(ValueError, match="diverge"):
        check_roundtrip(rebuilt.documents[0], broken)


# ------------------------------------------------- the guard against a rebuilt condition A
# CARDIO:DE's condition A was rebuilt on 2026-09-15 underneath jobs already reading it. 247 of 400
# union patches then addressed offsets past the end of the new text, and nine hours of utility
# scoring went into a corpus that no longer existed. Offsets still parsed; nothing looked wrong.

from dataclasses import replace as _dc_replace      # noqa: E402

from pseudonymkit.construction import check_current  # noqa: E402


def test_a_freshly_built_patch_carries_the_digest_of_its_text(built):
    docs, sets = built
    for patchset in sets.values():
        assert all(p.text_sha256 for p in patchset.patches)
    assert check_current(docs, sets["B"])["stale"] == 0


def test_a_rebuilt_corpus_is_refused_rather_than_scored(built):
    docs, sets = built
    rebuilt = [_dc_replace(d, text=d.text.replace("Berlin", "Bremen")) for d in docs]
    with pytest.raises(ValueError, match="different condition-A text"):
        check_current(rebuilt, sets["B"])


def test_a_patch_written_before_the_guard_existed_is_unverifiable_not_waved_through(built):
    docs, sets = built
    old = _dc_replace(sets["B"], patches=tuple(
        _dc_replace(p, text_sha256=None) for p in sets["B"].patches))
    with pytest.raises(ValueError, match="no digest"):
        check_current(docs, old)


def test_the_digest_survives_a_trip_through_disk(built, tmp_path):
    from pseudonymkit.construction import read_patchset, write_patchset

    docs, sets = built
    path = tmp_path / "b.patch.jsonl"
    write_patchset(sets["B"], path)
    assert check_current(docs, read_patchset(path))["stale"] == 0
