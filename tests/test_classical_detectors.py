"""The four classical detector levels of axis D.

No model is downloaded and no framework is imported: presidio, gliner, transformers and flair all
load inside each detector's ``load()``, and every test injects a stand-in through ``use()``.  What is
tested is the part that is ours and that fails silently when it is wrong — character offsets,
windowing, label routing and the cache contract — not that a third-party model can label a sentence.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pseudonymkit.detectors.alignment import dedupe_spans, text_windows
from pseudonymkit.detectors.base import DETECTORS
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.detectors.domain import PrivacyTagger, align_tokens
from pseudonymkit.detectors.finetuned import FINETUNED_MODELS, TokenClassificationDetector
from pseudonymkit.detectors.rule import MULTILINGUAL, SPACY_MODELS, PresidioDetector
from pseudonymkit.detectors.runner import run_detector
from pseudonymkit.detectors.zeroshot import GLINER_MODELS, GlinerDetector
from pseudonymkit.domain import Document, Span

TEXT = "Dr. Weber wrote to kate@example.com from Berlin on 3 March 2019."


def doc(text: str = TEXT, language: str = "en", doc_id: str = "d1") -> Document:
    return Document(doc_id, text, language)


def at(text: str, surface: str) -> tuple[int, int]:
    start = text.index(surface)
    return start, start + len(surface)


# ------------------------------------------------------------------------------------- windowing


def test_text_windows_cover_the_document_with_overlap():
    text = "x" * 250
    windows = text_windows(text, 100, 20)
    assert windows[0] == (0, 100)
    assert windows[1] == (80, 180)
    assert windows[-1][1] == len(text)
    covered = set()
    for start, end in windows:
        covered.update(range(start, end))
    assert covered == set(range(len(text)))


def test_text_windows_of_a_short_document_is_one_window():
    assert text_windows("short", 100, 20) == [(0, 5)]
    assert text_windows("", 100) == []


def test_text_windows_rejects_an_overlap_that_cannot_advance():
    with pytest.raises(ValueError):
        text_windows("abc", 10, 10)
    with pytest.raises(ValueError):
        text_windows("abc", 0)


def test_dedupe_keeps_the_better_scored_copy():
    a = Span(0, 4, "Kate", "PERSON", score=0.4)
    b = Span(0, 4, "Kate", "PERSON", score=0.9)
    c = Span(0, 4, "Kate", "ORG", score=0.1)
    kept = dedupe_spans([a, b, c])
    assert len(kept) == 2
    assert {(s.type, s.score) for s in kept} == {("PERSON", 0.9), ("ORG", 0.1)}


# --------------------------------------------------------------------------------- Presidio (rule)


class FakeAnalyzer:
    """Stands in for ``AnalyzerEngine``: returns fixed results and records what it was asked."""

    def __init__(self, results):
        self._results = results
        self.calls: list[tuple[str, str]] = []

    def analyze(self, text, language, entities=None, score_threshold=0.0):
        self.calls.append((text, language))
        return [r for r in self._results if r.entity_type and r.start < len(text)]


def result(entity_type: str, span: tuple[int, int], score: float = 0.85):
    return SimpleNamespace(entity_type=entity_type, start=span[0], end=span[1], score=score)


def test_presidio_emits_character_offsets_and_harmonised_types():
    analyzer = FakeAnalyzer([
        result("PERSON", at(TEXT, "Weber")),
        result("EMAIL_ADDRESS", at(TEXT, "kate@example.com")),
        result("LOCATION", at(TEXT, "Berlin")),
        result("DATE_TIME", at(TEXT, "3 March 2019")),
    ])
    out = PresidioDetector().use(analyzer).detect(doc())
    assert out.detector == "presidio"
    assert [(s.text, s.type, s.type_src) for s in out.spans] == [
        ("Weber", "PERSON", "PERSON"),
        ("kate@example.com", "CODE", "EMAIL_ADDRESS"),
        ("Berlin", "LOC", "LOCATION"),
        ("3 March 2019", "DATETIME", "DATE_TIME"),
    ]
    assert all(s.source == "presidio" and s.score == 0.85 for s in out.spans)


def test_presidio_span_text_is_read_from_the_document():
    """The span text must come from the document, not from the recogniser's own copy."""
    out = PresidioDetector().use(FakeAnalyzer([result("PERSON", at(TEXT, "Weber"))])).detect(doc())
    assert out.spans[0].text == TEXT[out.spans[0].start : out.spans[0].end]


