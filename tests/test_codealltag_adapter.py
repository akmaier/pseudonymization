"""CodE Alltag adapter — the two utility tasks, and the Git-LFS trap under them."""

from __future__ import annotations

import json

from pseudonymkit.adapters import codealltag

LFS_POINTER = (
    "version https://git-lfs.github.com/spec/v1\n"
    "oid sha256:609b676ef6568dbe662329b9b9e0c25854f1192c8127b5d424b5861693dfa73c\nsize 19354\n"
)


def build(root, s_files=("1_0", "2_0"), xl=None, scores=None):
    """Lay out a checkout in the release's shape."""
    emails = root / "pS" / "emails"
    emails.mkdir(parents=True)
    for stem in s_files:
        (emails / f"{stem}.txt").write_text(f"Sehr geehrte Damen und Herren, {stem}", "utf-8")
    for topic, stems in (xl or {}).items():
        for i, stem in enumerate(stems):
            # The XL tree is sharded: pXL_TOPIC/<n>-/<n>-dir/<n>.txt
            shard = root / f"pXL_{topic}" / f"{i % 3 + 1}-" / f"{i}-dir"
            shard.mkdir(parents=True, exist_ok=True)
            (shard / f"{stem}.txt").write_text(f"Hallo, {topic} {stem}", "utf-8")
    formality = root / "formality_scores"
    formality.mkdir(parents=True)
    for part, mapping in (scores or {}).items():
        path = formality / f"formality_scores_documents_CodEAlltag_{part}.json"
        path.write_text(mapping if isinstance(mapping, str) else json.dumps(mapping), "utf-8")
    return root


def test_s_loads_the_donated_emails_with_surrogate_provenance(tmp_path):
    build(tmp_path)
    corpus = codealltag.load(tmp_path)

    assert len(corpus) == 2
    document = corpus.documents[0]
    assert document.language == "de"
    assert document.domain == "email"
    # Eder et al. replaced the annotated spans with realistic surrogates: tier T2, not real.
    assert document.provenance == "surrogate"
    # The release ships no span annotations, which is why detection is not scorable here.
    assert document.mentions == ()
    assert document.metadata["annotation"] == "none"


def test_the_xl_partition_is_the_topic_label(tmp_path):
    build(tmp_path, xl={"EVENTS": ["10", "11"], "TRAVELS": ["20"]})
    corpus = codealltag.load(tmp_path, parts=("XL",), topics=("EVENTS", "TRAVELS"))

    assert len(corpus) == 3
    assert codealltag.topic_labels(corpus) == {
        "codealltag/XL/EVENTS/10": "EVENTS",
        "codealltag/XL/EVENTS/11": "EVENTS",
        "codealltag/XL/TRAVELS/20": "TRAVELS",
    }


def test_shard_directories_are_flattened_away(tmp_path):
    build(tmp_path, xl={"EVENTS": ["7"]})
    document = codealltag.load(tmp_path, parts=("XL",), topics=("EVENTS",)).documents[0]
    # The shard path carries no meaning; the numeric stem is the identity the scores key on.
    assert document.doc_id == "codealltag/XL/EVENTS/7"
    assert document.metadata["file"] == "7.txt"


def test_formality_scores_are_attached_by_file_name(tmp_path):
    build(tmp_path, s_files=("73_0", "827_0"), scores={"S": {"73_0.txt": 0.958, "827_0.txt": -0.4}})
    corpus = codealltag.load(tmp_path)
    assert {d.doc_id: d.task.get("formality") for d in corpus.documents} == {
        "codealltag/S/73_0": 0.958,
        "codealltag/S/827_0": -0.4,
    }


def test_an_lfs_pointer_is_not_mistaken_for_scores(tmp_path):
    # The published repository stores these under LFS. A checkout made without git-lfs leaves a
    # ~130-byte stub; treating it as JSON would crash, treating it as "no scores" would drop the
    # formality task without saying so.
    build(tmp_path, scores={"S": LFS_POINTER})
    assert codealltag.load_formality_scores(tmp_path / "formality_scores", "S") == {}
    assert not codealltag.formality_available(tmp_path / "formality_scores", "S")

    build_dir = tmp_path / "real"
    build(build_dir, scores={"S": {"1_0.txt": 0.5}})
    assert codealltag.formality_available(build_dir / "formality_scores", "S")


