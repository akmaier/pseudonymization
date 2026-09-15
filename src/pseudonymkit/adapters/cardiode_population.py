"""Who the people in CARDIO:DE are, across the whole corpus rather than one letter at a time.

``experiment_plan.md`` §12.1, rewritten 2026-09-15.  The fill used to mint a fresh person for every
uncued run, which produced a corpus in which **nobody appears twice** — 2,038 person entities over
400 letters, none recurring.  That is not how a cardiology department's correspondence looks, and it
silently removed every measurement that needs cross-document identity: drift (§8.2), A3 and A5
(§8.4), and the (name, date-of-birth) pair setting.

Three properties are constructed here instead, and each is a **recorded parameter** rather than a
hidden constant, in the same way §13 records a sampling rate:

``physicians`` / ``physician_turnover``
    A department's letters are signed by a bounded set of consultants, each signing many letters,
    with slow turnover as staff arrive and leave.

``patient_return_rate``
    Cardiology is a follow-up speciality, so a share of the corpus is repeat correspondence about the
    same person, and a returning patient's letters are separated in the sequence rather than
    adjacent — a follow-up arrives later, not next.

The identity remains **ours by construction**.  What changes is that it is now a realistic
construction rather than a maximal one, and every result on this corpus says so.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Mapping, Sequence

__all__ = ["PopulationSpec", "Population", "WeightedNames"]


@dataclass(frozen=True, slots=True)
class PopulationSpec:
    """The parameters of the construction.  Recorded with the build, never inferred afterwards."""

    physicians: int = 30
    """Consultants in the department at any one time.

    400 letters carry 1,571 signature runs — about 3.9 signatories each — so the alternative the fill
    used, one person per run, implies 1,571 physicians in a single department.  A German university
    cardiology department is on the order of tens, and 30 keeps the mean signing load near 52 letters
    per consultant over the corpus, which is what a department's correspondence looks like."""

    physician_turnover: float = 0.25
    """Fraction of the roster replaced across the corpus's span.

    Slow: staff arrive and leave, but the department is recognisably the same one from the first
    letter to the last.  Modelled as a window sliding over a slightly larger roster, so a consultant
    who leaves stops appearing and never returns."""

    patient_return_rate: float = 0.30
    """Probability that a letter continues an earlier patient's case rather than opening a new one.

    Gives roughly 0.3 of letters as follow-ups, so about 280 distinct patients over 400 letters with
    a tail of two- and three-letter cases — the shape of a follow-up speciality's correspondence."""

    follow_up_gap: int = 5
    """Minimum letters between a patient's appearances.  A follow-up arrives later, not next."""

    seed: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "physicians": self.physicians,
            "physician_turnover": self.physician_turnover,
            "patient_return_rate": self.patient_return_rate,
            "follow_up_gap": self.follow_up_gap,
            "seed": self.seed,
        }


class WeightedNames:
    """A name pool drawn in proportion to frequency, or uniformly when no weights exist.

    §12.1 requires the draw to reproduce German naming frequencies so that A2 has a signal to align
    and H4's frequency-preservation question is answerable.  The CodEAlltag lists carry no counts, so
    the weights come from elsewhere; **which source supplied them is recorded**, and ``"uniform"``
    is a legitimate recorded value that says plainly no weighting was applied.

    A name the weight source does not cover keeps a small floor weight rather than being dropped:
    the fill must not fail on a name the frequency table has never heard of, and a long tail of rare
    names is itself part of a realistic distribution.
    """

    FLOOR = 1.0

    def __init__(
        self,
        names: Sequence[str],
        weights: Mapping[str, float] | None = None,
        source: str = "uniform",
    ) -> None:
        if not names:
            raise ValueError("name pool is empty")
        self.names = tuple(names)
        self.source = source
        if weights:
            self.weights = tuple(float(weights.get(n, self.FLOOR)) for n in self.names)
            self.covered = sum(1 for n in self.names if n in weights)
        else:
            self.weights = tuple(self.FLOOR for _ in self.names)
            self.covered = 0
        self._cumulative: list[float] = []
        total = 0.0
        for weight in self.weights:
            total += weight
            self._cumulative.append(total)
        self._total = total

    def draw(self, rng: random.Random) -> str:
        import bisect

        return self.names[
            min(bisect.bisect_right(self._cumulative, rng.random() * self._total),
                len(self.names) - 1)
        ]

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "names": len(self.names),
            "covered_by_weights": self.covered,
            "coverage": self.covered / len(self.names) if self.names else 0.0,
        }


@dataclass(frozen=True, slots=True)
class _Slot:
    """One constructed person, stable across every letter they appear in."""

    entity_id: str
    given: str
    second: str
    family: str
    female: bool