def test_presidio_routes_unknown_languages_to_the_multilingual_backbone():
    detector = PresidioDetector().use(FakeAnalyzer([]))
    assert detector.language_for(doc(language="en")) == "en"
    assert detector.language_for(doc(language="de")) == "de"
    assert detector.language_for(doc(language="zh")) == MULTILINGUAL
    assert detector.language_for(doc(language="ar")) == MULTILINGUAL


def test_presidio_counts_the_fallback_so_a_result_carries_its_backbone():
    detector = PresidioDetector().use(FakeAnalyzer([]))
    detector.detect(doc(language="zh"))
    detector.detect(doc(language="zh"))
    detector.detect(doc(language="ar"))
    detector.detect(doc(language="en"))
    assert detector.fallbacks == {"zh": 2, "ar": 1}


def test_presidio_backbones_are_the_three_the_plan_names():
    assert SPACY_MODELS == {
        "en": "en_core_web_lg", "de": "de_core_news_lg", "xx": "xx_ent_wiki_sm"
    }


def test_presidio_windows_long_documents_and_shifts_offsets():
    long_text = ("filler " * 200) + "Weber"

    class Windowed(FakeAnalyzer):
        def analyze(self, text, language, entities=None, score_threshold=0.0):
            self.calls.append((text, language))
            found = text.find("Weber")
            return [result("PERSON", (found, found + 5))] if found >= 0 else []

    analyzer = Windowed([])
    detector = PresidioDetector(max_chars=100, overlap=10).use(analyzer)
    out = detector.detect(doc(long_text))
    assert len(analyzer.calls) > 1
    assert out.spans and all(long_text[s.start : s.end] == "Weber" for s in out.spans)


# --------------------------------------------------------------------------------- GLiNER (zero-shot)


class FakeGliner:
    def __init__(self, entities):
        self._entities = entities
        self.labels_seen: list[list[str]] = []

    def predict_entities(self, text, labels, threshold=0.5):
        self.labels_seen.append(list(labels))
        out = []
        for surface, label, score in self._entities:
            start = text.find(surface)
            if start >= 0:
                out.append({"start": start, "end": start + len(surface),
                            "text": surface, "label": label, "score": score})
        return out


def test_gliner_is_prompted_with_the_eight_harmonised_labels():
    model = FakeGliner([])
    GlinerDetector().use(model).detect(doc())
    assert model.labels_seen[0] == [
        "PERSON", "LOC", "ORG", "DATETIME", "CODE", "DEMOGRAPHIC", "QUANTITY", "MISC"
    ]


def test_gliner_names_the_checkpoint_so_the_two_levels_stay_apart():
    assert GlinerDetector(model=GLINER_MODELS[0]).name == "gliner:urchade/gliner_multi-v2.1"
    assert GlinerDetector(model=GLINER_MODELS[1]).name == "gliner:urchade/gliner_multi_pii-v1"


def test_gliner_emits_offsets_types_and_scores():
    model = FakeGliner([("Weber", "PERSON", 0.91), ("Berlin", "LOC", 0.77)])
    out = GlinerDetector().use(model).detect(doc())
    assert [(s.text, s.type, s.score) for s in out.spans] == [
        ("Weber", "PERSON", 0.91), ("Berlin", "LOC", 0.77)
    ]
    assert all(s.source.startswith("gliner:") for s in out.spans)


def test_gliner_windows_and_deduplicates_the_overlap():
    text = "Weber " + "x" * 300 + " Weber"
    model = FakeGliner([("Weber", "PERSON", 0.9)])
    out = GlinerDetector(max_chars=120, overlap=40).use(model).detect(doc(text))
    # Both occurrences are found, and neither is reported twice by the overlapping windows.
    assert sorted(s.start for s in out.spans) == [0, text.rindex("Weber")]


def test_gliner_batches_with_batch_predict_when_the_model_offers_it():
    class Batched(FakeGliner):
        def __init__(self, entities):
            super().__init__(entities)
            self.batches = 0

        def batch_predict_entities(self, texts, labels, threshold=0.5):
            self.batches += 1
            return [self.predict_entities(t, labels, threshold) for t in texts]

    model = Batched([("Weber", "PERSON", 0.9)])
    outputs = GlinerDetector().use(model).detect_many([doc(doc_id="a"), doc(doc_id="b")])
    assert model.batches == 1
    assert [o.doc_id for o in outputs] == ["a", "b"]
    assert all(o.spans[0].text == "Weber" for o in outputs)


