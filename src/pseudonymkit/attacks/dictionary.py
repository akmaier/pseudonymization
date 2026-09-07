"""A1 — dictionary / brute-force inversion.

The attacker enumerates candidate names, pushes each through the victim's pipeline, and matches the
result against the pseudonyms in the released corpus.  Kerckhoffs's assumption applies: everything
about the pipeline is public except the key, so the attacker knows the normaliser, the technique and
the surrogate inventory.

Two consequences shape this module, and both are properties of the threat model rather than results:

* **A1 is only defined against unkeyed techniques.**  Without the key, HMAC and AES-SIV cannot be
  evaluated by the attacker at all; the mapping table and the counter cannot be reproduced either.
  Reporting "HMAC resisted the dictionary attack" as a finding would be a category error, so
  :meth:`DictionaryAttack.run` refuses to score a keyed technique and says why.
* **A1 is only meaningful under a deterministic policy.**  Under document- or fully-randomised
  policies the scope key includes a document or mention identifier the attacker would also have to
  guess, which turns a dictionary attack into a different, much weaker attack.

The interesting output is not the headline rate but the **curve against name frequency**: a
dictionary contains common names and misses rare ones, so hashing protects exactly the names that
identify people and exposes exactly the ones that do not.
"""

from __future__ import annotations

from collections import Counter
from typing import Callable, Iterable, Mapping, Sequence

from ..domain import Mention, Span
from ..engine import PseudonymisedCorpus
from ..keys import Normaliser, entity_key
from ..surrogates import SurrogateForm
from ..techniques import Technique
from .base import AttackResult

__all__ = ["DictionaryAttack", "deterministic_inverter"]

_LENGTH_BANDS: tuple[tuple[str, int, int], ...] = (
    ("<=4", 0, 4),
    ("5-7", 5, 7),
    ("8-11", 8, 11),
    ("12+", 12, 1 << 20),
)


def deterministic_inverter(
    normaliser: Normaliser,
    technique: Technique,
    surrogate: SurrogateForm,
    entity_type: str,
    language: str = "en",
) -> Callable[[str], str]:
    """Reproduce the victim's pipeline for a candidate name, under a deterministic policy.

    The attacker rebuilds the same chain the defender ran — normalise, key, index, render — because
    all of it is public.  Only the deterministic policy is supported: see the module docstring.
    """

    def render(candidate: str) -> str:
        key = entity_key(candidate, entity_type, normaliser)
        index = technique.index((key,), entity_type)
        probe = Mention("", "", Span(0, len(candidate), candidate, entity_type))
        return surrogate.render(index, probe, language)

    return render


def _length_band(name: str) -> str:
    n = len(name)
    for label, low, high in _LENGTH_BANDS:
        if low <= n <= high:
            return label
    return _LENGTH_BANDS[-1][0]


