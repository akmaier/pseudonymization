"""Where the data lives — from the environment, never hard-coded.

Absolute cluster paths used to sit in seven scripts as literals.  Two things were wrong with that.
The small one is portability: nobody reproducing this work has a ``/cluster/<user>`` tree, so every
script needed editing before it would run.  The larger one is that those literals carry a **username**
and the location of a **DUA-restricted corpus** into a repository that is released with the paper.
CARDIO:DE is single-user and its directory is mode 700; the mode is the control, but publishing the
path is a signpost and it is exactly what this repository's own rules forbid.

So the paths come from two environment variables:

``PSEUDONYMKIT_WORK``
    The work directory holding ``data/``, ``results/``, ``models/`` and ``logs/``.  Defaults to the
    current directory, which is right when a script is run from the repository root.

``PSEUDONYMKIT_DUA``
    The root of the restricted-corpus tree.  **No default, deliberately.**  A wrong guess here would
    either fail confusingly or, worse, write derived files somewhere group-readable — the one
    mistake that would breach the grant on the day it was given.  Code that needs it and cannot find
    it stops and says which variable to set (§1: an impossible cell is reported, not substituted).

Set them in a shell file that is not tracked; ``config/env.example.sh`` shows the shape.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "WORK_ENV",
    "DUA_ENV",
    "work_dir",
    "dua_dir",
    "condition_a_dir",
    "cardiode_a",
    "cardiode_a_optional",
    "cardiode_corpus",
    "cardiode_conditions",
    "ontonotes_extract",
    "shared_corpora",
]

WORK_ENV = "PSEUDONYMKIT_WORK"
DUA_ENV = "PSEUDONYMKIT_DUA"


def work_dir() -> Path:
    """The work directory.  Defaults to ``.`` so a run from the repository root needs no setup."""
    return Path(os.environ.get(WORK_ENV, ".")).expanduser()


def dua_dir() -> Path:
    """The restricted-corpus root.  Raises if unset rather than guessing."""
    value = os.environ.get(DUA_ENV)
    if not value:
        raise SystemExit(
            f"{DUA_ENV} is not set. CARDIO:DE is DUA-restricted and single-user, so its location "
            f"is not recorded in this repository. Point {DUA_ENV} at the restricted-corpus root "
            "(mode 700, never a group-readable share) before running this. "
            "See config/env.example.sh."
        )
    return Path(value).expanduser()


def shared_corpora() -> Path:
    """The shared corpus and gazetteer tree.

    Shared with the group, and therefore **never** where a DUA-restricted corpus or anything derived
    from one may be written — that is what :func:`dua_dir` is for.  Read from
    ``PSEUDONYMKIT_CORPORA``, falling back to ``<work>/data/corpora``.
    """
    value = os.environ.get("PSEUDONYMKIT_CORPORA")
    return Path(value).expanduser() if value else work_dir() / "data" / "corpora"


def condition_a_dir() -> Path:
    """Condition A for the three unrestricted corpora."""
    return work_dir() / "data" / "conditionA"


def cardiode_a() -> Path:
    """CARDIO:DE condition A.  Under the restricted root, never under the work directory."""
    return dua_dir() / "cardiode" / "A" / "cardiode_A.jsonl.gz"


def cardiode_a_optional() -> Path | None:
    """:func:`cardiode_a`, or ``None`` when the restricted root is not configured.

    For runners that cover several corpora.  Someone reproducing this work without CARDIO:DE — which
    is everyone who has not signed their own agreement — must still be able to run TAB, OntoNotes and
    Enron, and must be *told* that the fourth corpus was skipped rather than have the whole job refuse
    to start.  Callers report the skip; none of them silently substitutes anything for it.
    """
    return cardiode_a() if os.environ.get(DUA_ENV) else None


def cardiode_corpus() -> Path:
    """The CARDIO:DE release as distributed."""
    return dua_dir() / "cardiode" / "corpus"


def cardiode_conditions() -> Path:
    """Where CARDIO:DE's conditions B and C are written — inside the restricted tree."""
    return dua_dir() / "cardiode" / "conditions"


def ontonotes_extract() -> Path:
    """The extracted OntoNotes tree."""
    return work_dir() / "data" / "ontonotes"
