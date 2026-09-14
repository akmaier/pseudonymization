"""JSONL serialisation must round-trip the domain model exactly.

``experiment_plan.md`` §12.2 records two losses, both of which were invisible until something
downstream failed: ``Span.source`` and ``Span.score`` were dropped, so a round-tripped corpus could
not say which detector produced a span; and ``__type__`` was written without a decoder, so
CARDIO:DE's medication and section spans returned as plain dictionaries and ``span.section_type``
raised.  There was no round-trip test.  This is it.
"""

from __future__ import annotations

import json

import pytest

from pseudonymkit.adapters.cardiode import MedicationSpan, SectionSpan
from pseudonymkit.domain import Corpus, Document, Mention, Span
from pseudonymkit.serialisation import (
    TYPES,
    iter_documents,
    read_corpus,
    register_type,
    write_corpus,
)


def _corpus() -> Corpus:
    text = "Dr. Weber verordnete Aspirin 100 mg am <[Pseudo] 12/03/2019>."
    detected = Span(
        start=text.index("Dr. Weber"),
        end=text.index("Dr. Weber") + len("Dr. Weber"),
        text="Dr. Weber",
        type="PERSON",
        type_src="FAMILY",
        source="privacy_tagger",
        score=0.93,
    )
    gold = Span(
        start=text.index("<[Pseudo]"),
        end=text.index("<[Pseudo]") + len("<[Pseudo] 12/03/2019>"),
        text="<[Pseudo] 12/03/2019>",
        type="DATETIME",
        type_src="Pseudo",
    )
    document = Document(
        doc_id="cardiode/CARDIODE400_main/1",
        text=text,
        language="de",
        mentions=(
            Mention("cardiode/CARDIODE400_main/1", "m0", detected, attributes={"gender": "M"}),
            Mention("cardiode/CARDIODE400_main/1", "d0", gold, gold_entity_id=None),
        ),
        corpus="cardiode",
        domain="clinical",
        provenance="placeholder",
        subject_id=None,
        task={
            "name": "cardiode",
            "medications": (
                MedicationSpan(21, 28, "Aspirin", "DRUG", False, False, "12"),
                MedicationSpan(29, 35, "100 mg", "STRENGTH", True, False, "13"),
            ),
            "sections": (SectionSpan(0, 9, "Anamnese", "40"),),
        },
        metadata={"split": "CARDIODE400_main", "n_medications": 2, "annotation": "gold"},
    )
    return Corpus("cardiode@sampled:all:seed0", (document,))


def test_round_trip_is_exact(tmp_path):
    path = tmp_path / "corpus.jsonl"
    original = _corpus()
    assert write_corpus(original, path) == 1
    restored = read_corpus(path)
    assert restored == original


def test_round_trip_keeps_the_detector_that_produced_a_span(tmp_path):
    path = tmp_path / "corpus.jsonl"
    write_corpus(_corpus(), path)
    span = read_corpus(path).documents[0].mentions[0].span
    assert (span.source, span.score, span.type_src) == ("privacy_tagger", 0.93, "FAMILY")


def test_round_trip_rebuilds_the_cardiode_annotation_layers(tmp_path):
    path = tmp_path / "corpus.jsonl"
    write_corpus(_corpus(), path)
    task = read_corpus(path).documents[0].task
    medications = task["medications"]
    assert all(isinstance(m, MedicationSpan) for m in medications)
    assert medications[1].class_type == "STRENGTH"
    assert medications[1].in_narrative is True
    # The failure §12.2 names: a plain dictionary has no attribute, and it raised at the point of
    # use rather than at the point of loss.
    assert task["sections"][0].section_type == "Anamnese"


def test_tuples_stay_tuples(tmp_path):
    path = tmp_path / "corpus.jsonl"
    write_corpus(_corpus(), path)
    task = read_corpus(path).documents[0].task
    assert isinstance(task["medications"], tuple)
    assert isinstance(task["sections"], tuple)