# ------------------------------------------------------------------------- fine-tuned token classes


class FakePipeline:
    def __init__(self, entities, offsets=True):
        self._entities = entities
        self._offsets = offsets

    def __call__(self, chunks, batch_size=8):
        results = []
        for text in chunks:
            found = []
            for surface, group, score in self._entities:
                start = text.find(surface)
                if start < 0:
                    continue
                found.append({
                    "entity_group": group,
                    "score": score,
                    "word": surface,
                    "start": start if self._offsets else None,
                    "end": (start + len(surface)) if self._offsets else None,
                })
            results.append(found)
        return results


def test_finetuned_names_and_source_table_come_from_the_model_id():
    detector = TokenClassificationDetector(model="obi/deid_roberta_i2b2")
    assert detector.name == "hf:obi/deid_roberta_i2b2"
    assert detector.source == "obi/deid_roberta_i2b2"


@pytest.mark.parametrize(
    "model,raw,expected",
    [
        ("obi/deid_roberta_i2b2", "PATIENT", "PERSON"),
        ("obi/deid_roberta_i2b2", "HOSP", "ORG"),
        ("StanfordAIMI/stanford-deidentifier-base", "HCW", "PERSON"),
        ("Davlan/xlm-roberta-large-ner-hrl", "PER", "PERSON"),
    ],
)
def test_finetuned_routes_each_checkpoints_own_labels(model, raw, expected):
    pipe = FakePipeline([("Weber", raw, 0.99)])
    out = TokenClassificationDetector(model=model).use(pipe).detect(doc())
    assert (out.spans[0].type, out.spans[0].type_src) == (expected, raw)


def test_finetuned_covers_the_three_checkpoints_the_plan_fixes():
    assert FINETUNED_MODELS == (
        "obi/deid_roberta_i2b2",
        "StanfordAIMI/stanford-deidentifier-base",
        "Davlan/xlm-roberta-large-ner-hrl",
    )


def test_finetuned_refuses_a_slow_tokenizers_missing_offsets():
    """Writing Span(None, None) would be invisible until the offsets were scored."""
    pipe = FakePipeline([("Weber", "PER", 0.9)], offsets=False)
    detector = TokenClassificationDetector(model=FINETUNED_MODELS[2]).use(pipe)
    with pytest.raises(RuntimeError, match="use_fast"):
        detector.detect(doc())


def test_finetuned_windows_and_shifts_offsets():
    text = "x" * 300 + " Weber"
    pipe = FakePipeline([("Weber", "PER", 0.9)])
    out = TokenClassificationDetector(model=FINETUNED_MODELS[2], max_chars=120, overlap=20)\
        .use(pipe).detect(doc(text))
    assert [s.start for s in out.spans] == [text.index("Weber")]
    assert out.spans[0].text == "Weber"


def test_finetuned_detect_many_keeps_documents_apart():
    pipe = FakePipeline([("Weber", "PER", 0.9)])
    outputs = TokenClassificationDetector(model=FINETUNED_MODELS[2]).use(pipe).detect_many(
        [doc(doc_id="a"), doc("Nothing here.", doc_id="b")]
    )
    assert [len(o.spans) for o in outputs] == [1, 0]
    assert [o.doc_id for o in outputs] == ["a", "b"]


# ------------------------------------------------------------------------ privacy_tagger (domain)


def test_align_tokens_finds_each_token_once_in_order():
    text = "Weber traf Weber."
    offsets, cursor = align_tokens(text, ["Weber", "traf", "Weber", "."])
    assert offsets == [(0, 5), (6, 10), (11, 16), (16, 17)]
    assert cursor == 17


def test_align_tokens_does_not_jump_far_ahead_for_a_normalised_token():
    """A rewritten token must lose itself, not drag every following offset with it."""
    text = "a" * 200 + " Weber"
    offsets, _ = align_tokens(text, ["“quote”", "Weber"], max_skip=8)
    assert offsets[0] is None
    assert offsets[1] is None or offsets[1] == (201, 206)


class FakeToken:
    def __init__(self, text, offset=None):
        self.text = text
        self.character_offset = offset
        self.original_spelling = None


