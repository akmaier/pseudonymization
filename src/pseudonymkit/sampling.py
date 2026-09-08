"""Subsampling a corpus — and being explicit about what each scheme costs.

Running the full factorial over 517,000 Enron messages is neither necessary nor affordable, and since
nothing in this study trains, a sample costs only statistical power.  But **there is no single fair
sample**: the sampling unit decides which structure survives, and the measurements here depend on
different structures.

The quantity that matters for the relational attacks is **per-entity evidence completeness** — how
much of one person's profile the sample still contains — not the raw document count:

============================  ===========================  =====================  ================
scheme                        profile retained per entity  entity population      within-document
============================  ===========================  =====================  ================
``by_document``               ~ *rate*                     ~ unchanged            intact
``stratified_by_subject``     ~ *rate*, evenly             unchanged              intact
``by_subject``                **higher than rate**         reduced                intact
``by_time``                   **higher than rate**         reduced to the window  intact
============================  ===========================  =====================  ================

**No scheme keeps a profile whole except taking everything.**  ``by_subject`` keeps every document of
a kept subject, so an entity confined to one mailbox survives intact — but a person who appears in
many mailboxes, which in Enron is most of the interesting ones, is still truncated by however many of
their mailboxes were dropped.  The schemes therefore rank rather than solve: subject and time
sampling retain markedly more of each profile than uniform document sampling at the same rate, and
that is the best available trade, not a guarantee.

So a uniform document sample is fair to **A2**, which reads marginal frequencies and preserves their
ranks under thinning, and unfair to **A3 and A5**, which read a profile assembled from an entity's
mentions: at *rate* = 0.1 each profile keeps a tenth of its evidence, and any co-occurrence observed
only once is lost with probability 0.9.  Subject and time sampling keep profiles whole and shrink the
population instead, which is the trade the relational attacks want.

Every sampler stamps the scheme, rate and seed into ``Corpus.name`` and each document's metadata, so
a result can never be quoted without its sampling provenance.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import replace
from typing import Callable, Sequence

from .domain import Corpus, Document

__all__ = [
    "by_document",
    "by_subject",
    "stratified_by_subject",
    "by_time",
    "SAMPLERS",
    "sample",
]


def _stamp(corpus: Corpus, documents: Sequence[Document], scheme: str, rate: float, seed: int) -> Corpus:
    tag = f"{scheme}@{rate:g}/seed{seed}"
    stamped = tuple(
        replace(d, metadata={**dict(d.metadata), "sampling": tag}) for d in documents
    )
    return Corpus(f"{corpus.name}[{tag}]", stamped)


def by_document(corpus: Corpus, rate: float, seed: int = 0) -> Corpus:
    """Uniform random documents.

    Preserves the marginal entity-frequency distribution up to scaling, so **A2 remains fair**: the
    frequency *ranks* survive thinning even though the counts do not.

    Thins every entity's profile to about ``rate`` of its mentions, and loses any co-occurrence seen
    only once with probability ``1 - rate``.  That is the wrong trade for A3 and A5, which assemble
    an entity's profile from its mentions.
    """
    docs = sorted(corpus.documents, key=lambda d: d.doc_id)
    rng = random.Random(seed)
    keep = rng.sample(docs, max(1, round(len(docs) * rate)))
    return _stamp(corpus, sorted(keep, key=lambda d: d.doc_id), "document", rate, seed)


def by_subject(corpus: Corpus, rate: float, seed: int = 0) -> Corpus:
    """Whole subjects — every document of a sampled mailbox, patient or author.

    **Every kept subject keeps all of its documents**, so profiles and cross-document identity are
    complete rather than thinned — which is what A3, A5 and the drift metric need.  The price is a
    smaller entity population and a shifted one: prolific correspondents are kept or dropped whole,
    and links to dropped subjects disappear entirely.
    """
    subjects = sorted({d.subject_id for d in corpus if d.subject_id is not None})
    if not subjects:
        raise ValueError("corpus has no subject_id; use by_document or stratified_by_subject")
    rng = random.Random(seed)
    keep = set(rng.sample(subjects, max(1, round(len(subjects) * rate))))
    docs = [d for d in corpus if d.subject_id in keep]
    return _stamp(corpus, sorted(docs, key=lambda d: d.doc_id), "subject", rate, seed)


def stratified_by_subject(corpus: Corpus, rate: float, seed: int = 0) -> Corpus:
    """A fraction of *each* subject's documents.

    Every subject stays represented in proportion, so the population is not shifted and no mailbox
    vanishes.  Profiles still thin to about ``rate``, as with :func:`by_document`, so this is the fair
    choice for detection, within-document stability and utility — not for the relational attacks.
    """
    rng = random.Random(seed)
    grouped: dict[str | None, list[Document]] = defaultdict(list)
    for doc in sorted(corpus.documents, key=lambda d: d.doc_id):
        grouped[doc.subject_id].append(doc)
    keep: list[Document] = []
    for _, docs in sorted(grouped.items(), key=lambda kv: (kv[0] is None, kv[0])):
        keep.extend(rng.sample(docs, max(1, round(len(docs) * rate))))
    return _stamp(corpus, sorted(keep, key=lambda d: d.doc_id), "stratified", rate, seed)


def by_time(
    corpus: Corpus, rate: float, seed: int = 0, key: Callable[[Document], str] | None = None
) -> Corpus:
    """A contiguous window, ordered by a date field.

    **Preserves everything inside the window** — frequencies, co-occurrence, identity — because it is
    a real corpus, merely a shorter one.  It also matches the threat model A3 and A5 assume: an
    attacker who knows an earlier period and attacks a later release.  The window's position is
    driven by ``seed``, so several windows can be compared.
    """
    def default_key(doc: Document) -> str:
        return str(doc.metadata.get("date") or doc.doc_id)

    ordered = sorted(corpus.documents, key=key or default_key)
    width = max(1, round(len(ordered) * rate))
    start = random.Random(seed).randrange(max(1, len(ordered) - width + 1))
    return _stamp(corpus, ordered[start : start + width], "time", rate, seed)


SAMPLERS: dict[str, Callable[..., Corpus]] = {
    "document": by_document,
    "subject": by_subject,
    "stratified": stratified_by_subject,
    "time": by_time,
}


def sample(corpus: Corpus, scheme: str, rate: float, seed: int = 0) -> Corpus:
    """Dispatch by name, so the scheme is a config string like every other axis."""
    try:
        sampler = SAMPLERS[scheme]
    except KeyError:
        raise KeyError(
            f"unknown sampling scheme {scheme!r}; available: {', '.join(sorted(SAMPLERS))}"
        ) from None
    if not 0 < rate <= 1:
        raise ValueError("rate must be in (0, 1]")
    return sampler(corpus, rate, seed)