class Population:
    """The department and its patients, decided once for the whole corpus.

    Built from the **ordered** document ids, because both properties are sequential: a consultant is
    active over a stretch of the correspondence, and a follow-up letter comes after the letter it
    follows.  Order is the corpus's own — the caller passes the documents in the order it fills them.

    ``female_patient`` carries each letter's own gender cue — CARDIO:DE's German morphology survives
    de-identification, so the text says whether the patient is *der Patient* or *die Patientin*.  A
    letter is only matched to a returning patient whose gender agrees; otherwise the follow-up would
    contradict the text it is written into, and the corpus would assert that one person is both.
    """

    def __init__(
        self,
        doc_ids: Sequence[str],
        family: WeightedNames,
        male: WeightedNames,
        female: WeightedNames,
        spec: PopulationSpec = PopulationSpec(),
        female_patient: Mapping[str, bool] | None = None,
    ) -> None:
        self.spec = spec
        self.doc_ids = tuple(doc_ids)
        self._family, self._male, self._female = family, male, female
        rng = random.Random(f"population:{spec.seed}")

        # --- the department -----------------------------------------------------------------
        replacements = round(spec.physicians * spec.physician_turnover)
        roster_size = spec.physicians + replacements
        self.roster = [
            self._person(f"physician:{index}", rng) for index in range(roster_size)
        ]
        self._replacements = replacements

        # --- the patients -------------------------------------------------------------------
        # One pass, and the eligibility test is O(1): `last_seen` holds each patient's most recent
        # position, so a follow-up is a lookup rather than a scan back through the corpus.
        self._position = {doc_id: index for index, doc_id in enumerate(self.doc_ids)}
        self._wanted = dict(female_patient or {})
        self._registry: dict[str, _Slot] = {}
        self.patient_of: dict[str, _Slot] = {}
        self.letters_of: dict[str, list[str]] = {}
        last_seen: dict[str, int] = {}
        eligible: list[str] = []      # patients whose gap has elapsed; append-only, popped by index
        pending: list[tuple[int, str]] = []
        made = 0
        for position, doc_id in enumerate(self.doc_ids):
            while pending and pending[0][0] <= position:
                eligible.append(pending.pop(0)[1])
            wanted = (female_patient or {}).get(doc_id)
            matching = [
                index for index, pid in enumerate(eligible)
                if wanted is None or self._registry[pid].female == wanted
            ]
            if matching and rng.random() < spec.patient_return_rate:
                patient_id = eligible.pop(rng.choice(matching))
            else:
                patient_id = f"patient:{made}"
                made += 1
                self._registry[patient_id] = self._person(patient_id, rng, female=wanted)
            self.patient_of[doc_id] = self._registry[patient_id]
            self.letters_of.setdefault(patient_id, []).append(doc_id)
            last_seen[patient_id] = position
            pending.append((position + spec.follow_up_gap, patient_id))
            pending.sort()

    def _person(self, entity_id: str, rng: random.Random, female: bool | None = None) -> _Slot:
        if female is None:
            female = rng.random() < 0.5
        pool = self._female if female else self._male
        return _Slot(
            entity_id=entity_id,
            given=pool.draw(rng),
            second=pool.draw(rng),
            family=self._family.draw(rng),
            female=female,
        )

    # ------------------------------------------------------------------ lookups used by the fill

    def active_physicians(self, doc_id: str) -> list[_Slot]:
        """The consultants in post when this letter was written.

        A window of ``spec.physicians`` sliding over the roster as the correspondence proceeds, so
        early letters are signed by the early roster and late ones by the late roster, with a long
        overlap in between.
        """
        if self._replacements == 0:
            return self.roster
        position = self._position.get(doc_id, 0)
        fraction = position / max(len(self.doc_ids) - 1, 1)
        start = round(fraction * self._replacements)
        return self.roster[start : start + self.spec.physicians]

    def physician(self, doc_id: str, slot: int) -> _Slot:
        """The ``slot``-th distinct signatory of this letter, drawn from those in post."""
        active = self.active_physicians(doc_id)
        rng = random.Random(f"sign:{self.spec.seed}:{doc_id}:{slot}")
        return active[rng.randrange(len(active))]

    def patient(self, doc_id: str) -> _Slot:
        """The patient this letter is about — shared with the letter's other appearances."""
        return self.patient_of[doc_id]

    def report(self) -> dict[str, object]:
        """What the construction produced.  Goes into the build manifest."""
        counts = [len(v) for v in self.letters_of.values()]
        mismatch = sum(
            1 for doc_id, person in self.patient_of.items()
            if self._wanted.get(doc_id) is not None and self._wanted[doc_id] != person.female
        )
        return {
            "gender_cue_conflicts": mismatch,
            "spec": self.spec.as_dict(),
            "letters": len(self.doc_ids),
            "patients": len(self.letters_of),
            "patients_with_more_than_one_letter": sum(1 for c in counts if c > 1),
            "max_letters_per_patient": max(counts) if counts else 0,
            "physician_roster": len(self.roster),
            "physicians_in_post": self.spec.physicians,
            "family_names": self._family.as_dict(),
            "given_names_male": self._male.as_dict(),
            "given_names_female": self._female.as_dict(),
        }
