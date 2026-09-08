"""Adapter: CodE Alltag — German e-mail — -> the domain model.

CodE Alltag is the study's German e-mail corpus and its **direct methodological baseline**: Eder et
al. (LREC 2020, ACL Anthology R19-1030) detect privacy-bearing spans and then replace them with
*"synthetically generated surrogates"*.  That is exactly the pipeline this study varies, one axis at
a time, so the corpus is where our engine meets the closest published prior art.

Three release parts matter, and they play different roles:

* ``pS/emails`` — **CodE Alltag_S**, 800 donated e-mails from 460 donors.  Its README states that
  *"privacy-sensitive text spans were annotated manually before substituting them with realistic
  surrogates automatically"*: identifier provenance **``surrogate`` (tier T2)**, not ``real``.  The
  span annotations themselves are **not in the release**, which is why the corpus is utility-only in
  ``experiment_plan.md`` §4 — there is no gold against which to score detection.
* ``pXL_<TOPIC>`` — **CodE Alltag_XL**, seven topic partitions (EVENTS, FINANCE, GERMAN, MOVIES,
  PHILOSOPHY, TEENS, TRAVELS) harvested from public mailing lists.  The partition *is* the label for
  the seven-way topic task, so no external annotation is needed.
* ``formality_scores`` — per-document formality in ``[-1, +1]``, from Eder et al.'s transformer
  scorers.  A **continuous** per-document target, which the utility protocol scores as an error
  against the original-text prediction rather than as a class.

The XL tree is sharded — ``pXL_EVENTS/1-/100-dir/100000.txt`` — because the partitions run to
hundreds of thousands of files.  The shard directories carry no meaning and are flattened away here;
the numeric stem is the document identity the formality scores key on.

**These files are distributed under a custom academic licence and are not redistributable.** The
adapter reads a local checkout; nothing here ships corpus text.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterator, Mapping, Sequence

from ..domain import Corpus, Document

__all__ = ["TOPICS", "load", "load_s", "load_xl", "load_formality_scores"]

TOPICS: tuple[str, ...] = (
    "EVENTS",
    "FINANCE",
    "GERMAN",
    "MOVIES",
    "PHILOSOPHY",
    "TEENS",
    "TRAVELS",
)
"""The seven CodE Alltag_XL partitions, which double as the topic-classification labels."""


def load_formality_scores(directory: Path | str, part: str) -> dict[str, float]:
    """Read one ``formality_scores_documents_CodEAlltag_<part>.json``.

    ``part`` is ``"S"`` or ``"XL_<TOPIC>"``.  Keys are file names as the release writes them
    (``"73_0.txt"`` in S, ``"18739.txt"`` in XL); the value is the document's formality in
    ``[-1, +1]``, +1 most formal.

    Returns an empty mapping when the file is absent **or is still a Git-LFS pointer** — the
    published repository stores these under LFS, and a checkout made without ``git-lfs`` leaves a
    ~130-byte stub in place of the data.  Silently treating a stub as "no scores" would drop the
    formality task without saying so, so the caller is told which it was via the empty result plus
    :func:`formality_available`.
    """
    path = Path(directory) / f"formality_scores_documents_CodEAlltag_{part}.json"
    if not path.is_file():
        return {}
    raw = path.read_text("utf-8", errors="replace")
    if raw.startswith("version https://git-lfs"):
        return {}
    return {str(k): float(v) for k, v in json.loads(raw).items()}


def formality_available(directory: Path | str, part: str) -> bool:
    """Whether real formality scores — not an LFS stub — are present for ``part``."""
    path = Path(directory) / f"formality_scores_documents_CodEAlltag_{part}.json"
    return path.is_file() and not path.read_text("utf-8", errors="replace").startswith(
        "version https://git-lfs"
    )


def _document(
    path: Path,
    doc_id: str,
    topic: str | None,
    formality: float | None,
    part: str,
) -> Document:
    task: dict[str, object] = {"name": "codealltag_utility"}
    if topic is not None:
        task["topic"] = topic
    if formality is not None:
        task["formality"] = formality
    return Document(
        doc_id=doc_id,
        text=path.read_text("utf-8", errors="replace"),
        language="de",
        mentions=(),  # the release carries no span annotations; detection is not scorable here
        corpus="codealltag",
        domain="email",
        # Eder et al. replaced the annotated spans with realistic surrogates: tier T2, not real
        # identifiers, and axis F is exactly the contrast that makes this worth recording.
        provenance="surrogate",
        subject_id=None,  # donors are not identified in the release; S has 460 behind 800 e-mails
        task=task,
        metadata={"annotation": "none", "part": part, "file": path.name},
    )


def load_s(
    root: Path | str,
    limit: int | None = None,
    formality_dir: Path | str | None = None,
) -> Corpus:
    """CodE Alltag_S: the 800 donated e-mails, with formality where the scores are present."""
    root = Path(root)
    scores = load_formality_scores(formality_dir, "S") if formality_dir else {}
    paths = sorted((root / "pS" / "emails").glob("*.txt"), key=_numeric_key)
    if limit is not None:
        paths = paths[:limit]
    documents = [
        _document(p, f"codealltag/S/{p.stem}", None, scores.get(p.name), "S") for p in paths
    ]
    return Corpus("codealltag_S", tuple(documents))


def load_xl(
    root: Path | str,
    topics: Sequence[str] = TOPICS,
    limit_per_topic: int | None = None,
    formality_dir: Path | str | None = None,
    progress: Callable[[str], None] | None = None,
) -> Corpus:
    """CodE Alltag_XL: the seven topic partitions, flattened out of their shard directories.

    ``limit_per_topic`` is a **sampling rate applied per label**, so the seven-way task stays
    balanced.  It is a declared experimental parameter (``experiment_plan.md`` §5) and is stamped
    into the corpus name; it is never a way to make a run finish.
    """
    root = Path(root)
    documents: list[Document] = []
    for topic in topics:
        directory = root / f"pXL_{topic}"
        if not directory.is_dir():
            continue
        scores = load_formality_scores(formality_dir, f"XL_{topic}") if formality_dir else {}
        paths = sorted(directory.rglob("*.txt"), key=_numeric_key)
        if limit_per_topic is not None:
            paths = paths[:limit_per_topic]
        for path in paths:
            documents.append(
                _document(
                    path,
                    f"codealltag/XL/{topic}/{path.stem}",
                    topic,
                    scores.get(path.name),
                    f"XL_{topic}",
                )
            )
        if progress:
            progress(f"codealltag XL/{topic}: {len(paths)} documents")
    suffix = f"@{limit_per_topic}" if limit_per_topic is not None else ""
    return Corpus(f"codealltag_XL{suffix}", tuple(documents))


def load(
    root: Path | str,
    parts: Sequence[str] = ("S",),
    limit: int | None = None,
    limit_per_topic: int | None = None,
    topics: Sequence[str] = TOPICS,
    progress: Callable[[str], None] | None = None,
) -> Corpus:
    """Load ``"S"``, ``"XL"`` or both from one CodE Alltag checkout.

    ``root`` is the directory holding ``pS/``, ``pXL_*/`` and ``formality_scores/``; the formality
    file is located relative to it, so callers never pass two paths that could drift apart.
    """
    root = Path(root)
    formality_dir = root / "formality_scores"
    documents: list[Document] = []
    if "S" in parts:
        documents.extend(load_s(root, limit, formality_dir).documents)
    if "XL" in parts:
        documents.extend(
            load_xl(root, topics, limit_per_topic, formality_dir, progress).documents
        )
    return Corpus("codealltag", tuple(documents))


def _numeric_key(path: Path) -> tuple[int, str]:
    """Sort ``1.txt`` before ``10.txt``, so a prefix limit is a stable, reproducible sample."""
    head = path.stem.split("_", 1)[0]
    return (int(head) if head.isdigit() else 1 << 62, path.stem)


def topic_labels(corpus: Corpus) -> Mapping[str, str]:
    """doc_id -> topic, for the documents that carry one."""
    return {
        d.doc_id: str(d.task["topic"]) for d in corpus.documents if "topic" in d.task
    }


def iter_documents(corpus: Corpus) -> Iterator[Document]:
    return iter(corpus.documents)
