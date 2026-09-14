"""A cached span set belongs to one exact text, and the cache now knows it.

Two runs spent four days detecting over texts that had been rebuilt underneath them — CARDIO:DE's
tag markup after the condition-A fill had replaced it, Enron's 66,432-document sample after the
empty-body exclusion cut it to 58,636. Nothing in the output looked wrong. These tests pin the
behaviour that makes that loud instead of silent.
"""

from __future__ import annotations

from pseudonymkit.detectors.cache import DetectorCache, text_digest
from pseudonymkit.domain import Span


def _cache(tmp_path) -> DetectorCache:
    return DetectorCache(tmp_path, "tab")


def test_a_record_carries_the_digest_of_the_text_it_saw(tmp_path):
    cache = _cache(tmp_path)
    cache.append("llm:x", "d1", [Span(0, 4, "Anna", "PERSON")], text="Anna was here")
    record = next(cache._read(cache.path("llm:x")))
    assert record["text_sha256"] == text_digest("Anna was here")


def test_a_document_whose_text_changed_is_not_counted_as_done(tmp_path):
    cache = _cache(tmp_path)
    cache.append("llm:x", "d1", [Span(0, 4, "Anna", "PERSON")], text="Anna was here")
    assert cache.done("llm:x", texts={"d1": "Anna was here"}) == {"d1"}
    assert cache.done("llm:x", texts={"d1": "Anna was there"}) == set()


def test_a_document_whose_text_changed_is_dropped_from_load(tmp_path):
    """An ensemble must not be half spans over the current text and half over a vanished one."""
    cache = _cache(tmp_path)
    cache.append("llm:x", "d1", [Span(0, 4, "Anna", "PERSON")], text="Anna was here")
    cache.append("llm:x", "d2", [Span(0, 3, "Bob", "PERSON")], text="Bob was here")
    loaded = cache.load("llm:x", texts={"d1": "Anna was here", "d2": "Bob was THERE"})
    assert set(loaded) == {"d1"}


def test_without_texts_the_cache_behaves_exactly_as_before(tmp_path):
    """Callers that pass no text still get everything — the check is opt-in, not a breaking change."""
    cache = _cache(tmp_path)
    cache.append("llm:x", "d1", [Span(0, 4, "Anna", "PERSON")], text="Anna was here")
    assert cache.done("llm:x") == {"d1"}
    assert set(cache.load("llm:x")) == {"d1"}


def test_a_record_written_before_hashes_existed_is_unverifiable_not_valid(tmp_path):
    cache = _cache(tmp_path)
    cache.append("llm:x", "d1", [Span(0, 4, "Anna", "PERSON")])   # no text passed
    assert cache.done("llm:x") == {"d1"}                          # unchecked: still usable
    assert cache.done("llm:x", texts={"d1": "Anna was here"}) == set()   # checked: refused


def test_a_failed_record_is_never_done_whatever_the_hash(tmp_path):
    cache = _cache(tmp_path)
    cache.append("llm:x", "d1", [], error="gateway 429", text="Anna was here")
    assert cache.done("llm:x", texts={"d1": "Anna was here"}) == set()


# --- digests(): the same resume decision, without holding the corpus -----------------------------
# done() needs every text in hand to compare against.  On Enron that is 58,636 documents of text
# pinned per model thread on a 7 GB head node, which is why the gateway runner now streams and asks
# for digests instead (AM, 2026-09-14).


def test_digests_returns_the_hash_of_each_recorded_document(tmp_path):
    cache = _cache(tmp_path)
    cache.append("llm:x", "d1", [], text="one")
    cache.append("llm:x", "d2", [], text="two")
    assert cache.digests("llm:x") == {"d1": text_digest("one"), "d2": text_digest("two")}


def test_digests_agrees_with_done_about_what_may_be_skipped(tmp_path):
    cache = _cache(tmp_path)
    cache.append("llm:x", "unchanged", [], text="same")
    cache.append("llm:x", "rebuilt", [], text="before")
    texts = {"unchanged": "same", "rebuilt": "after"}
    by_text = cache.done("llm:x", texts=texts)
    by_digest = {d for d, h in texts.items() if cache.digests("llm:x").get(d) == text_digest(h)}
    assert by_text == by_digest == {"unchanged"}


def test_a_failure_removes_a_document_from_the_digest_index(tmp_path):
    cache = _cache(tmp_path)
    cache.append("llm:x", "d1", [], text="one")
    cache.append("llm:x", "d1", (), error="HTTP 500", text="one")
    assert cache.digests("llm:x") == {}


def test_a_record_written_before_hashing_existed_is_not_resumable(tmp_path):
    cache = _cache(tmp_path)
    cache.append("llm:x", "d1", [])          # no text=, so no digest
    assert cache.digests("llm:x") == {}