def test_a_plain_list_in_task_stays_a_list(tmp_path):
    """A file written before tuples were tagged must still read, as a list."""
    path = tmp_path / "legacy.jsonl"
    path.write_text(
        json.dumps({"__corpus__": "legacy", "documents": 1}) + "\n"
        + json.dumps({
            "doc_id": "d1", "text": "x", "language": "en",
            "task": {"name": "echr_articles", "label": ["Art.6", "Art.13"]},
            "metadata": {}, "mentions": [],
        }) + "\n",
        encoding="utf-8",
    )
    document = read_corpus(path).documents[0]
    assert document.task["label"] == ["Art.6", "Art.13"]


def test_corpus_name_carries_the_sampling_provenance(tmp_path):
    path = tmp_path / "corpus.jsonl"
    write_corpus(_corpus(), path)
    assert read_corpus(path).name == "cardiode@sampled:all:seed0"


def test_iter_documents_streams_the_same_documents(tmp_path):
    path = tmp_path / "corpus.jsonl"
    write_corpus(_corpus(), path)
    assert list(iter_documents(path)) == list(_corpus().documents)


def test_gzip_round_trips_too(tmp_path):
    path = tmp_path / "corpus.jsonl.gz"
    write_corpus(_corpus(), path)
    assert read_corpus(path) == _corpus()


def test_an_unknown_type_tag_is_loud(tmp_path):
    path = tmp_path / "future.jsonl"
    path.write_text(
        json.dumps({"__corpus__": "future", "documents": 1}) + "\n"
        + json.dumps({
            "doc_id": "d1", "text": "x", "language": "en",
            "task": {"layer": {"__type__": "SomethingFromTheFuture", "a": 1}},
            "metadata": {}, "mentions": [],
        }) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(KeyError, match="SomethingFromTheFuture"):
        read_corpus(path)


def test_register_type_refuses_a_non_dataclass():
    with pytest.raises(TypeError):
        register_type(int)


def test_the_cardiode_layers_registered_themselves():
    assert {"MedicationSpan", "SectionSpan", "MedicationRelation"} <= set(TYPES)


def test_the_adapter_import_is_thread_safe(tmp_path):
    """Two threads reading corpora at once must not race the lazy adapter import.

    The flag used to be set *before* the import, so a second thread saw it true, skipped the import,
    found nothing registered and raised `no decoder for 'MedicationSpan'` while the first thread was
    still importing. Serialised corpus loads hid it; one thread per detector model exposed it at
    once.

    Reaching the race in-process needs the adapter package dropped from ``sys.modules`` as well as
    from ``TYPES`` — otherwise ``import_module`` returns the cached module without re-running
    ``register_type``, and the decoder can never recover. Re-import makes new class objects, so the
    assertion is on the class *name*.
    """
    import importlib
    import sys
    import threading

    from pseudonymkit import serialisation
    from pseudonymkit.adapters.cardiode import MedicationSpan

    path = tmp_path / "c.jsonl"
    doc = Document(doc_id="d1", text="x", language="de", corpus="cardiode",
                   task={"medications": (MedicationSpan(0, 1, "x", "DRUG", True, False, "1"),)})
    write_corpus(Corpus("c", (doc,)), path)

    saved_types = dict(serialisation.TYPES)
    saved_modules = {k: v for k, v in sys.modules.items() if k.startswith("pseudonymkit.adapters")}
    try:
        serialisation.TYPES.pop("MedicationSpan", None)
        for name in saved_modules:
            sys.modules.pop(name, None)
        serialisation._ADAPTERS_IMPORTED = False

        errors: list[BaseException] = []

        def read() -> None:
            try:
                got = read_corpus(path)
                span = got.documents[0].task["medications"][0]
                assert type(span).__name__ == "MedicationSpan"
            except BaseException as exc:      # noqa: BLE001 — the point is to surface any of them
                errors.append(exc)

        threads = [threading.Thread(target=read) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors
    finally:
        sys.modules.update(saved_modules)
        serialisation.TYPES.update(saved_types)
        serialisation._ADAPTERS_IMPORTED = True
        importlib.import_module("pseudonymkit.adapters")
