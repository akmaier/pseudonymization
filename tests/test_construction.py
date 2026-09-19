"""Conditions B and C, built from one span set in one pass.

The invariant these tests exist to hold: B and C are one axis level apart, so they must be driven by
the *same* detected spans. If one were built from ``union`` and the other from ``vote(3)``, the
difference between them would confound the condition with detector coverage.
"""

from __future__ import annotations

import pytest

from pseudonymkit.construction import (
    Patch,
    PatchEntry,
    construct,
    detected_documents,
    materialise,
    materialise_corpus,
    read_patchset,
    write_patchset,
)
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.domain import Document, Mention, Span
from pseudonymkit.inventories import ListInventory
from pseudonymkit.inventories import Entry

KEY = b"0123456789abcdef"

TEXT = "Anna Schmidt wrote to Bob Meier about Berlin."
#       0123456789...
ANNA = (0, 12)
BOB = (22, 31)


def _doc(doc_id: str = "d1", text: str = TEXT) -> Document:
    return Document(doc_id=doc_id, text=text, language="en", corpus="t")


def _inventory() -> ListInventory:
    return ListInventory({
        ("PERSON", "en"): [Entry("Fiona Clarke"), Entry("Owen Bright"), Entry("Nina Hall")],
        ("LOC", "en"): [Entry("Ashford"), Entry("Wexley")],
    })


def _detected(spans) -> Document:
    doc = _doc()
    return doc.with_mentions(tuple(
        Mention("d1", f"d1:det:{i}", Span(a, b, TEXT[a:b], t))
        for i, (a, b, t) in enumerate(spans)
    ))


# --------------------------------------------------------------------------- one pass, two outputs


def test_B_and_C_are_built_from_the_same_spans():
    doc = _detected([(*ANNA, "PERSON"), (*BOB, "PERSON")])
    out = construct([doc], "t", ("B", "C"), inventory=_inventory(), key=KEY)
    b, c = out["B"].patches[0], out["C"].patches[0]
    assert [(e.old_start, e.old_end) for e in b.entries] == [ANNA, BOB]
    assert [(e.old_start, e.old_end) for e in b.entries] == [
        (e.old_start, e.old_end) for e in c.entries
    ]


def test_C_is_a_typed_placeholder_and_B_is_not():
    doc = _detected([(*ANNA, "PERSON")])
    out = construct([doc], "t", ("B", "C"), inventory=_inventory(), key=KEY)
    assert out["C"].patches[0].entries[0].replacement == "[PERSON]"
    assert out["B"].patches[0].entries[0].replacement != "[PERSON]"


def test_C_still_records_which_entity_each_placeholder_stood_for():
    """The text loses the distinction — that is C. Our records must not, or leakage is unscorable."""
    doc = _detected([(*ANNA, "PERSON"), (*BOB, "PERSON")])
    out = construct([doc], "t", ("C",), key=KEY)
    keys = [e.entity_key for e in out["C"].patches[0].entries]
    assert len(set(keys)) == 2 and all(keys)


def test_condition_A_cannot_be_constructed():
    with pytest.raises(ValueError, match="A is the input"):
        construct([_detected([])], "t", ("A",), key=KEY)


def test_B_without_an_inventory_is_refused():
    with pytest.raises(ValueError, match="inventory"):
        construct([_detected([(*ANNA, "PERSON")])], "t", ("B",), key=KEY)


# ----------------------------------------------------------------------------------- round trip


def test_materialise_reproduces_the_text_and_the_offsets():
    doc = _detected([(*ANNA, "PERSON"), (*BOB, "PERSON")])
    out = construct([doc], "t", ("B",), inventory=_inventory(), key=KEY)
    built = materialise(doc, out["B"].patches[0])
    for entry in out["B"].patches[0].entries:
        assert built.text[entry.new_start : entry.new_end] == entry.replacement
    assert "Anna Schmidt" not in built.text and "Bob Meier" not in built.text
    assert "wrote to" in built.text and "about Berlin." in built.text


