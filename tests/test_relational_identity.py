"""A3 and A5 need an identity the corpus asserts across documents — and must say so when there is none.

Both attacks link a query mention to a profile of the same person built from *other* documents.
TAB's and OntoNotes' co-reference is document-scoped: every gold entity id is prefixed with the
document it came from, and 0 of TAB's 8,701 PERSON entities (0 of OntoNotes' 13,230) appear in a
second document.  After the document-disjoint split no query's true identity is in the gallery, so
both attacks return Rank-1 = 0 for every span source *and* for the condition-A ceiling.

That zero is not a result.  Read off the table it says pseudonymisation defeats structural linkage
on TAB, when in fact the attack had no true match to find.  These tests pin the distinction.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from sweep_leakage import relational_identity  # noqa: E402

from pseudonymkit.domain import Corpus, Document, Mention, Span  # noqa: E402


def _doc(doc_id: str, entity_ids: list[str]) -> Document:
    text = " ".join(f"Person{i}" for i in range(len(entity_ids))) or "nothing here"
    mentions, cursor = [], 0
    for index, entity in enumerate(entity_ids):
        surface = f"Person{index}"
        start = text.index(surface, cursor)
        mentions.append(Mention(
            doc_id=doc_id,
            mention_id=f"{doc_id}_m{index}",
            span=Span(start, start + len(surface), surface, "PERSON"),
            gold_entity_id=entity,
        ))
        cursor = start + len(surface)
    return Document(doc_id=doc_id, text=text, language="en", mentions=tuple(mentions))


def test_document_scoped_coreference_is_reported_as_not_computable():
    """TAB's shape: each entity id carries its own document's name, so nothing is shared."""
    corpus = Corpus("tab", (
        _doc("001-90194", ["001-90194_e1", "001-90194_e2"]),
        _doc("002-11111", ["002-11111_e1"]),
    ))
    computable, why = relational_identity(corpus, "PERSON", {"001-90194"}, {"002-11111"})
    assert computable is False
    assert "document-scoped" in why
    assert "0 shared" in why


def test_cross_document_identity_is_reported_as_computable():
    """Enron's shape: the e-mail address is the same string in every mailbox it appears in."""
    corpus = Corpus("enron", (
        _doc("mail/1", ["kay.mann@enron.com", "vince.kaminski@enron.com"]),
        _doc("mail/2", ["kay.mann@enron.com"]),
    ))
    computable, why = relational_identity(corpus, "PERSON", {"mail/1"}, {"mail/2"})
    assert computable is True
    assert "1 PERSON identities" in why


def test_only_the_two_halves_of_the_split_are_considered():
    """A document in neither half must not create an overlap that the attack cannot use."""
    corpus = Corpus("x", (
        _doc("g", ["e1"]),
        _doc("q", ["e2"]),
        _doc("held-out", ["e1", "e2"]),          # shares with both, but is in neither half
    ))
    computable, _ = relational_identity(corpus, "PERSON", {"g"}, {"q"})
    assert computable is False


def test_the_entity_type_is_respected():
    """An ORG shared across the split does not make a PERSON attack computable."""
    shared = Mention(doc_id="g", mention_id="g_m0",
                     span=Span(0, 5, "Enron", "ORG"), gold_entity_id="org1")
    gallery = Document(doc_id="g", text="Enron and Person0", language="en", mentions=(shared,))
    query = Document(doc_id="q", text="Enron and Person0", language="en", mentions=(
        Mention(doc_id="q", mention_id="q_m0",
                span=Span(0, 5, "Enron", "ORG"), gold_entity_id="org1"),))
    corpus = Corpus("x", (gallery, query))
    assert relational_identity(corpus, "PERSON", {"g"}, {"q"})[0] is False
    assert relational_identity(corpus, "ORG", {"g"}, {"q"})[0] is True
