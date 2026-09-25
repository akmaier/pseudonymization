"""A2 — frequency analysis, as an adversary could actually mount it.

Under a deterministic policy every occurrence of an entity becomes the same pseudonym, so the
frequency distribution of the pseudonyms is the frequency distribution of the real entities, merely
relabelled.  Ranking both and aligning them recovers the mapping without touching the cryptography.
That is why H1 predicts hash, HMAC and AES-SIV leak comparably: **A2 is indifferent to the
technique.**

On optimal assignment: the attacker matches two one-dimensional sequences under a cost increasing in
the frequency difference, and for that problem the sorted (rank) alignment *is* the optimal
assignment, so a Hungarian solver returns the same answer at far greater cost.

## What changed on 2026-09-22, and why

AM: *"I am not happy about an unrealistic attack. What we want to report is real risks, not
theoretical bounds ... the collisions will happen in a real case, so neglecting them would require
ground truth, something an attacker does not have."*

The previous implementation was an upper bound wearing the clothes of a measurement. It took its
prior from the corpus under attack, counted mentions out of the defender's own assignment records,
and deleted from scoring every pseudonym that stood for more than one entity — the last of which
requires the mapping the attack is trying to recover.

There is **no published frequency attack on pseudonymised free text**, so every element below is
transferred from the structured-data literature and is labelled with the work it comes from:

* **Two priors over one observation.** Kuzu et al. (2013, ``10.1136/amiajnl-2012-000917``) reran
  their own idealised attack with a genuinely external prior and reported the collapse as the
  result; Niedermeyer et al. (2014, ``10.29012/jpc.v6i2.640``) assume only "a publicly available
  list of the most frequent attributes".  Vatsalan et al. (2014, ``10.29012/jpc.v6i1.636``) defend
  the oracle run as a worst case worth keeping.  So both run here, over the same observation, and
  the oracle is labelled a bound.
* **The attacker's own detector.** Carrell et al.'s parrot attack (2019, ``10.1093/jamia/ocz114``)
  has the adversary run its own tagger over the release rather than read the defender's annotations.
  :func:`observe` does the same, so a name the defender's detector *missed* is visible to the
  attacker — as it plainly is on the page — instead of being invisible.
* **Full denominator, named bins.** Vidanage et al. (2022, ``10.29012/jpc.764``) score six outcomes,
  four of which exist to account for ambiguity and failure; Dankar et al. (2012,
  ``10.1186/1472-6947-12-66``) reject the resolvable-only denominator by reductio.  Collisions are
  attempted and scored, never deleted, and Rocher et al. (2019, ``10.1038/s41467-019-10933-3``) give
  them fractional credit — three entities behind one surrogate is one chance in three.
* **Abstention without an oracle.** Narayanan and Shmatikov (``arXiv:cs/0610105``) abstain when
  ``(max - max2) / sigma < phi``, a signal computed entirely from the attacker's own scores, and
  note that a real adversary has no oracle telling it whether it succeeded.  Both numbers are
  reported side by side, as PAN requires: the abstention-blind rate over what was attempted, and
  ``c@1`` (Peñas and Rodrigo, 2011, ACL ``P11-1142``), which rewards declining to answer.
* **A chance baseline.** Carrell et al. (2013, ``10.1136/amiajnl-2012-001034``, eq. 3; 2019) report
  the precision expected by chance beside every rate.

## The prior-quality sweep

Bindschaedler et al. (2018, ``10.14778/3236187.3236217``) §7.3 degrade the adversary's auxiliary
data along **age** and **size** and report accuracy per cell.  :func:`degrade` does the same, which
turns "the attacker was unrealistic" into a measurement of how attack strength varies with how much
the adversary actually knows.  Both axes are real here rather than simulated: the German given-name
weights are held per birth decade and the Chinese lists per decade cohort, so *age* is a cohort
mismatch between the prior and the population, not a synthetic perturbation.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

from ..engine import PseudonymisedCorpus
from .base import AttackResult

__all__ = [
    "FrequencyAttack", "Prior", "A2Score", "spearman",
    "observe", "capitalised_spans", "degrade", "reference_from_counts",
]

_BANDS: tuple[tuple[str, int, int], ...] = (
    ("1", 1, 1),
    ("2-4", 2, 4),
    ("5-19", 5, 19),
    ("20+", 20, 1 << 30),
)

DEFAULT_ECCENTRICITY = 1.5
"""``phi`` in Narayanan and Shmatikov's rule, and their own experimental value.