def test_the_same_entity_gets_the_same_surrogate_across_documents():
    """Deterministic policy: stability across the corpus is what B is for (§7)."""
    d1 = _doc("d1").with_mentions((Mention("d1", "m", Span(*ANNA, TEXT[0:12], "PERSON")),))
    other = "Later, Anna Schmidt replied."
    d2 = Document("d2", other, "en", corpus="t").with_mentions(
        (Mention("d2", "m", Span(7, 19, "Anna Schmidt", "PERSON")),)
    )
    out = construct([d1, d2], "t", ("B",), inventory=_inventory(), key=KEY)
    a, b = out["B"].patches
    assert a.entries[0].replacement == b.entries[0].replacement


def test_a_patchset_round_trips_through_disk(tmp_path):
    doc = _detected([(*ANNA, "PERSON"), (*BOB, "PERSON")])
    out = construct([doc], "t", ("B",), inventory=_inventory(), key=KEY,
                    provenance={"rule": "union"})
    path = tmp_path / "b.jsonl"
    assert write_patchset(out["B"], path) == 1
    back = read_patchset(path)
    assert back.condition == "B" and back.corpus == "t"
    assert back.provenance["rule"] == "union"
    assert back.patches == out["B"].patches
    assert materialise(doc, back.patches[0]).text == materialise(doc, out["B"].patches[0]).text


def test_task_layers_move_with_the_text():
    """CARDIO:DE's medication and section spans are the utility tasks; the transform must carry them."""
    from pseudonymkit.adapters.cardiode import SectionSpan

    marked = Document(
        doc_id="d1", text=TEXT, language="en", corpus="t",
        mentions=(Mention("d1", "d1:det:0", Span(*ANNA, TEXT[ANNA[0]:ANNA[1]], "PERSON")),),
        task={"sections": (SectionSpan(BOB[0], BOB[1], "body", "1"),)},
    )
    assert TEXT[BOB[0]:BOB[1]] == "Bob Meier"
    out = construct([marked], "t", ("C",), key=KEY)
    built = materialise(marked, out["C"].patches[0])
    section = built.task["sections"][0]
    assert (section.start, section.end) != BOB          # the text before it got shorter
    assert built.text[section.start : section.end] == "Bob Meier"


def test_a_document_with_no_patch_passes_through_unchanged():
    doc = _detected([])
    out = construct([doc], "t", ("C",), key=KEY)
    corpus = materialise_corpus([doc], out["C"])
    assert corpus.documents[0].text == TEXT


# --------------------------------------------------------------- post-hoc ensembling over a cache


def _cache_with(tmp_path, **by_detector) -> DetectorCache:
    cache = DetectorCache(tmp_path, "t")
    for detector, records in by_detector.items():
        for doc_id, spans, extra in records:
            cache.append(detector, doc_id, spans, text=TEXT, **extra)
    return cache


def test_union_and_intersection_come_from_the_same_cache(tmp_path):
    cache = _cache_with(
        tmp_path,
        a=[("d1", [Span(*ANNA, "Anna Schmidt", "PERSON"), Span(*BOB, "Bob Meier", "PERSON")], {})],
        b=[("d1", [Span(*ANNA, "Anna Schmidt", "PERSON")], {})],
    )
    docs = [_doc()]
    union, _ = detected_documents(docs, cache, ["a", "b"], "union")
    inter, _ = detected_documents(docs, cache, ["a", "b"], "intersection")
    assert len(union[0].mentions) == 2
    assert len(inter[0].mentions) == 1


def test_a_truncated_record_is_dropped_not_believed(tmp_path):
    """A truncated response is a runaway, not a short one: 279 spans against 53.8 on CARDIO:DE."""
    cache = _cache_with(
        tmp_path,
        a=[("d1", [Span(*ANNA, "Anna Schmidt", "PERSON")], {"meta": {"truncated": True}})],
        b=[("d1", [Span(*BOB, "Bob Meier", "PERSON")], {})],
    )
    docs, summary = detected_documents([_doc()], cache, ["a", "b"])
    assert summary["records_dropped_truncated"] == 1
    assert [m.span.text for m in docs[0].mentions] == ["Bob Meier"]