def test_a_missing_score_file_leaves_the_task_key_absent(tmp_path):
    build(tmp_path)
    document = codealltag.load(tmp_path).documents[0]
    assert "formality" not in document.task


def test_per_topic_limit_keeps_the_seven_way_task_balanced(tmp_path):
    build(tmp_path, xl={"EVENTS": ["1", "2", "3"], "TRAVELS": ["4", "5", "6"]})
    corpus = codealltag.load_xl(
        tmp_path, topics=("EVENTS", "TRAVELS"), limit_per_topic=2
    )
    counts: dict[str, int] = {}
    for topic in codealltag.topic_labels(corpus).values():
        counts[topic] = counts.get(topic, 0) + 1
    assert counts == {"EVENTS": 2, "TRAVELS": 2}
    # Rate *and seed* are stamped into the corpus name: the draw is random, so without the seed the
    # provenance is incomplete and no result may be quoted from it.
    assert corpus.name == "codealltag_XL@2#0"


def test_the_per_topic_draw_is_random_and_reproducible(tmp_path):
    """It used to take a numeric prefix, and the numeric stem is archive order — not a sample."""
    build(tmp_path, xl={"EVENTS": [str(i) for i in range(1, 21)]})
    pick = lambda seed: [
        d.doc_id for d in codealltag.load_xl(
            tmp_path, topics=("EVENTS",), limit_per_topic=5, seed=seed
        ).documents
    ]
    first, again, other = pick(0), pick(0), pick(1)
    assert first == again                      # same seed, same draw
    assert first != other                      # a different seed draws differently
    assert first != [f"codealltag/XL/EVENTS/{i}" for i in range(1, 6)]   # not a prefix


def test_unusable_documents_are_excluded_before_the_draw(tmp_path):
    """XL is a raw Usenet dump: one-byte files, and text carrying U+FFFD."""
    build(tmp_path, xl={"EVENTS": [str(i) for i in range(1, 11)]})
    root = tmp_path / "pXL_EVENTS"
    files = sorted(root.rglob("*.txt"))
    files[0].write_text("x", encoding="utf-8")                       # too short
    files[1].write_text("ein besch\ufffddigter Text hier", encoding="utf-8")   # damaged
    report: dict = {}
    corpus = codealltag.load_xl(
        tmp_path, topics=("EVENTS",), min_bytes=10, drop_damaged=True, report=report
    )
    kept = {d.doc_id.rsplit("/", 1)[1] for d in corpus.documents}
    assert files[0].stem not in kept and files[1].stem not in kept
    assert report["EVENTS"] == {"found": 10, "eligible": 8, "drawn": 8}
    assert corpus.name == "codealltag_XLmin10clean"


def test_the_filter_runs_before_the_draw_so_n_is_n_usable_documents(tmp_path):
    build(tmp_path, xl={"EVENTS": [str(i) for i in range(1, 21)]})
    for path in sorted((tmp_path / "pXL_EVENTS").rglob("*.txt"))[:10]:
        path.write_text("x", encoding="utf-8")
    corpus = codealltag.load_xl(
        tmp_path, topics=("EVENTS",), limit_per_topic=8, min_bytes=10, seed=0
    )
    assert len(corpus.documents) == 8
    assert all(len(d.text) >= 10 for d in corpus.documents)


def test_numeric_ordering_makes_a_prefix_limit_reproducible(tmp_path):
    build(tmp_path, s_files=("1_0", "2_0", "10_0", "100_0"))
    corpus = codealltag.load(tmp_path, limit=3)
    assert [d.doc_id for d in corpus.documents] == [
        "codealltag/S/1_0",
        "codealltag/S/2_0",
        "codealltag/S/10_0",
    ]


def test_seven_topics_are_declared(tmp_path):
    assert len(codealltag.TOPICS) == 7
    assert set(codealltag.TOPICS) == {
        "EVENTS", "FINANCE", "GERMAN", "MOVIES", "PHILOSOPHY", "TEENS", "TRAVELS"
    }
