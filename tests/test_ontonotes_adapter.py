"""OntoNotes adapter — inline SGML offsets, co-reference alignment, genre and language."""

from __future__ import annotations

import io
import tarfile

from pseudonymkit.adapters import ontonotes

NAME = (
    '<DOC DOCNO="wsj_0001">\n'
    'A &amp; B told <ENAMEX TYPE="PERSON">Pierre Vinken</ENAMEX> that '
    '<ENAMEX TYPE="GPE">Paris</ENAMEX> was <ENAMEX TYPE="ORG">Elsevier</ENAMEX> .\n'
    "</DOC>\n"
)
COREF = (
    '<DOC DOCNO="wsj_0001">\n'
    'A &amp; B told <COREF ID="7">Pierre Vinken</COREF> that '
    '<COREF ID="9">Paris</COREF> was Elsevier .\n'
    "</DOC>\n"
)


def write(root, language, relative, name=NAME, coref=COREF):
    path = root / language / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".name").write_text(name, "utf-8")
    if coref is not None:
        path.with_suffix(".coref").write_text(coref, "utf-8")
    return path


# ---------------------------------------------------------------------------------- the parser


def test_offsets_survive_an_escaped_entity_before_the_span():
    text, spans = ontonotes.parse_name(NAME)
    # "&amp;" collapses to one character; a span recorded before that collapse would be shifted.
    assert "A & B told" in text
    assert [text[a:b] for a, b, _ in spans] == ["Pierre Vinken", "Paris", "Elsevier"]
    assert [label for _, _, label in spans] == ["PERSON", "GPE", "ORG"]


def test_the_doc_wrapper_is_not_part_of_the_text():
    text, _ = ontonotes.parse_name(NAME)
    assert "DOCNO" not in text and "<DOC" not in text


def test_coref_parses_to_chain_ids():
    text, spans = ontonotes.parse_coref(COREF)
    assert [(text[a:b], cid) for a, b, cid in spans] == [("Pierre Vinken", "7"), ("Paris", "9")]


# ----------------------------------------------------------------------------------- the loader


def test_load_maps_types_and_attaches_chains_on_exact_spans(tmp_path):
    write(tmp_path, "english", "nw/wsj/00/wsj_0001")
    corpus = ontonotes.load(tmp_path, languages=("english",))

    document = corpus.documents[0]
    assert document.language == "en"
    assert document.domain == "newswire"
    assert document.provenance == "real"
    assert [m.type for m in document.mentions] == ["PERSON", "LOC", "ORG"]
    assert [m.span.type_src for m in document.mentions] == ["PERSON", "GPE", "ORG"]
    # Two of the three entities are in a chain; "Elsevier" has no COREF markup, so no chain id.
    assert [m.gold_entity_id for m in document.mentions][2] is None
    assert document.metadata["has_coref"]


def test_chain_ids_are_namespaced_by_document(tmp_path):
    # OntoNotes numbers chains per document. A bare "7" in two documents would fabricate a
    # cross-document identity between two unrelated people.
    write(tmp_path, "english", "nw/wsj/00/wsj_0001")
    write(tmp_path, "english", "nw/wsj/00/wsj_0002")
    corpus = ontonotes.load(tmp_path, languages=("english",))
    ids = {m.gold_entity_id for d in corpus.documents for m in d.mentions if m.gold_entity_id}
    assert len(ids) == 4  # two chains in each of two documents, all distinct
    assert all(i.startswith("ontonotes/english/nw/wsj/00/wsj_000") for i in ids)


def test_a_misaligned_coref_layer_is_dropped_and_counted(tmp_path):
    write(tmp_path, "english", "nw/wsj/00/wsj_0001", coref="<DOC>Different text entirely.</DOC>")
    report: dict[str, ontonotes.LoadReport] = {}
    corpus = ontonotes.load(tmp_path, languages=("english",), report=report)

    assert all(m.gold_entity_id is None for m in corpus.documents[0].mentions)
    assert report["english"].coref_misaligned == 1
    assert report["english"].with_coref == 0


def test_a_document_with_no_coref_layer_is_counted_separately(tmp_path):
    write(tmp_path, "english", "nw/wsj/00/wsj_0001", coref=None)
    report: dict[str, ontonotes.LoadReport] = {}
    ontonotes.load(tmp_path, languages=("english",), report=report)
    assert report["english"].coref_absent == 1
    assert report["english"].coref_misaligned == 0


def test_basenames_repeated_across_genres_stay_distinct(tmp_path):
    # ann_0001.name exists under several genres; flattening would silently overwrite documents.
    write(tmp_path, "arabic", "nw/ann/00/ann_0001")
    write(tmp_path, "arabic", "bn/ann/00/ann_0001")
    corpus = ontonotes.load(tmp_path, languages=("arabic",))
    assert len(corpus) == 2
    assert {d.domain for d in corpus.documents} == {"newswire", "broadcast_news"}
    assert len({d.doc_id for d in corpus.documents}) == 2


def test_languages_map_to_iso_codes(tmp_path):
    for language in ("english", "chinese", "arabic"):
        write(tmp_path, language, "nw/x/00/d1")
    corpus = ontonotes.load(tmp_path)
    assert {d.language for d in corpus.documents} == {"en", "zh", "ar"}


def test_an_empty_document_is_skipped_and_counted(tmp_path):
    write(tmp_path, "english", "nw/wsj/00/wsj_0001", name="<DOC>\n</DOC>\n", coref=None)
    report: dict[str, ontonotes.LoadReport] = {}
    corpus = ontonotes.load(tmp_path, languages=("english",), report=report)
    assert len(corpus) == 0
    assert report["english"].empty == 1


# -------------------------------------------------------------------------------- the extractor


def test_extract_keeps_only_the_two_layers_and_preserves_the_genre_path(tmp_path):
    archive = tmp_path / "onto.tgz"
    members = {
        "ontonotes-release-5.0/data/files/data/english/annotations/nw/wsj/00/wsj_0001.name": NAME,
        "ontonotes-release-5.0/data/files/data/english/annotations/nw/wsj/00/wsj_0001.coref": COREF,
        "ontonotes-release-5.0/data/files/data/english/annotations/nw/wsj/00/wsj_0001.parse": "()",
        "ontonotes-release-5.0/data/files/data/arabic/annotations/bn/ann/00/ann_0001.name": NAME,
        "ontonotes-release-5.0/data/files/data/french/annotations/nw/x/00/x.name": NAME,
    }
    with tarfile.open(archive, "w:gz") as tar:
        for name, body in members.items():
            data = body.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

    destination = tmp_path / "out"
    counts = ontonotes.extract(archive, destination, languages=("english", "arabic"))

    assert counts == {"english/name": 1, "english/coref": 1, "arabic/name": 1}
    assert (destination / "english" / "nw" / "wsj" / "00" / "wsj_0001.name").is_file()
    assert (destination / "arabic" / "bn" / "ann" / "00" / "ann_0001.name").is_file()
    assert not (destination / "french").exists()          # language not requested
    assert not list(destination.rglob("*.parse"))         # layer not needed

    # And the extracted tree loads straight back.
    corpus = ontonotes.load(destination, languages=("english", "arabic"))
    assert {d.domain for d in corpus.documents} == {"newswire", "broadcast_news"}