class FakeSoMaJo:
    def __init__(self, sentences, offsets=False):
        self._sentences = sentences
        self._offsets = offsets

    def tokenize_text(self, paragraphs):
        text = paragraphs[0]
        for words in self._sentences:
            cursor = 0
            tokens = []
            for word in words:
                start = text.find(word, cursor)
                cursor = start + len(word)
                tokens.append(FakeToken(word, (start, cursor) if self._offsets else None))
            yield tokens


class FakeFlairSpan:
    def __init__(self, indices, tag, score):
        self.tokens = [SimpleNamespace(idx=i) for i in indices]
        self.tag = tag
        self.score = score


class FakeTagger:
    tag_type = "ner"

    def __init__(self, spans_per_sentence):
        self._spans = spans_per_sentence
        self.predicted = 0

    def predict(self, sentences, mini_batch_size=32):
        self.predicted += len(sentences)
        for sentence, spans in zip(sentences, self._spans):
            sentence._spans = spans


@pytest.fixture
def flair_sentence(monkeypatch):
    """Install a minimal ``flair.data.Sentence`` so the detector can be exercised without flair."""
    import sys
    import types

    class Sentence:
        def __init__(self, tokens):
            self.tokens = tokens
            self._spans = []

        def get_spans(self, tag_type):
            return self._spans

    module = types.ModuleType("flair")
    data = types.ModuleType("flair.data")
    data.Sentence = Sentence
    module.data = data
    monkeypatch.setitem(sys.modules, "flair", module)
    monkeypatch.setitem(sys.modules, "flair.data", data)
    return Sentence


def test_privacy_tagger_maps_flair_tokens_back_to_document_offsets(flair_sentence):
    text = "Sehr geehrter Herr Weber , ich wohne in Bonn ."
    words = text.split()
    tagger = FakeTagger([[FakeFlairSpan([4], "FAMILY", 0.98), FakeFlairSpan([9], "CITY", 0.88)]])
    detector = PrivacyTagger().use(tagger, FakeSoMaJo([words]))
    out = detector.detect(Document("d1", text, "de"))
    assert [(s.text, s.type, s.type_src) for s in out.spans] == [
        ("Weber", "PERSON", "FAMILY"), ("Bonn", "LOC", "CITY")
    ]
    assert all(text[s.start : s.end] == s.text for s in out.spans)


def test_privacy_tagger_uses_somajo_offsets_when_they_are_available(flair_sentence):
    text = "Herr Weber wohnt in Bonn ."
    words = text.split()
    tagger = FakeTagger([[FakeFlairSpan([2], "FAMILY", 0.9)]])
    detector = PrivacyTagger().use(tagger, FakeSoMaJo([words], offsets=True), has_offsets=True)
    out = detector.detect(Document("d1", text, "de"))
    assert out.spans[0].text == "Weber"


def test_privacy_tagger_joins_a_multi_token_entity(flair_sentence):
    text = "Am Ring 14 wohnt niemand ."
    words = text.split()
    tagger = FakeTagger([[FakeFlairSpan([2, 3], "STREET", 0.8)]])
    out = PrivacyTagger().use(tagger, FakeSoMaJo([words])).detect(Document("d1", text, "de"))
    assert out.spans[0].text == "Ring 14"
    assert out.spans[0].type == "LOC"


def test_privacy_tagger_runs_on_a_corpus_it_never_saw(flair_sentence):
    """§7 runs it out of distribution on purpose: no language gate, and the language is recorded."""
    text = "Doctor Weber wrote to Kate ."
    words = text.split()
    tagger = FakeTagger([[FakeFlairSpan([2], "FAMILY", 0.5)]])
    detector = PrivacyTagger().use(tagger, FakeSoMaJo([words]))
    out = detector.detect(Document("d1", text, "en"))
    assert out.spans[0].text == "Weber"
    assert detector.languages == {"en": 1}


def test_privacy_tagger_drops_an_entity_whose_tokens_did_not_align(flair_sentence):
    text = "Herr Weber ."
    tagger = FakeTagger([[FakeFlairSpan([99], "FAMILY", 0.9)]])
    out = PrivacyTagger().use(tagger, FakeSoMaJo([text.split()])).detect(Document("d1", text, "de"))
    assert out.spans == ()


# ----------------------------------------------------------------------------- the cache contract