An attacker declines when the best candidate does not stand out from the rest: with ``max`` the best
score, ``max2`` the runner-up and ``sigma`` the spread, it answers only if
``(max - max2) / sigma >= phi``.  Every quantity is one the attacker computes for itself, which is
the point — a rule that consulted the truth would be the oracle again in another costume.
"""


def _band(count: int) -> str:
    for label, low, high in _BANDS:
        if low <= count <= high:
            return label
    return _BANDS[-1][0]


# --------------------------------------------------------------------------- the attacker's view

_NAME_LIKE = re.compile(
    r"\b[A-ZÀ-Þ][a-zß-ÿ'’\-]{1,}(?:\s+[A-ZÀ-Þ][a-zß-ÿ'’\-]{1,}){0,2}"
)
"""Capitalised runs of one to three tokens — a crude tagger of the kind an adversary writes in an
afternoon.  Deliberately *not* one of the study's detectors: the attacker does not have the
defender's model, and a shared detector would make the attack's reach a function of the defence."""


def capitalised_spans(text: str) -> list[str]:
    """Name-like surfaces in one released document, found without any gold knowledge."""
    return [m.group(0) for m in _NAME_LIKE.finditer(text)]


def observe(
    result: PseudonymisedCorpus,
    finder: Callable[[str], Iterable[str]] = capitalised_spans,
) -> Counter[str]:
    """Count name-like surfaces **in the released text**.

    This is the one input the adversary genuinely has.  The previous implementation counted
    ``pdoc.assignments`` instead, which handed over three things the release does not print: that a
    substitution happened at all, a PERSON/LOC/ORG partition of the results, and the guarantee that
    every counted string is a surrogate.  Names the defender's detector missed were thereby
    invisible to the attack although they sit in the text in plain sight.
    """
    counts: Counter[str] = Counter()
    for pdoc in result.documents:
        for surface in finder(pdoc.text):
            counts[surface] += 1
    return counts


# --------------------------------------------------------------------------- the attacker's prior

@dataclass(frozen=True, slots=True)
class Prior:
    """What the adversary believes about how often each real name occurs."""

    label: str
    kind: str
    """``"oracle"`` or ``"external"`` — printed beside every number so the two are never conflated."""
    weights: Mapping[str, float]
    provenance: str
    """Where it came from, in words, for the experimental record."""
    vintage: str | None = None
    """The *age* axis of the Bindschaedler sweep: which cohort or edition this list describes."""

    @property
    def size(self) -> int:
        return len(self.weights)

    def ranked(self) -> list[str]:
        """Candidate names, commonest first. Ties broken on the name so the order is reproducible."""
        return [k for k, _ in sorted(self.weights.items(), key=lambda kv: (-kv[1], kv[0]))]

    def describe(self) -> dict[str, object]:
        return {"prior": self.label, "prior_kind": self.kind, "prior_size": self.size,
                "prior_vintage": self.vintage, "prior_provenance": self.provenance}

    @classmethod
    def corpus_internal(cls, result: PseudonymisedCorpus, entity_type: str) -> "Prior":
        """The upper bound: the attacker already knows this corpus's own name frequencies.

        Kept because Vatsalan et al. argue a scheme safe under it is safe in practice, and because
        the gap between it and an external prior measures how much the attack depends on knowledge
        the adversary probably does not have.  **It is not a risk estimate** and every consumer is
        told so by ``kind``.
        """
        counts: Counter[str] = Counter()
        for pdoc in result.documents:
            for a in pdoc.assignments:
                if a.entity_type == entity_type:
                    counts[a.entity_key] += 1
        return cls(label="corpus-internal", kind="oracle", weights=dict(counts),
                   provenance="entity frequencies of the corpus under attack — an upper bound, "
                              "not a realistic adversary (Kuzu 2013; Vatsalan 2014)")


    @classmethod
    def from_names(
        cls,
        pairs: Iterable[tuple[str, float]],
        entity_type: str,
        normaliser,
        *,
        label: str,
        provenance: str,
        vintage: str | None = None,
    ) -> "Prior":
        """An external list of real names, lifted into the key space the corpus uses.

        A census file says "SMITH, 2442977"; the corpus identifies entities by
        ``f"{type}\x1f{normalised surface}"``.  Without this the external prior would score zero
        against every corpus for a reason that has nothing to do with the adversary's knowledge —
        which is the sort of bug that reads as a finding.
        """
        from ..keys import entity_key

        merged: Counter[str] = Counter()
        for name, weight in pairs:
            if not name or not weight or float(weight) <= 0:
                continue
            merged[entity_key(str(name), entity_type, normaliser)] += float(weight)
        return cls(label=label, kind="external",
                   weights=reference_from_counts(merged.items()),
                   provenance=provenance, vintage=vintage)


def reference_from_counts(pairs: Iterable[tuple[str, float]]) -> dict[str, float]:
    """Normalise any (name, weight) list to relative frequencies summing to one."""
    items = [(k, float(v)) for k, v in pairs if v and float(v) > 0]
    total = sum(v for _, v in items)
    return {k: v / total for k, v in items} if total else {}


def degrade(prior: Prior, *, top: int | None = None, vintage: str | None = None) -> Prior:
    """One cell of the Bindschaedler prior-quality sweep.

    ``top`` truncates to the *n* commonest names — the size axis, and the realistic one: a public
    list gives an adversary the head of the distribution, never its tail.  ``vintage`` only
    relabels; selecting a cohort is the caller's job because the cohorts live in the source files.
    """
    weights = prior.weights
    if top is not None and top < len(weights):
        keep = prior.ranked()[:top]
        weights = reference_from_counts((k, prior.weights[k]) for k in keep)
    return Prior(
        label=prior.label + (f" top-{top:,}" if top is not None else ""),
        kind=prior.kind, weights=weights,
        provenance=prior.provenance + (f"; truncated to the {top:,} commonest" if top else ""),
        vintage=vintage if vintage is not None else prior.vintage,
    )


# --------------------------------------------------------------------------- scoring

@dataclass(frozen=True, slots=True)
class A2Score:
    """One alignment, scored over the full denominator in named bins.

    The bins are Vidanage et al.'s, minus the two that a rank alignment cannot produce: it emits at
    most one guess per observed surface, so ``correct_many_to_1`` and ``correct_many_to_many`` are
    structurally zero here and are recorded as such rather than silently omitted.
    """

    observed: int
    """Every name-like surface the attacker found — the denominator (Dankar et al. 2012)."""
    attempted: int
    abstained: int
    correct_1_to_1: int
    correct_1_to_many: int
    correct_many_to_1: int = 0
    correct_many_to_many: int = 0
    wrong: int = 0
    expected_correct: float = 0.0
    """Rocher's fractional credit: a guess against *k* entities behind one surrogate scores 1/k."""
    mean_candidate_set: float = 0.0
    """Christen et al. report this beside every hit rate; a hit among 90 candidates is not a hit
    among 10."""
    chance: float = 0.0
    eccentricity: float = DEFAULT_ECCENTRICITY
    by_band: Mapping[str, float] = field(default_factory=dict)
    prior: Mapping[str, object] = field(default_factory=dict)
    undetected_recovered: int = 0
    """Surfaces the defender's detector missed, which the attacker reads as the real name. These are
    genuine re-identifications and the previous implementation could not see them at all."""

    @property
    def correct(self) -> int:
        return self.correct_1_to_1 + self.correct_1_to_many

    @property
    def accuracy_attempted(self) -> float:
        """The abstention-**blind** rate: correct over what the attacker chose to answer.

        Reported alongside ``c_at_1`` and never alone — on its own it rewards an attacker that
        answers one easy case and declines everything else (Peñas and Rodrigo 2011, §3.4)."""
        return self.correct / self.attempted if self.attempted else 0.0

    @property
    def correct_by_alignment(self) -> int:
        """Recoveries the *frequency attack* made, excluding names it simply read.

        These two must never be added together and quoted as one rate. A mention the detector
        missed is printed in the release as the real name, so the attacker recovers it without
        aligning anything; counting that as attack success measures the defender's recall, not the
        adversary's. Measured on CARDIO:DE on 2026-09-22, **every** apparent success was of the
        second kind and the alignment recovered nothing — which a combined rate would have
        reported as a lift of 110x over chance."""
        return max(0, self.correct - self.undetected_recovered)

    @property
    def accuracy_alignment(self) -> float:
        """The rate the lift is computed on: alignment successes over alignment attempts."""
        attempts = self.attempted - self.undetected_recovered
        return self.correct_by_alignment / attempts if attempts > 0 else 0.0

    @property
    def c_at_1(self) -> float:
        """The abstention-**rewarding** rate, over the full denominator.

        ``c@1 = (1/n)(n_ac + (n_ac/n) * n_u)`` — an abstention is credited at the rate the attacker
        achieves where it does answer, so declining is neither free nor punished as a wrong answer.
        """
        n = self.observed
        if not n:
            return 0.0
        return (self.correct + (self.correct / n) * self.abstained) / n

    @property
    def lift_over_chance(self) -> float:
        """Lift of the **alignment** over chance — never of the read-the-missed-name effect.

        Chance is ``1/|candidates|``: the rate a random alignment achieves. Reading a name the
        defender left in the clear has nothing to do with that baseline, so it is excluded from the
        numerator (Carrell et al. report the chance rate beside the measured one precisely so the
        two cannot be confused)."""
        return (self.accuracy_alignment / self.chance) if self.chance else 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "observed": self.observed, "attempted": self.attempted, "abstained": self.abstained,
            "correct_1_to_1": self.correct_1_to_1,
            "correct_1_to_many": self.correct_1_to_many,
            "correct_many_to_1": self.correct_many_to_1,
            "correct_many_to_many": self.correct_many_to_many,
            "wrong": self.wrong,
            "correct": self.correct,
            "expected_correct": self.expected_correct,
            "accuracy_attempted": self.accuracy_attempted,
            "correct_by_alignment": self.correct_by_alignment,
            "accuracy_alignment": self.accuracy_alignment,
            "c_at_1": self.c_at_1,
            "chance": self.chance,
            "lift_over_chance": self.lift_over_chance,
            "mean_candidate_set": self.mean_candidate_set,
            "eccentricity": self.eccentricity,
            "undetected_recovered": self.undetected_recovered,
            "by_band": dict(self.by_band),
            **dict(self.prior),
        }


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman's rho, with average ranks for ties. ``None`` when it is undefined."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


