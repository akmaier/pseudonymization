"""Axis B: the pseudonymisation technique.

ENISA's five techniques, each reduced to the same interface: a scope key goes in, an integer index
comes out.  The surrogate form (axis C) renders that index into text, so a technique never needs to
know what a name looks like.

The point of the study is that under a deterministic policy these five differ far less than
practitioners expect, because the attack that works — frequency analysis — is distributional rather
than cryptanalytic.  Keeping them behind one interface is what makes that comparison honest.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Protocol, runtime_checkable

from cryptography.hazmat.primitives.ciphers.aead import AESSIV

from .registry import Registry

__all__ = ["Technique", "TECHNIQUES", "SPACE"]

SPACE = 1 << 32
"""Size of the index space. Rendering reduces it modulo the inventory size for that entity type."""


def _encode(scope_key: tuple[str, ...]) -> bytes:
    return "\x1f".join(scope_key).encode("utf-8")


def _int_from(digest: bytes) -> int:
    return int.from_bytes(digest[:8], "big") % SPACE


@runtime_checkable
class Technique(Protocol):
    """Maps a scope key to an index in ``[0, SPACE)``."""

    name: str
    keyed: bool
    """Whether inversion requires a secret. A1 (dictionary attack) is only defined against
    unkeyed techniques; that HMAC and AES-SIV resist it is a fact about the threat model."""

    def index(self, scope_key: tuple[str, ...], entity_type: str) -> int: ...


TECHNIQUES: Registry[Technique] = Registry("technique")


@TECHNIQUES.register("counter")
class Counter:
    """An ordinal per entity type, assigned in order of first appearance.

    ENISA: the ordinal "can still provide information on the order of the data".  That leak is the
    reason this level exists, so the iteration order is part of the experimental record — it is
    whatever order the engine visits mentions in, which is document then character offset.
    """

    name = "counter"
    keyed = False

    def __init__(self) -> None:
        self._next: dict[str, int] = {}
        self._seen: dict[tuple[str, ...], int] = {}

    def index(self, scope_key: tuple[str, ...], entity_type: str) -> int:
        if scope_key in self._seen:
            return self._seen[scope_key]
        value = self._next.get(entity_type, 0)
        self._next[entity_type] = value + 1
        self._seen[scope_key] = value
        return value


@TECHNIQUES.register("table")
class MappingTable:
    """A seeded random draw, remembered in a table.

    ENISA warns that "collisions may be an issue, as well as scalability".  Testing that warning
    requires a mode in which collisions can actually happen, so both are provided:

    * ``replacement=True``  — independent draws; two entities may collide, and the rate is measured.
    * ``replacement=False`` — draw without replacement; collisions cannot occur, and ENISA's warning
      is untestable. Included so the difference between the two is itself a reported result.
    """

    name = "table"
    keyed = True  # the table is the secret

    def __init__(self, seed: int = 0, replacement: bool = True, space: int = SPACE) -> None:
        import random

        self._rng = random.Random(seed)
        self._space = space
        self._replacement = replacement
        self._table: dict[tuple[str, ...], int] = {}
        self._used: set[int] = set()

    def index(self, scope_key: tuple[str, ...], entity_type: str) -> int:
        if scope_key in self._table:
            return self._table[scope_key]
        value = self._rng.randrange(self._space)
        if not self._replacement:
            while value in self._used:
                value = self._rng.randrange(self._space)
            self._used.add(value)
        self._table[scope_key] = value
        return value


@TECHNIQUES.register("hash")
class CryptographicHash:
    """Unkeyed SHA-256.

    ENISA: "generally considered weak as a pseudonymisation technique, as it is prone to brute
    force and dictionary attacks".  Being unkeyed is exactly what makes A1 applicable.
    """

    name = "hash"
    keyed = False

    def index(self, scope_key: tuple[str, ...], entity_type: str) -> int:
        return _int_from(hashlib.sha256(_encode(scope_key)).digest())


@TECHNIQUES.register("hmac")
class Hmac:
    """Keyed HMAC-SHA256.

    ENISA: "generally considered a robust pseudonymisation technique from a data protection point
    of view".  Deterministic and table-free, so it gives stability without storing a mapping — at
    the price that the whole corpus inverts if the key leaks.
    """

    name = "hmac"
    keyed = True

    def __init__(self, key: bytes | None = None) -> None:
        self._key = key if key is not None else b"\x00" * 32

    def index(self, scope_key: tuple[str, ...], entity_type: str) -> int:
        return _int_from(hmac.new(self._key, _encode(scope_key), hashlib.sha256).digest())


@TECHNIQUES.register("aes_siv")
class AesSiv:
    """Deterministic symmetric encryption, AES-SIV (RFC 5297).

    A random-IV mode would destroy stability outright, so a deterministic mode is required; AES-SIV
    is the honest comparator to HMAC.  Format-preserving encryption (FF1, NIST SP 800-38G) is cited
    as related work rather than run: its format preservation is a *surrogate form* property and
    would confound axis B with axis C.

    The entity type is passed as associated data, so the same string under two types encrypts
    differently.
    """

    name = "aes_siv"
    keyed = True

    def __init__(self, key: bytes | None = None) -> None:
        self._siv = AESSIV(key if key is not None else b"\x00" * 32)

    def index(self, scope_key: tuple[str, ...], entity_type: str) -> int:
        ct = self._siv.encrypt(_encode(scope_key), [entity_type.encode("utf-8")])
        return _int_from(ct)
