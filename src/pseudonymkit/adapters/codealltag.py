"""Adapter: CodE Alltag — German e-mail — -> the domain model.

**The corpus is OUT of the study** (AM, 2026-09-11, ``experiment_plan.md`` §11): the release carries
no gold spans, so utility measured on it is not attributable to a method.  This adapter is kept
because it works and because the decision could be revisited if annotations ever appear — it is not
called by anything in ``experiments/``.  Do not re-add the corpus to a run without AM's decision.

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

**The corpus is CC BY-SA 4.0** — the LICENSE in every ``codealltag`` repository is the unmodified
Creative Commons legal code with no added non-commercial, research-only or no-redistribution clause
(verified 2026-09-10; ``data/candidates.md`` records the same).  ShareAlike is what bites: anything
we release that is derived from this text — a re-pseudonymised corpus, for instance — is Adapted
Material and must go out under CC BY-SA 4.0 or a compatible licence, with attribution and an
indication that it was modified.  That is unlike every other corpus in the study.

The adapter reads a local checkout; nothing here ships corpus text.
"""

from __future__ import annotations

import json
import random
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
        # Eder et al. replaced the annotated spans with realistic surrogates, so what stands here is
        # already a pseudonym: "surrogate", never "real".  Condition A on this corpus is therefore
        # not full data, and any leakage number measured on it attacks surrogates rather than real
        # identities (experiment_plan.md §11).
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


_REPLACEMENT = b"\xef\xbf\xbd"
"""UTF-8 for U+FFFD.  Read as bytes so a damaged file is detected without decoding it first."""


def _eligible(path: Path, min_bytes: int, drop_damaged: bool) -> bool:
    """Whether one XL document can carry a measurement at all.

    Size comes from ``stat`` and the file is opened only if it survives that, because the size test
    rejects a large share of XL and reading 1.47 M small files over a shared filesystem is the
    expensive half of the job.
    """
    try:
        if min_bytes and path.stat().st_size < min_bytes:
            return False
        if not drop_damaged:
            return True
        return _REPLACEMENT not in path.read_bytes()
    except OSError:
        return False


def load_xl(
    root: Path | str,
    topics: Sequence[str] = TOPICS,
    limit_per_topic: int | None = None,
    formality_dir: Path | str | None = None,
    progress: Callable[[str], None] | None = None,
    seed: int = 0,
    min_bytes: int = 0,
    drop_damaged: bool = False,
    report: dict[str, dict[str, int]] | None = None,
) -> Corpus:
    """CodE Alltag_XL: the seven topic partitions, flattened out of their shard directories.

    ``limit_per_topic`` is a **sampling rate applied per label**, so the seven-way task stays
    balanced.  It is a declared experimental parameter (``experiment_plan.md`` §13) and is stamped
    into the corpus name; it is never a way to make a run finish.

    **The draw is random under ``seed``, not a prefix.**  It used to take the first *n* paths in
    numeric order, and the numeric stem is archive order — so a prefix is a slice of the archive's
    beginning, correlated with time and with thread structure, not a sample of the partition.  The
    seed is stamped into the corpus name alongside *n*.

    ``min_bytes`` and ``drop_damaged`` are the **eligibility filter**, applied *before* the draw so
    that *n* is *n* usable documents rather than *n* candidates.  XL is a raw Usenet dump — the
    release README calls it *"merely rudimentary data cleansing"* — and it contains documents of one
    byte and documents whose text carries the Unicode replacement character.  A detector's behaviour
    on those measures the dump, not the method.  Both thresholds are stamped into the name, and
    ``report`` receives the per-topic counts so the exclusion is reportable rather than silent.
    """
    root = Path(root)
    documents: list[Document] = []
    for topic in topics:
        directory = root / f"pXL_{topic}"
        if not directory.is_dir():
            continue
        scores = load_formality_scores(formality_dir, f"XL_{topic}") if formality_dir else {}
        paths = sorted(directory.rglob("*.txt"), key=_numeric_key)
        found = len(paths)
        if min_bytes or drop_damaged:
            paths = [p for p in paths if _eligible(p, min_bytes, drop_damaged)]
        eligible = len(paths)
        if limit_per_topic is not None and limit_per_topic < eligible:
            paths = sorted(
                random.Random(f"{seed}:{topic}").sample(paths, limit_per_topic),
                key=_numeric_key,
            )
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
        if report is not None:
            report[topic] = {"found": found, "eligible": eligible, "drawn": len(paths)}
        if progress:
            progress(
                f"codealltag XL/{topic}: {found} found, {eligible} eligible, {len(paths)} drawn"
            )
    marks = []
    if limit_per_topic is not None:
        marks.append(f"@{limit_per_topic}#{seed}")
    if min_bytes:
        marks.append(f"min{min_bytes}")
    if drop_damaged:
        marks.append("clean")
    return Corpus(f"codealltag_XL{''.join(marks)}", tuple(documents))


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