# --------------------------------------------------------------------------- the attack

def _truth_tables(
    result: PseudonymisedCorpus, entity_type: str
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Evaluator-side only: what actually stands behind each surface.

    Two tables, and the distinction between them is the point.  ``surrogates`` maps a replacement
    string to every entity that was given it — a set with more than one member is a **collision**,
    which the attacker cannot see and which is therefore scored rather than deleted.  ``real_names``
    maps an original surface to its entity, so that a mention the defender's detector **missed**
    is recognised for what it is: a name sitting in the release, which the attacker recovers by
    reading it.
    """
    surrogates: dict[str, set[str]] = {}
    real_names: dict[str, set[str]] = {}
    for pdoc in result.documents:
        for a in pdoc.assignments:
            if a.entity_type == entity_type:
                surrogates.setdefault(a.surface, set()).add(a.entity_key)
        for mention in pdoc.document.mentions:
            if mention.type == entity_type and mention.gold_entity_id:
                real_names.setdefault(mention.surface, set()).add(mention.gold_entity_id)
    # A surface that is both a surrogate and a real name is a surrogate here: the replacement is
    # what the reader of the release actually encounters at that position.
    for surface in surrogates:
        real_names.pop(surface, None)
    return surrogates, real_names


def _alignment_scores(count: int, expected: Sequence[float], sample: Sequence[float]):
    """Best and runner-up candidate scores for one observed count, and the spread.

    The score is ``-|log((count+1)/(expected+1))|``: an attacker prefers the candidate whose
    population frequency implies the count it actually sees, and works in log space so that the
    comparison is not dominated by the head of the distribution.  ``expected`` is sorted, so the best
    two are found by binary search rather than by scanning every candidate — the exhaustive version
    is quadratic and does not finish on Enron.  ``sigma`` is estimated from a fixed stride sample,
    which keeps Narayanan and Shmatikov's rule computable at this scale.
    """
    import bisect

    target = math.log(count + 1)
    position = bisect.bisect_left(expected, count)
    near = []
    for index in range(max(0, position - 2), min(len(expected), position + 3)):
        near.append((-abs(target - math.log(expected[index] + 1)), index))
    if not near:
        return None, None, None, 0
    near.sort(reverse=True)
    best = near[0][0]
    runner_up = near[1][0] if len(near) > 1 else best
    scores = [-abs(target - math.log(e + 1)) for e in sample]
    mean = sum(scores) / len(scores)
    sigma = (sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5
    return best, runner_up, sigma, near[0][1]


class FrequencyAttack:
    """Rank name-like surfaces by frequency, rank candidate names by frequency, align.

    ``prior`` decides which adversary this is, and the two are meant to be run over the same
    observation and reported together (Kuzu et al. 2013):

    * :meth:`Prior.corpus_internal` — the attacker already knows this corpus's own distribution.
      An upper bound.  Labelled ``kind="oracle"`` in every output row.
    * an external list — census surnames, a register of given names by birth decade.  The realistic
      setting, and weaker, because population frequency is not corpus frequency.
    """

    name = "a2_frequency"
    requires_unkeyed = False

    def __init__(
        self,
        prior: Prior | None = None,
        *,
        eccentricity: float = DEFAULT_ECCENTRICITY,
        finder: Callable[[str], Iterable[str]] = capitalised_spans,
        sigma_sample: int = 2_000,
    ) -> None:
        self._prior = prior
        self._eccentricity = eccentricity
        self._finder = finder
        self._sigma_sample = sigma_sample

    def score(
        self,
        result: PseudonymisedCorpus,
        entity_type: str,
        observed: Counter[str] | None = None,
        tables: tuple[dict[str, set[str]], dict[str, set[str]]] | None = None,
    ) -> A2Score:
        """Mount the attack and score it over every surface the attacker found.

        ``observed`` and ``tables`` let a caller compute the adversary's view of the release **once**
        and reuse it across every prior and every abstention threshold. That is not only an
        optimisation: "two priors over one observation" is the design, and recomputing the
        observation per cell would let it drift between cells that are meant to differ in exactly
        one respect. It also matters at Enron's scale, where tagging 58,636 documents twenty-five
        times per span source is most of the run.
        """
        if observed is None:
            observed = observe(result, self._finder)
        prior = self._prior or Prior.corpus_internal(result, entity_type)
        surrogates, real_names = tables if tables is not None else _truth_tables(result, entity_type)

        weights = prior.weights
        if not observed or not weights:
            return A2Score(observed=len(observed), attempted=0, abstained=len(observed),
                           correct_1_to_1=0, correct_1_to_many=0,
                           eccentricity=self._eccentricity, prior=prior.describe())

        total_mentions = sum(observed.values())
        candidates = prior.ranked()
        # Expected count for each candidate under the prior, ascending — the axis the alignment
        # searches.  Built once; the scoring loop only binary-searches it.
        pairs = sorted(((weights[c] * total_mentions, c) for c in candidates), key=lambda kv: kv[0])
        expected = [e for e, _ in pairs]
        names = [c for _, c in pairs]
        stride = max(1, len(expected) // self._sigma_sample)
        sample = expected[::stride]

        attempted = abstained = c11 = c1m = wrong = undetected = 0
        fractional = 0.0
        per_band: dict[str, list[int]] = {}
        chance = 1.0 / len(candidates)

        # The alignment depends on the observed *count*, never on which string carried it, and
        # counts repeat heavily — most surfaces occur once or twice. Memoising by count turns a
        # per-surface sigma estimate over a 2,000-element sample into a few hundred of them, which
        # is the difference between 19 span sources an hour and the rate this had before the
        # rewrite. The results are identical; only the work is not repeated.
        alignment: dict[int, tuple] = {}
        for surface, count in observed.most_common():
            if count not in alignment:
                alignment[count] = _alignment_scores(count, expected, sample)
            best, runner_up, sigma, index = alignment[count]
            if best is None:
                abstained += 1
                continue
            # Narayanan and Shmatikov's rule, computed entirely from the attacker's own scores.
            eccentricity = (best - runner_up) / sigma if sigma else 0.0
            if eccentricity < self._eccentricity:
                abstained += 1
                continue
            attempted += 1
            guess = names[index]
            behind = surrogates.get(surface)
            if behind is None:
                if surface in real_names:
                    # The defender's detector missed this mention, so the release prints the name.
                    # The attacker recovers it by reading, not by aligning — which is exactly the
                    # leakage the old implementation could not see, because it counted only what
                    # the detector had caught.
                    undetected += 1
                    c11 += 1
                    fractional += 1.0
                    per_band.setdefault(_band(count), []).append(1)
                else:
                    # The attacker's own tagger fired on something that is not an entity of this
                    # type. A real adversary pays for its own false positives.
                    wrong += 1
                    per_band.setdefault(_band(count), []).append(0)
                continue
            hit = guess in behind
            if hit and len(behind) == 1:
                c11 += 1
                fractional += 1.0
            elif hit:
                # A collision: several entities wear this surrogate and the attacker cannot tell.
                # Vidanage's "correct 1-to-many"; Rocher's fractional credit of 1/k.
                c1m += 1
                fractional += 1.0 / len(behind)
            else:
                wrong += 1
            per_band.setdefault(_band(count), []).append(int(hit))

        return A2Score(
            observed=len(observed), attempted=attempted, abstained=abstained,
            correct_1_to_1=c11, correct_1_to_many=c1m, wrong=wrong,
            expected_correct=fractional,
            mean_candidate_set=float(len(candidates)),
            chance=chance, eccentricity=self._eccentricity,
            by_band={k: sum(v) / len(v) for k, v in sorted(per_band.items())},
            prior=prior.describe(), undetected_recovered=undetected,
        )

    def run(
        self,
        result: PseudonymisedCorpus,
        entity_type: str,
        policy: str,
        technique: str,
    ) -> AttackResult:
        """The :class:`AttackResult` shape the sweep already consumes, from :meth:`score`."""
        scored = self.score(result, entity_type)
        observed_counts = observe(result, self._finder)
        surrogates, _ = _truth_tables(result, entity_type)
        # True mentions per entity, evaluator-side. `rho` asks how faithfully the released text
        # preserves the frequency ordering of the entities underneath it.
        true_counts: Counter[str] = Counter()
        for pdoc in result.documents:
            for a in pdoc.assignments:
                if a.entity_type == entity_type:
                    true_counts[a.entity_key] += 1
        xs, ys = [], []
        for surface, count in observed_counts.most_common():
            behind = surrogates.get(surface)
            if behind:
                # Collisions stay in, and their true frequency is the sum over the entities sharing
                # the surrogate — which is exactly the inflated quantity the attacker cannot
                # decompose. Dropping them would need the mapping (AM, 2026-09-22).
                xs.append(count)
                ys.append(sum(true_counts.get(k, 0) for k in behind))
        # `accuracy_top5` carries c@1 rather than a top-5 rate: this attack emits one guess per
        # surface, so there is no five-deep list, and the second slot is better spent on the
        # abstention-rewarding number the PAN convention requires beside the blind one. The note
        # says so, and `score()` returns the full set of bins for any consumer that wants them.
        return AttackResult(
            self.name, entity_type, policy, technique,
            candidates=scored.observed,
            recovered_top1=scored.correct,
            recovered_top5=scored.correct,
            accuracy_top1=scored.accuracy_attempted,
            accuracy_top5=scored.c_at_1,
            rank_correlation=spearman(xs, ys),
            by_frequency_band=dict(scored.by_band),
            notes=f"accuracy_top5 is c@1, not a top-5 rate; {prior_note(scored)}",
        )


def prior_note(scored: A2Score) -> str:
    kind = scored.prior.get("prior_kind")
    label = scored.prior.get("prior", "?")
    warning = " — UPPER BOUND, not a risk estimate" if kind == "oracle" else ""
    return (f"prior: {label} ({kind}, {scored.prior.get('prior_size')} names){warning}; "
            f"abstained on {scored.abstained}/{scored.observed} at eccentricity "
            f"{scored.eccentricity}")