class StubDetector:
    name = "stub"
    family = "rule"

    def __init__(self, spans_by_doc, fail=()):
        self._spans = spans_by_doc
        self._fail = set(fail)
        self.seen: list[str] = []

    def detect(self, document):
        from pseudonymkit.detectors.base import DetectorOutput

        self.seen.append(document.doc_id)
        if document.doc_id in self._fail:
            raise RuntimeError("model went away")
        return DetectorOutput(document.doc_id, self.name, tuple(self._spans.get(document.doc_id, ())))


def test_run_detector_writes_through_the_cache(tmp_path):
    cache = DetectorCache(tmp_path, "tab")
    documents = [doc(doc_id="a"), doc(doc_id="b")]
    detector = StubDetector({"a": [Span(0, 5, "Dr. W", "PERSON", type_src="PERSON")]})
    report = run_detector(detector, documents, cache, prompt_version="v2")
    assert (report.written, report.failed, report.spans) == (2, 0, 1)
    loaded = cache.load("stub")
    assert set(loaded) == {"a", "b"}
    assert loaded["a"].spans[0].type_src == "PERSON"


def test_run_detector_resumes_and_retries_failures(tmp_path):
    cache = DetectorCache(tmp_path, "tab")
    documents = [doc(doc_id="a"), doc(doc_id="b")]
    first = StubDetector({}, fail={"b"})
    run_detector(first, documents, cache, retries=0)
    assert first.seen == ["a", "b"]

    second = StubDetector({})
    report = run_detector(second, documents, cache, retries=0)
    assert second.seen == ["b"], "a was cached; b errored and must be retried"
    assert report.skipped == 1


def test_a_transient_failure_is_retried_in_place(tmp_path):
    """The GPU faults on this cluster came in bursts and cleared on their own.

    Both privacy-tagger repairs died on an NVML assertion inside torch's caching allocator, and a
    bare re-run recovered 8 of Enron's 24 failures while losing 16 new ones to the same assertion.
    That is a transient fault, not a document the detector cannot read, and re-running a
    58,636-document pass to reach a handful of them is the expensive way to find out.
    """

    class FlakyDetector(StubDetector):
        def __init__(self, fail_times: int) -> None:
            super().__init__({})
            self.remaining = fail_times

        def detect(self, document):
            if self.remaining:
                self.remaining -= 1
                raise RuntimeError("NVML_SUCCESS == DriverAPI::get()->nvmlInit_v2_()")
            return super().detect(document)

    cache = DetectorCache(tmp_path, "tab")
    detector = FlakyDetector(fail_times=2)
    report = run_detector(detector, [doc(doc_id="a")], cache, retries=2, retry_wait=0.0)
    assert (report.written, report.failed) == (1, 0)
    assert detector.remaining == 0, "both transient failures were consumed by the retries"


def test_a_persistent_failure_still_fails_and_says_how_often_it_was_tried(tmp_path):
    """Retrying must not turn a real failure into silence — §2 says report faithfully."""
    import json

    cache = DetectorCache(tmp_path, "tab")
    report = run_detector(StubDetector({}, fail={"a"}), [doc(doc_id="a")], cache,
                          retries=2, retry_wait=0.0)
    assert (report.written, report.failed) == (0, 1)
    record = json.loads(cache.path("stub").read_text(encoding="utf-8").splitlines()[0])
    assert "after 3 attempts" in record["error"]


def test_run_detector_records_the_family_with_every_record(tmp_path):
    import json

    cache = DetectorCache(tmp_path, "tab")
    run_detector(StubDetector({}), [doc(doc_id="a")], cache, model="presidio")
    record = json.loads(cache.path("stub").read_text().splitlines()[0])
    assert record["family"] == "rule"
    assert record["model"] == "presidio"


def test_run_detector_uses_detect_many_when_a_batch_size_is_given(tmp_path):
    from pseudonymkit.detectors.base import DetectorOutput

    class Batched(StubDetector):
        def __init__(self):
            super().__init__({})
            self.batches = 0

        def detect_many(self, documents):
            self.batches += 1
            docs = list(documents)
            self.seen.extend(d.doc_id for d in docs)
            return [DetectorOutput(d.doc_id, self.name, ()) for d in docs]

    detector = Batched()
    cache = DetectorCache(tmp_path, "tab")
    run_detector(detector, [doc(doc_id=str(i)) for i in range(5)], cache, batch_size=5)
    assert detector.batches == 1


def test_all_four_levels_are_registered():
    for level in ("presidio", "gliner", "finetuned", "privacy_tagger"):
        assert level in DETECTORS