def test_a_record_over_changed_text_is_dropped(tmp_path):
    cache = DetectorCache(tmp_path, "t")
    cache.append("a", "d1", [Span(*ANNA, "Anna Schmidt", "PERSON")], text="a different text")
    docs, summary = detected_documents([_doc()], cache, ["a"])
    assert summary["records_dropped_stale_text"] == 1
    assert docs == []


def test_a_missing_detector_is_a_hole_not_a_zero(tmp_path):
    """Treating 'not run' as 'found nothing' turns a missing detector into a vote against."""
    cache = _cache_with(
        tmp_path, a=[("d1", [Span(*ANNA, "Anna Schmidt", "PERSON")], {})],
    )
    docs, summary = detected_documents([_doc()], cache, ["a", "b"], "intersection")
    assert summary["documents_missing_a_detector"] == 1
    assert len(docs[0].mentions) == 1          # combined over the pool that actually ran
    strict, _ = detected_documents([_doc()], cache, ["a", "b"], "intersection", require_all=True)
    assert strict == []


def test_gold_is_just_another_detector(tmp_path):
    """§7 lists gold spans as a level of axis D; it must not need a special path."""
    cache = DetectorCache(tmp_path, "t")
    doc = _doc().with_mentions((Mention("d1", "g0", Span(*ANNA, "Anna Schmidt", "PERSON")),))
    docs, summary = detected_documents([doc], cache, ["gold"], "union")
    assert [m.span.text for m in docs[0].mentions] == ["Anna Schmidt"]
    assert summary["detectors"] == ["gold"]


def test_the_clustering_settings_reach_the_summary(tmp_path):
    """link and iou silently changed every ensemble result before they were reportable."""
    cache = _cache_with(tmp_path, a=[("d1", [Span(*ANNA, "Anna Schmidt", "PERSON")], {})])
    _, summary = detected_documents(
        [_doc()], cache, ["a"], "union", rule_kwargs={"link": "iou", "iou": 0.7}
    )
    assert summary["link"] == "iou" and summary["iou"] == 0.7


def test_a_varying_pool_size_is_recorded_and_flagged_for_a_vote_rule(tmp_path):
    """A majority threshold derived per document is not the rule the patch set is labelled with.

    MajorityVote with no explicit k uses (n // 2) + 1 over the detectors *present for that
    document*. Where records were dropped as truncated or never written, n differs between
    documents, so one is judged at 7 of 13 and its neighbour at 8 of 15 under one name. On Enron
    that is 56,993 of 58,636 documents; on OntoNotes 5,416 of 5,994. The behaviour is left alone
    deliberately — changing it changes every condition built on a partial pool — but it must be
    visible in the summary rather than inferable only from a document count.
    """
    from pseudonymkit.detectors.cache import DetectorCache

    cache = DetectorCache(tmp_path, "tab")
    documents = [
        Document("full", "Anna met Bob in Bonn.", "en"),
        Document("short", "Carla met Dan in Kiel.", "en"),
    ]
    for name in ("d1", "d2", "d3"):
        cache.append(name, "full", [Span(0, 4, "Anna", "PERSON")], text=documents[0].text)
    for name in ("d1", "d2"):                       # "short" is missing d3 entirely
        cache.append(name, "short", [Span(0, 5, "Carla", "PERSON")], text=documents[1].text)

    _, summary = detected_documents(documents, cache, ["d1", "d2", "d3"], "vote")
    assert summary["pool_size_histogram"] == {2: 1, 3: 1}
    assert summary["documents_missing_a_detector"] == 1
    assert "WARNING_vote_threshold_varies" in summary


def test_a_complete_pool_carries_no_warning(tmp_path):
    from pseudonymkit.detectors.cache import DetectorCache

    cache = DetectorCache(tmp_path, "tab")
    documents = [Document("a", "Anna met Bob in Bonn.", "en"),
                 Document("b", "Carla met Dan in Kiel.", "en")]
    for document in documents:
        for name in ("d1", "d2", "d3"):
            cache.append(name, document.doc_id, [Span(0, 4, document.text[:4], "PERSON")],
                         text=document.text)
    _, summary = detected_documents(documents, cache, ["d1", "d2", "d3"], "vote")
    assert summary["pool_size_histogram"] == {3: 2}
    assert "WARNING_vote_threshold_varies" not in summary
