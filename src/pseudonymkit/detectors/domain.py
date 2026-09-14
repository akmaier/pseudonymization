"""Axis D, domain-specific level: CodEAlltag's ``privacy_tagger``.

**This level is an overfitting probe, and that is the whole reason it is in the design** (AM,
2026-09-09; ``experiment_plan.md`` §7).  ``privacy_tagger`` was fine-tuned on 3,000 *pseudonymised*
CodEAlltag e-mails, so on CodEAlltag it has already seen the substitutions it is being asked to find.
Running it there **and** on German text it has never seen — CARDIO:DE — measures how much a
corpus-trained detector inflates its own recall, a number the field assumes and nobody reports.  Its
own README concedes the mechanism from the other side: *"ORG, CITY, URL and EMAIL currently do not
get recognized well due to their replacements in the pseudonymized texts."*

So this class deliberately imposes **no language or corpus gate**.  Pointing it at English or Chinese
text is not a misuse; a near-zero score there is the measurement.  What it does do is record the
document language with the run, so a result is never read as if the model had been evaluated in
distribution.

## Two dependencies that are not interchangeable

``privacy_tagger`` is a **flair** ``SequenceTagger`` distributed as ``models/privacy_tagger.pt``, and
it was trained over **SoMaJo** tokens (``SoMaJo("de_CMC", split_camel_case=False)``).  Substituting a
different tokeniser changes the token boundaries the model was trained on, which changes its output —
so the tokeniser is part of the detector, not a detail of how it is called.

## Why the offsets are computed from tokens rather than from flair

A flair ``Sentence`` built from a token list has its own text — the tokens joined by single spaces —
and its span offsets are into *that* string, not into the document.  Reading them directly puts every
span a few characters off, increasingly so through a document, and nothing about the output looks
wrong.  The offsets here therefore come from the SoMaJo tokens' own positions in the document text:
flair supplies which tokens an entity covers, and the token table supplies where those tokens are.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..domain import Document, Span
from ..taxonomy import harmonise
from .alignment import dedupe_spans
from .base import DETECTORS, DetectorOutput

__all__ = ["PrivacyTagger", "align_tokens", "PRIVACY_TAGGER_LABELS"]

PRIVACY_TAGGER_LABELS: tuple[str, ...] = (
    "FEMALE", "MALE", "FAMILY", "ORG", "USER", "DATE", "STREET", "STREETNO", "CITY", "ZIP",
    "PASS", "UFID", "EMAIL", "URL", "PHONE",
)
"""The fifteen labels §10 maps.  Kept here so a checkpoint that emits something else is visible as a
change in the model rather than as an unexplained MISC count."""


def align_tokens(
    text: str, tokens: Sequence[str], start: int = 0, max_skip: int = 64
) -> tuple[list[tuple[int, int] | None], int]:
    """Locate each token in ``text``, left to right, returning offsets and the new cursor.

    Used only when the tokeniser does not supply character offsets itself.  The search is **bounded**
    by ``max_skip`` past the cursor: a tokeniser that normalised a token — a typographic quotation
    mark rewritten as a plain one, say — would otherwise match the next identical string hundreds of
    characters later and silently drag every following offset with it.  A token that cannot be found
    within the bound gets ``None`` and carries no span, which loses one token rather than corrupting
    the document.
    """
    offsets: list[tuple[int, int] | None] = []
    cursor = start
    for token in tokens:
        if not token:
            offsets.append(None)
            continue
        position = text.find(token, cursor, cursor + len(token) + max_skip)
        if position < 0:
            offsets.append(None)
            continue
        offsets.append((position, position + len(token)))
        cursor = position + len(token)
    return offsets, cursor


def _install_bpemb_shim() -> None:
    """Make a flair 0.11-era checkpoint unpicklable under flair 0.15.

    Eder et al.'s tagger was trained when ``flair.embeddings.token`` still defined
    ``BPEmbSerializable``; 0.15.1 removed it, so unpickling the checkpoint raises
    ``AttributeError: Can't get attribute 'BPEmbSerializable'``.  Pickle resolves a class by *name and
    module*, so restoring the name at that path is all that is required.

    The class has to reproduce the original ``__setstate__``, which is not a formality: the old flair
    stored the SentencePiece model **inside** the checkpoint as ``spm_model_binary`` rather than as a
    path, precisely so that a checkpoint would keep working when the cache moved.  Writing those bytes
    back out and reloading them is what makes the embedding usable; skipping it would leave a tagger
    that loads and then produces nothing.

    Downgrading flair instead would be the other option, and a worse one: it is shared with nothing
    else here, but pinning a four-year-old release to read one checkpoint trades a contained shim for
    an uncontained dependency.
    """
    import flair
    import flair.embeddings.token as token_module

    if hasattr(token_module, "BPEmbSerializable"):
        return
    try:
        from bpemb import BPEmb
    except ModuleNotFoundError as exc:                       # reported, never worked around (§1)
        raise RuntimeError(
            "privacy_tagger's checkpoint needs `bpemb` to unpickle its embeddings "
            "(flair 0.15 dropped BPEmbSerializable). pip install bpemb."
        ) from exc

    class BPEmbSerializable(BPEmb):                          # noqa: N801 — the pickled name
        def __getstate__(self):
            state = self.__dict__.copy()
            state["spm_model_binary"] = open(self.model_file, mode="rb").read()
            state["spm"] = None
            return state

        def __setstate__(self, state):
            from bpemb.util import sentencepiece_load

            model_file = self.model_tpl.format(lang=state["lang"], vs=state["vs"])
            self.__dict__ = state
            self.cache_dir = Path(flair.cache_root) / "embeddings"
            if "spm_model_binary" in state:
                # The checkpoint carries the SentencePiece model; write it where bpemb expects it
                # rather than re-downloading, which is the whole point of the original design.
                (self.cache_dir / state["lang"]).mkdir(parents=True, exist_ok=True)
                self.model_file = self.cache_dir / model_file
                self.model_file.write_bytes(state["spm_model_binary"])
            else:
                self.model_file = self._load_file(model_file)
            state["spm"] = sentencepiece_load(self.model_file)

    token_module.BPEmbSerializable = BPEmbSerializable


def _install_bytepair_shim() -> None:
    """Teach flair 0.15's ``BytePairEmbeddings`` how to read a flair 0.11-era pickle of itself.

    Unpickling the checkpoint restores a ``BytePairEmbeddings`` *instance* whose ``__dict__`` is the
    one flair 0.11 wrote::

        {'_BytePairEmbeddings__embedding_length': 200, 'embedder': BPEmbSerializable(...),
         'name': '1-bpe-de-100000-100', 'static_embeddings': True, ...}

    Between 0.11 and 0.15 flair rewrote the class.  Where 0.11 kept a live ``BPEmb`` object in
    ``self.embedder`` and embedded a token with ``self.embedder.embed(word.lower())`` — a numpy
    lookup, one token at a time — 0.15 keeps the same vectors in a ``torch.nn.Embedding`` and
    embeds a whole batch with one tensor gather.  That rewrite introduced five attributes the old
    pickle does not carry: ``embedding``, ``spm``, ``force_cpu``, ``field`` and ``do_preproc``.
    The first one to be touched is ``force_cpu``, in ``BytePairEmbeddings._apply``, which flair
    reaches while moving the freshly loaded model onto a device::

        AttributeError: 'BytePairEmbeddings' object has no attribute 'force_cpu'

    and behind it, at prediction time, ``spm``, ``do_preproc``, ``field`` and ``embedding`` in
    ``_add_embeddings_internal``.

    flair does this migration itself for the sibling class ``WordEmbeddings`` — see its
    ``__setstate__``, which fills in ``force_cpu``/``fine_tune``/``field`` and turns a pickled
    gensim ``precomputed_word_embeddings`` into an ``nn.Embedding``.  It simply never wrote the
    equivalent for ``BytePairEmbeddings``.  This shim is that missing ``__setstate__``, written to
    the same pattern, so what runs afterwards is flair's own unmodified 0.15 code path.

    **Why the translation is exact, not approximate.**  Old flair asked bpemb for the vectors:
    ``BPEmb.embed(t)`` is ``self.emb.vectors[self.encode_ids(t)]``, i.e. a row lookup into the same
    matrix by sentencepiece id, and old flair then kept the first and last subword vector
    (``np.concatenate((e[0], e[-1]))``).  New flair takes ``ids = spm.EncodeAsIds(word.lower())``,
    keeps ``[ids[0], ids[-1]]`` and gathers them out of ``nn.Embedding.from_pretrained(vstack(
    embedder.vectors, zeros))``.  Same matrix, same rows, same order — so rebuilding the
    ``nn.Embedding`` from ``embedder.vectors`` reproduces the old numbers rather than approximating
    them.  The appended zero row is how new flair spells the old "empty token gets a zero vector"
    branch: it indexes it as ``spm.vocab_size()``, which is why that row must line up with the end
    of the vector matrix — asserted below, because an off-by-one there would leave a tagger that
    loads, runs, and quietly returns the wrong embedding for every token.

    Preprocessing lines up too, which is worth stating because it is where a silent divergence
    would otherwise hide.  Old flair passed ``word.lower()`` to bpemb, and bpemb applied its own
    ``preprocess`` — ``re.sub(r"\\d", "0", text.lower())`` — when its ``do_preproc`` was set.  New
    flair applies ``re.sub(r"\\d", "0", word)`` itself under its own ``do_preproc`` flag and then
    lowercases inside ``EncodeAsIds(word.lower())``.  Digit folding and lowercasing commute, so the
    two agree exactly — provided ``do_preproc`` is carried over from the pickled bpemb object
    instead of being defaulted, which is what this shim does.

    ``field`` is ``None`` because flair 0.11 had no such option: it always embedded ``token.text``.
    ``force_cpu`` is ``True``, the value flair 0.15 defaults to for this class and the value its
    ``WordEmbeddings.__setstate__`` fills in for old pickles; it keeps the 100k x 100 lookup table
    on the CPU, which is where flair 0.11 kept it (a numpy array) in any case.
    """
    import flair
    import numpy as np
    import torch
    from torch import nn

    from flair.embeddings.token import BytePairEmbeddings

    if getattr(BytePairEmbeddings, "_pseudonymkit_bytepair_shim", False):
        return

    def __setstate__(self, state: dict) -> None:                 # noqa: N807 — the dunder is the API
        embedder = state.pop("embedder", None)
        if embedder is not None:
            # A flair 0.11 pickle.  Translate it; a 0.15 pickle has none of this and falls through.
            vectors = embedder.vectors
            vocab_size = embedder.spm.vocab_size()
            if vectors.shape[0] != vocab_size:
                raise RuntimeError(                              # reported, never papered over (§1)
                    "privacy_tagger's BytePairEmbeddings is inconsistent: its sentencepiece model "
                    f"has {vocab_size} pieces but its vector matrix has {vectors.shape[0]} rows. "
                    "flair 0.15 indexes the matrix by piece id, so these must match."
                )
            state["spm"] = embedder.spm
            state["do_preproc"] = bool(getattr(embedder, "do_preproc", True))
            state["embedding"] = nn.Embedding.from_pretrained(
                torch.FloatTensor(
                    np.vstack((vectors, np.zeros(vectors.shape[1], dtype=vectors.dtype)))
                ),
                freeze=True,
            )
        state.setdefault("force_cpu", True)
        state.setdefault("field", None)
        state.setdefault("do_preproc", True)
        super(BytePairEmbeddings, self).__setstate__(state)
        # __init__ ends with .to(flair.device); _add_embeddings_internal reads self.device, and an
        # old pickle carries none.  force_cpu=True makes this a no-op move that only sets the flag.
        self.to(flair.device)

    BytePairEmbeddings.__setstate__ = __setstate__
    BytePairEmbeddings._pseudonymkit_bytepair_shim = True


def _install_flair_compat_shims() -> None:
    """Every compatibility patch needed to read Eder et al.'s 2022 checkpoint under flair 0.15.

    Kept as one entry point so a caller cannot install half of them, and so the reason they exist —
    a checkpoint frozen at flair ~0.11 against a library four minor versions ahead of it — is stated
    in one place.  Each patch is documented at its own definition.
    """
    _install_bpemb_shim()
    _install_bytepair_shim()


@DETECTORS.register("privacy_tagger")
@dataclass
class PrivacyTagger:
    """The CodEAlltag domain detector: flair sequence tagger over SoMaJo tokens."""

    model_path: Path | str = "models/privacy_tagger.pt"
    somajo_language: str = "de_CMC"
    split_camel_case: bool = False
    tag_type: str | None = None
    """``None`` takes the tagger's own ``tag_type``, so a checkpoint that labels something other than
    ``ner`` still works and the choice is recorded rather than assumed."""
    mini_batch_size: int = 32
    name: str = "privacy_tagger"
    family: str = "domain"
    _tagger: Any = field(default=None, init=False, repr=False)
    _tokenizer: Any = field(default=None, init=False, repr=False)
    _has_offsets: bool = field(default=False, init=False, repr=False)
    _languages: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    # ------------------------------------------------------------------ set-up

    def load(self) -> None:
        """Load the checkpoint and build the tokeniser.  Separate so a job can time the load."""
        from flair.models import SequenceTagger
        from somajo import SoMaJo

        _install_flair_compat_shims()
        self._tagger = SequenceTagger.load(str(self.model_path))
        try:
            self._tokenizer = SoMaJo(
                self.somajo_language,
                split_camel_case=self.split_camel_case,
                character_offsets=True,
            )
            self._has_offsets = True
        except TypeError:
            # SoMaJo < 2.2 has no character_offsets argument; align_tokens() covers that case.
            self._tokenizer = SoMaJo(
                self.somajo_language, split_camel_case=self.split_camel_case
            )
            self._has_offsets = False

    def use(self, tagger: Any, tokenizer: Any, has_offsets: bool = False) -> PrivacyTagger:
        """Inject an already-loaded tagger and tokeniser.  Used by tests and by a batched job."""
        self._tagger = tagger
        self._tokenizer = tokenizer
        self._has_offsets = has_offsets
        return self

    @property
    def languages(self) -> dict[str, int]:
        """Document language -> how many documents were tagged.  Reported with the run, because this
        detector is run out of its training distribution on purpose (§7)."""
        return dict(self._languages)

    # ------------------------------------------------------------------ tokenisation

    def sentences(self, text: str) -> list[tuple[list[str], list[tuple[int, int] | None]]]:
        """Tokenise into sentences of ``(token strings, character offsets)``.

        Offsets come from SoMaJo where the installed version supplies them and from
        :func:`align_tokens` otherwise; the cursor is carried across sentences either way, so a
        token repeated later in the document cannot be matched against an earlier occurrence.
        """
        out: list[tuple[list[str], list[tuple[int, int] | None]]] = []
        cursor = 0
        for sentence in self._tokenizer.tokenize_text([text]):
            words = [t.text for t in sentence]
            if not words:
                continue
            if self._has_offsets:
                offsets: list[tuple[int, int] | None] = [
                    tuple(t.character_offset) if getattr(t, "character_offset", None) else None
                    for t in sentence
                ]
                last = [o for o in offsets if o]
                if last:
                    cursor = max(cursor, last[-1][1])
            else:
                surfaces = [getattr(t, "original_spelling", None) or t.text for t in sentence]
                offsets, cursor = align_tokens(text, surfaces, cursor)
            out.append((words, offsets))
        return out

    # ------------------------------------------------------------------ detection

    @staticmethod
    def _label(span: Any, tag_type: str) -> tuple[str, float]:
        """Read a flair span's label across flair versions.

        flair >= 0.11 puts it behind ``get_label``; earlier releases expose ``tag`` and ``score``
        directly.  Both are handled because the cluster's environment is not ours to pin.
        """
        getter = getattr(span, "get_label", None)
        if getter is not None:
            label = getter(tag_type)
            value = getattr(label, "value", None)
            if value:
                return str(value), float(getattr(label, "score", 0.0) or 0.0)
        return str(getattr(span, "tag", "")), float(getattr(span, "score", 0.0) or 0.0)

    def detect(self, document: Document) -> DetectorOutput:
        return self.detect_many([document])[0]

    def detect_many(self, documents: Iterable[Document]) -> list[DetectorOutput]:
        """Tag every sentence of every document in one flair call.

        flair batches internally, and a sentence is short, so the per-call overhead would otherwise
        dominate: an Enron mailbox is thousands of sentences.
        """
        if self._tagger is None or self._tokenizer is None:
            self.load()
        tag_type = self.tag_type or getattr(self._tagger, "tag_type", "ner")

        from flair.data import Sentence

        docs = list(documents)
        sentences: list[Any] = []
        owner: list[tuple[int, list[tuple[int, int] | None]]] = []
        for index, document in enumerate(docs):
            key = document.language or "unknown"
            self._languages[key] = self._languages.get(key, 0) + 1
            for words, offsets in self.sentences(document.text):
                sentences.append(Sentence(words))
                owner.append((index, offsets))

        if sentences:
            self._tagger.predict(sentences, mini_batch_size=self.mini_batch_size)

        per_document: list[list[Span]] = [[] for _ in docs]
        for sentence, (index, offsets) in zip(sentences, owner):
            document = docs[index]
            for span in sentence.get_spans(tag_type):
                positions = [
                    offsets[token.idx - 1]
                    for token in span.tokens
                    if 0 < token.idx <= len(offsets) and offsets[token.idx - 1] is not None
                ]
                if not positions:
                    continue                     # every token of this entity failed to align
                start = min(p[0] for p in positions)
                end = max(p[1] for p in positions)
                raw, score = self._label(span, tag_type)
                per_document[index].append(
                    Span(
                        start=start,
                        end=end,
                        text=document.text[start:end],
                        type=harmonise(raw, "privacy_tagger")[0],
                        type_src=raw,
                        source=self.name,
                        score=score,
                    )
                )
        return [
            DetectorOutput(d.doc_id, self.name, tuple(dedupe_spans(spans)))
            for d, spans in zip(docs, per_document)
        ]
