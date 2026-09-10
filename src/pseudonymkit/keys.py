"""Axis: the entity key.

The key decides what counts as "the same entity", and therefore whether two mentions receive the
same pseudonym.  Keying on the gold co-reference chain would make fragmentation zero by
construction and measure nothing; keying on the surface form is what a deployed system does.

The normalisers below are the levels N0-N4; condition B fixes the normaliser at N2 (``experiment_plan.md`` §7), where
they trace a monotone collision-fragmentation frontier before any cryptography is involved.  N2 is
the default; all five are run as a reported sub-axis.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Protocol, runtime_checkable

from .registry import Registry

__all__ = ["Normaliser", "NORMALISERS", "entity_key"]

_HONORIFICS = (
    "mr", "mrs", "ms", "miss", "mx", "dr", "prof", "professor", "sir", "lord", "lady",
    "judge", "justice", "president", "chancellor", "minister", "rev", "reverend",
    "capt", "col", "gen", "sgt", "lt", "hon", "herr", "frau", "monsieur", "madame",
    "mme", "mlle", "señor", "señora", "sr", "sra", "dhr", "mevr",
)
_HONORIFIC_RE = re.compile(rf"^(?:{'|'.join(_HONORIFICS)})\b\.?\s*", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[.,;:!?'\"()\[\]{}<>«»„“”‘’]")
_WS_RE = re.compile(r"\s+")


@runtime_checkable
class Normaliser(Protocol):
    """Maps a mention's surface form to the key under which it is pseudonymised."""

    name: str

    def __call__(self, surface: str, entity_type: str) -> str: ...


NORMALISERS: Registry[Normaliser] = Registry("key normaliser")


class _Normaliser:
    """Base for the built-in normalisers; each stage is additive over the previous one."""

    name = "N0"

    def __call__(self, surface: str, entity_type: str) -> str:  # noqa: ARG002 - type unused here
        return self.transform(surface)

    def transform(self, surface: str) -> str:
        return surface


@NORMALISERS.register("N0")
class RawSurface(_Normaliser):
    """N0 — the surface form verbatim. Maximum fragmentation, zero key collisions."""

    name = "N0"


@NORMALISERS.register("N1")
class Casefold(_Normaliser):
    """N1 — Unicode casefold and whitespace collapse."""

    name = "N1"

    def transform(self, surface: str) -> str:
        return _WS_RE.sub(" ", unicodedata.normalize("NFKC", surface).strip()).casefold()


@NORMALISERS.register("N2")
class StripTitles(Casefold):
    """N2 — N1 plus honorifics and punctuation removed. The default."""

    name = "N2"

    def transform(self, surface: str) -> str:
        text = _PUNCT_RE.sub("", super().transform(surface))
        text = _HONORIFIC_RE.sub("", text)
        return _WS_RE.sub(" ", text).strip()


@NORMALISERS.register("N3")
class DropInitials(StripTitles):
    """N3 — N2 plus single-letter initials dropped, so 'f weber' and 'weber' unify."""

    name = "N3"

    def transform(self, surface: str) -> str:
        text = super().transform(surface)
        kept = " ".join(tok for tok in text.split() if len(tok) > 1)
        return kept or text


@NORMALISERS.register("N4")
class LastTokenOnly(DropInitials):
    """N4 — the final token only (surname, or the head of a place name).

    Minimum fragmentation, and on TAB the highest collision rate by a wide margin: 9.0 % for
    PERSON. Included because it is what naive implementations do.
    """

    name = "N4"

    def transform(self, surface: str) -> str:
        text = super().transform(surface)
        tokens = text.split()
        return tokens[-1] if tokens else text


def entity_key(surface: str, entity_type: str, normaliser: Normaliser) -> str:
    """Build the key for a mention.

    The entity type is part of the key: a person and a city that normalise to the same string are
    different entities and must not share a pseudonym.
    """
    return f"{entity_type}\x1f{normaliser(surface, entity_type)}"
