"""The flair-version shims that let Eder et al.'s 2022 ``privacy_tagger`` run under flair 0.15.

The checkpoint (``models/privacy_tagger.pt``, 2.6 GB, cluster only) was written by flair ~0.11.
Two things about it no longer match the installed library, and both are patched in
:mod:`pseudonymkit.detectors.domain`.  Neither patch can be exercised by loading the real
checkpoint here — it is 2.6 GB and reachable only from the cluster — so these tests drive the shims
with a synthetic pickle shaped exactly like the one found inside the real file.

**Why these tests check numbers and not just "it loaded".**  Both shims sit on a path where a wrong
answer is invisible: a tagger whose byte-pair table is zeroed or misaligned still loads, still runs,
and simply finds less.  A detector pool reads that as "found nothing", which is a result rather than
a failure.  So the assertions below are on the vectors, not on the absence of an exception.
"""

from __future__ import annotations

import pytest

flair = pytest.importorskip("flair", reason="the flair shims only exist where flair is installed")
pytest.importorskip("bpemb", reason="the BPEmbSerializable shim subclasses bpemb.BPEmb")
np = pytest.importorskip("numpy")
torch = pytest.importorskip("torch")

from flair.embeddings.token import BytePairEmbeddings  # noqa: E402

from pseudonymkit.detectors.domain import _install_flair_compat_shims  # noqa: E402

DIM = 4
VOCAB = 6


@pytest.fixture(autouse=True)
def _cpu(monkeypatch):
    """Pin ``flair.device``.  The shim ends with ``self.to(flair.device)`` the way flair's own
    ``__init__`` does, and the cluster login node reports a CUDA build with no usable GPU."""
    monkeypatch.setattr(flair, "device", torch.device("cpu"))


class StubSentencePiece:
    """The two ``SentencePieceProcessor`` methods flair 0.15's ``BytePairEmbeddings`` calls.

    ``EncodeAsIds`` is deliberately sensitive to case and to digits, because that is where the old
    and new preprocessing orders could have diverged: flair 0.11 lower-cased and let bpemb fold
    digits, flair 0.15 folds digits itself and lower-cases afterwards.
    """

    def vocab_size(self) -> int:
        return VOCAB

    def EncodeAsIds(self, text: str) -> list[int]:  # noqa: N802 — sentencepiece's own name
        return [ord(c) % VOCAB for c in text] or [0]