class DictionaryAttack:
    """Invert pseudonyms by enumerating a candidate name list.

    ``candidates`` are ``(surface, frequency)`` pairs — a census surname table, a gazetteer, or the
    surrogate inventory itself.  Frequencies are used only to band the results; the attack tries
    every candidate.
    """

    name = "a1_dictionary"
    requires_unkeyed = True

    def __init__(self, candidates: Iterable[tuple[str, float]]) -> None:
        self._candidates = tuple(candidates)

    def run(
        self,
        result: PseudonymisedCorpus,
        entity_type: str,
        policy: str,
        technique: Technique,
        inverter: Callable[[str], str] | None = None,
    ) -> AttackResult:
        observed = self._observed(result, entity_type)
        keyed = getattr(technique, "keyed", True)
        technique_name = getattr(technique, "name", str(technique))

        if keyed or inverter is None:
            return AttackResult(
                attack=self.name,
                entity_type=entity_type,
                policy=policy,
                technique=technique_name,
                candidates=len(observed),
                recovered_top1=0,
                recovered_top5=0,
                accuracy_top1=0.0,
                accuracy_top5=0.0,
                notes=(
                    "not applicable: the technique is keyed, so the attacker cannot evaluate the "
                    "function. This is the threat model, not a measured resistance."
                ),
            )
        if policy != "deterministic":
            return AttackResult(
                attack=self.name, entity_type=entity_type, policy=policy,
                technique=technique_name, candidates=len(observed),
                recovered_top1=0, recovered_top5=0, accuracy_top1=0.0, accuracy_top5=0.0,
                notes=(
                    "not applicable: under a non-deterministic policy the scope key carries a "
                    "document or mention id the attacker would also have to guess."
                ),
            )

        # The attacker's table: pseudonym -> the candidate name that produces it, plus that
        # candidate's frequency.  Banding is keyed on the *pseudonym* rather than on the true name,
        # because the true name in the mapping is the normalised key and the dictionary holds raw
        # surfaces; and because "is this pseudonym in my rainbow table" is precisely the attacker's
        # own view of whether a name was enumerated.
        rainbow: dict[str, str] = {}
        frequency_by_pseudonym: dict[str, float] = {}
        for candidate, frequency in self._candidates:
            pseudonym = inverter(candidate)
            if pseudonym not in rainbow:
                rainbow[pseudonym] = candidate
                frequency_by_pseudonym[pseudonym] = frequency

        truth = self._truth(result, entity_type)
        by_frequency: dict[str, list[int]] = {}
        by_length: dict[str, list[int]] = {}

        recovered = 0
        for surface, count in observed.items():
            true_key = truth.get(surface)
            if true_key is None:
                continue
            true_name = true_key.split("\x1f", 1)[-1]
            guess = rainbow.get(surface)
            hit = int(guess is not None and guess.casefold() == true_name.casefold())
            recovered += hit
            band = _frequency_band(frequency_by_pseudonym.get(surface))
            by_frequency.setdefault(band, []).append(hit)
            by_length.setdefault(_length_band(true_name), []).append(hit)

        n = max(len(observed), 1)
        return AttackResult(
            attack=self.name,
            entity_type=entity_type,
            policy=policy,
            technique=technique_name,
            candidates=len(observed),
            recovered_top1=recovered,
            recovered_top5=recovered,
            accuracy_top1=recovered / n,
            accuracy_top5=recovered / n,
            by_frequency_band={k: sum(v) / len(v) for k, v in sorted(by_frequency.items())},
            notes=(
                f"dictionary of {len(self._candidates)} candidates; "
                f"length bands: "
                + ", ".join(f"{k}={sum(v) / len(v):.2f}" for k, v in sorted(by_length.items()))
            ),
        )

    @staticmethod
    def _observed(result: PseudonymisedCorpus, entity_type: str) -> Counter[str]:
        counts: Counter[str] = Counter()
        for pdoc in result.documents:
            for a in pdoc.assignments:
                if a.entity_type == entity_type:
                    counts[a.surface] += 1
        return counts

    @staticmethod
    def _truth(result: PseudonymisedCorpus, entity_type: str) -> dict[str, str]:
        keys: dict[str, set[str]] = {}
        for pdoc in result.documents:
            for a in pdoc.assignments:
                if a.entity_type == entity_type:
                    keys.setdefault(a.surface, set()).add(a.entity_key)
        return {s: next(iter(k)) for s, k in keys.items() if len(k) == 1}


def _frequency_band(frequency: float | None) -> str:
    """Bands chosen so the two ends are the interesting ones: in the dictionary, or absent from it."""
    if frequency is None:
        return "not in dictionary"
    if frequency >= 10_000:
        return "very common"
    if frequency >= 1_000:
        return "common"
    if frequency >= 100:
        return "uncommon"
    return "rare"


def candidates_from_inventory(
    names: Mapping[str, float] | Sequence[str],
) -> list[tuple[str, float]]:
    """Coerce a name list or frequency table into candidate pairs."""
    if isinstance(names, Mapping):
        return [(n, float(f)) for n, f in names.items()]
    return [(n, 1.0) for n in names]
