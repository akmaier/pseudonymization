"""Surrogate inventories — the one input that cannot be derived from the corpora.

Realistic and attribute-matched surrogates need name and place lists carrying **frequencies** and
**attributes**.  Frequencies are not decoration, but they do not enter A2 on this side of the fence:
:class:`~pseudonymkit.attacks.frequency.FrequencyAttack` counts how often a pseudonym occurs *in the
corpus* and never looks up the population frequency of the string it drew.  Weighting matters here
because §7 asks for a realistic, locale-appropriate surrogate, and it matters to A2 only through
``FrequencyAttack(reference=...)`` — the *attacker's* prior over real names, which is a different
list.

This module defines the port.  Adapters that load real gazetteers (census surnames, GeoNames,
national given-name registries) implement the same interface, so the engine never learns where the
names came from.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence, runtime_checkable

__all__ = ["Entry", "Inventory", "ListInventory", "SyntheticInventory"]


@dataclass(frozen=True, slots=True)
class Entry:
    """One candidate surrogate."""

    surface: str
    frequency: float = 1.0
    attributes: Mapping[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.attributes is None:
            object.__setattr__(self, "attributes", {})
        if self.frequency <= 0:
            raise ValueError("frequency must be positive")


@runtime_checkable
class Inventory(Protocol):
    """A pool of surrogates, addressable by an integer index."""

    def size(self, entity_type: str, language: str, stratum: Mapping[str, str] | None = None) -> int:
        """How many candidates exist for this type, language and attribute stratum."""

    def surface(
        self,
        index: int,
        entity_type: str,
        language: str,
        stratum: Mapping[str, str] | None = None,
    ) -> str:
        """The candidate at ``index`` (taken modulo :meth:`size`)."""


def _stratum_key(stratum: Mapping[str, str] | None) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((stratum or {}).items()))


class ListInventory:
    """An inventory backed by explicit entry lists, keyed by ``(entity_type, language)``.

    Selection is by index, so the technique alone decides which surrogate an entity receives and
    the mapping stays reproducible.  When ``frequency_matched`` is set, the index selects within a
    frequency-weighted cumulative distribution instead of uniformly, so the surrogate distribution
    imitates the real one.

    This makes A2 **harder**, not easier, and the direction is worth stating because the opposite was
    written here first.  A weighted draw gives two entities the same surrogate far more often than a
    uniform one — for a Chinese surname, p(王)² = 0.56 % against 1/1806 = 0.055 % — and
    ``FrequencyAttack._truth`` omits any pseudonym carried by more than one entity key while the
    denominator keeps it.  The collisions are wanted anyway: a natural distribution produces them,
    and they are not corrected (AM, 2026-09-10).
    """

    def __init__(
        self,
        entries: Mapping[tuple[str, str], Sequence[Entry]],
        frequency_matched: bool = False,
    ) -> None:
        self._entries = {k: tuple(v) for k, v in entries.items()}
        self._frequency_matched = frequency_matched
        self._strata: dict[tuple[str, str, tuple[tuple[str, str], ...]], tuple[Entry, ...]] = {}
        self._cum: dict[tuple[str, str, tuple[tuple[str, str], ...]], list[float]] = {}

    def _pool(
        self, entity_type: str, language: str, stratum: Mapping[str, str] | None
    ) -> tuple[Entry, ...]:
        cache_key = (entity_type, language, _stratum_key(stratum))
        cached = self._strata.get(cache_key)
        if cached is not None:
            return cached
        pool = self._entries.get((entity_type, language), ())
        if stratum:
            pool = tuple(
                e for e in pool if all(e.attributes.get(k) == v for k, v in stratum.items())
            )
            if not pool:  # no candidate matches the attributes; fall back to the unstratified pool
                pool = self._entries.get((entity_type, language), ())
        self._strata[cache_key] = pool
        if self._frequency_matched and pool:
            cum: list[float] = []
            total = 0.0
            for e in pool:
                total += e.frequency
                cum.append(total)
            self._cum[cache_key] = cum
        return pool

    def size(self, entity_type: str, language: str, stratum: Mapping[str, str] | None = None) -> int:
        return len(self._pool(entity_type, language, stratum))

    def surface(
        self,
        index: int,
        entity_type: str,
        language: str,
        stratum: Mapping[str, str] | None = None,
    ) -> str:
        pool = self._pool(entity_type, language, stratum)
        if not pool:
            # Loud on purpose. The engine now passes the *document's* language (experiment_plan.md
            # §12.2), so a corpus in a language the gazetteers do not cover stops here instead of
            # quietly receiving surrogates from another language. §1 says an impossible cell is
            # reported, not substituted, and silently falling back to English is a substitution.
            raise LookupError(
                f"no surrogates for type={entity_type!r} language={language!r}: this inventory "
                f"covers {sorted({lang for _, lang in self._entries})}"
            )
        if not self._frequency_matched:
            return pool[index % len(pool)].surface
        cum = self._cum[(entity_type, language, _stratum_key(stratum))]
        target = (index / (1 << 32)) * cum[-1]
        return pool[min(bisect.bisect_right(cum, target), len(pool) - 1)].surface


class SyntheticInventory:
    """A deterministic, dependency-free inventory used by tests and smoke runs.

    Produces stable pronounceable strings so the engine and the metrics can be exercised long
    before real gazetteers are licensed and loaded.  It is **not** suitable for the leakage
    attacks: every surrogate is drawn from one flat pool, so the surrogates carry no locale and no
    attribute, which is what §7's realistic, locale-appropriate surrogate requires of condition B.
    """

    _ONSET = ("b", "d", "f", "g", "k", "l", "m", "n", "p", "r", "s", "t", "v", "z")
    _NUCLEUS = ("a", "e", "i", "o", "u", "ei", "ou", "ae")
    _CODA = ("", "n", "r", "s", "t", "l", "ng", "ck")

    def __init__(self, pool_size: int = 4096) -> None:
        self._pool_size = pool_size

    def size(self, entity_type: str, language: str, stratum: Mapping[str, str] | None = None) -> int:
        return self._pool_size

    def surface(
        self,
        index: int,
        entity_type: str,
        language: str,
        stratum: Mapping[str, str] | None = None,
    ) -> str:
        i = index % self._pool_size
        syllables = 2 if entity_type == "PERSON" else 3
        parts = []
        for _ in range(syllables):
            parts.append(
                self._ONSET[i % len(self._ONSET)]
                + self._NUCLEUS[(i // 7) % len(self._NUCLEUS)]
                + self._CODA[(i // 13) % len(self._CODA)]
            )
            i //= 3
        return "".join(parts).capitalize()