class StubToken:
    """``_add_embeddings_internal`` touches only these three members of a token."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.embeddings: dict = {}

    def set_embedding(self, name: str, emb) -> None:
        self.embeddings[name] = emb


class StubSentence:
    def __init__(self, words) -> None:
        self.tokens = [StubToken(w) for w in words]


def _old_flair_state(*, vectors=None, do_preproc: bool = True) -> dict:
    """A ``__dict__`` shaped like the one flair 0.11 pickled for ``BytePairEmbeddings``.

    Read off the real checkpoint: the only class attributes it carries are the mangled embedding
    length, the ``BPEmbSerializable`` in ``embedder``, ``name``, ``static_embeddings`` and
    ``training`` — no ``embedding``, ``spm``, ``force_cpu``, ``field`` or ``do_preproc``.  The
    ``torch.nn.Module`` bookkeeping is taken from a real module so the migrated object is a working
    module afterwards, exactly as it is when torch unpickles one.
    """
    scaffold = object.__new__(BytePairEmbeddings)
    torch.nn.Module.__init__(scaffold)

    if vectors is None:
        vectors = np.arange(VOCAB * DIM, dtype=np.float32).reshape(VOCAB, DIM) + 1.0

    embedder = type(
        "StubBPEmb",
        (),
        {"vectors": vectors, "spm": StubSentencePiece(), "do_preproc": do_preproc},
    )()

    state = dict(scaffold.__dict__)
    state.update(
        {
            "_BytePairEmbeddings__embedding_length": DIM * 2,
            "embedder": embedder,
            "name": "1-bpe-de-100000-100",
            "static_embeddings": True,
            "training": False,
        }
    )
    return state


def _migrated(**kwargs) -> BytePairEmbeddings:
    _install_flair_compat_shims()
    obj = object.__new__(BytePairEmbeddings)
    obj.__setstate__(_old_flair_state(**kwargs))
    return obj


# --------------------------------------------------------------------- the BPEmbSerializable shim


def test_bpemb_shim_restores_the_class_the_pickle_names():
    """flair 0.15 deleted ``flair.embeddings.token.BPEmbSerializable``.  Pickle resolves a class by
    module *and* name, so the checkpoint cannot be read until that name is back at that path."""
    _install_flair_compat_shims()
    import flair.embeddings.token as token_module
    from bpemb import BPEmb

    assert issubclass(token_module.BPEmbSerializable, BPEmb)


def test_bpemb_shim_keeps_the_sentencepiece_model_inside_the_checkpoint(tmp_path):
    """The original class existed so a checkpoint would carry its SentencePiece model as
    ``spm_model_binary`` instead of a path into somebody's home directory — which is exactly why
    this 2022 checkpoint still works after the cache it was trained against disappeared."""
    _install_flair_compat_shims()
    import flair.embeddings.token as token_module

    blob = b"stand-in for a sentencepiece model"
    model_file = tmp_path / "de.wiki.bpe.vs100000.model"
    model_file.write_bytes(blob)

    obj = object.__new__(token_module.BPEmbSerializable)
    obj.__dict__.update({"model_file": model_file, "spm": object(), "lang": "de", "vs": 100000})
    state = obj.__getstate__()

    assert state["spm_model_binary"] == blob
    assert state["spm"] is None          # the live processor is not picklable and is rebuilt


# ------------------------------------------------------------------- the BytePairEmbeddings shim


def test_old_pickle_gains_the_attributes_flair_015_added():
    """``force_cpu`` is the one that fails first — ``BytePairEmbeddings._apply`` reads it while
    flair moves the freshly loaded model onto a device — but all five are needed to predict."""
    bpe = _migrated()

    assert bpe.force_cpu is True
    assert bpe.field is None
    assert bpe.do_preproc is True
    assert isinstance(bpe.spm, StubSentencePiece)
    assert isinstance(bpe.embedding, torch.nn.Embedding)
    assert not hasattr(bpe, "embedder")     # translated, not carried alongside


def test_do_preproc_is_carried_from_bpemb_rather_than_defaulted():
    """flair 0.11 delegated digit folding to bpemb's own ``do_preproc``; flair 0.15 reimplements it
    behind a flag of the same name.  Defaulting it would change the tokenisation of every number in
    the corpus — dates, ZIPs, phone numbers, which is most of what this tagger is for."""
    assert _migrated(do_preproc=False).do_preproc is False


def test_the_lookup_table_is_the_old_vectors_plus_one_zero_row():
    """flair 0.11 special-cased a blank token to a zero vector; flair 0.15 spells the same thing as
    an extra matrix row indexed at ``spm.vocab_size()``.  Rows must stay in sentencepiece id order,
    because id order is what both versions index by."""
    bpe = _migrated()
    weight = bpe.embedding.weight.detach().cpu().numpy()

    assert weight.shape == (VOCAB + 1, DIM)
    expected = np.arange(VOCAB * DIM, dtype=np.float32).reshape(VOCAB, DIM) + 1.0
    assert np.array_equal(weight[:VOCAB], expected)
    assert np.array_equal(weight[VOCAB], np.zeros(DIM, dtype=np.float32))


def test_a_vocab_that_does_not_match_the_vectors_is_reported_not_absorbed():
    """An off-by-one between the sentencepiece vocabulary and the vector matrix would give every
    token a wrong embedding while the tagger kept running.  Fail loudly instead."""
    with pytest.raises(RuntimeError, match="indexes the matrix by piece id"):
        _migrated(vectors=np.zeros((VOCAB - 1, DIM), dtype=np.float32))


def test_embedding_a_sentence_reproduces_the_flair_011_formula():
    """The behavioural test.  flair 0.11 computed ``concat(e[0], e[-1])`` over
    ``BPEmb.embed(w.lower())``, which is ``emb.vectors[encode_ids(...)]``; flair 0.15 gathers
    ``[ids[0], ids[-1]]`` out of the ``nn.Embedding``.  Migrated correctly the two agree exactly —
    on the real checkpoint this same comparison came out bit-identical over German test tokens."""
    from flair.data import Sentence

    bpe = _migrated()
    vectors = bpe.embedding.weight.detach().cpu().numpy()
    words = ["Müller", "91054", "Erlangen"]

    sentence = Sentence(words)
    bpe.embed(sentence)

    for word, token in zip(words, sentence.tokens):
        folded = "".join("0" if c.isdigit() else c for c in word).lower()
        ids = StubSentencePiece().EncodeAsIds(folded)
        reference = np.concatenate((vectors[ids[0]], vectors[ids[-1]]))
        got = token.get_embedding([bpe.name]).detach().cpu().numpy()
        assert np.allclose(got, reference), word
        assert np.linalg.norm(got) > 0     # a shim that embedded zeros would pass everything above


def test_a_blank_token_still_embeds_to_zero():
    """The one case flair 0.11 short-circuited.  Its own test because it is the only place where a
    zero vector is the right answer, and therefore the only place a zeroing bug could hide."""
    bpe = _migrated()
    sentence = StubSentence([" "])

    bpe._add_embeddings_internal([sentence])

    got = sentence.tokens[0].embeddings[bpe.name].detach().cpu().numpy()
    assert np.array_equal(got, np.zeros(DIM * 2, dtype=np.float32))


def test_a_flair_015_pickle_passes_through_unchanged():
    """The shim must not rewrite a checkpoint that is already current: a state carrying its own
    ``force_cpu``/``field``/``do_preproc`` and no ``embedder`` keeps every one of them."""
    _install_flair_compat_shims()
    state = _old_flair_state()
    state.pop("embedder")
    state.update(
        {
            "force_cpu": False,
            "field": "lemma",
            "do_preproc": False,
            "spm": StubSentencePiece(),
            "embedding": torch.nn.Embedding(VOCAB + 1, DIM),
        }
    )

    obj = object.__new__(BytePairEmbeddings)
    obj.__setstate__(state)

    assert (obj.force_cpu, obj.field, obj.do_preproc) == (False, "lemma", False)


def test_installing_the_shims_twice_is_a_no_op():
    """``PrivacyTagger.load`` can run more than once per process — a batched job loads, times and
    reloads.  Re-patching would stack ``__setstate__`` wrappers on top of each other."""
    _install_flair_compat_shims()
    first = BytePairEmbeddings.__setstate__
    _install_flair_compat_shims()

    assert BytePairEmbeddings.__setstate__ is first
