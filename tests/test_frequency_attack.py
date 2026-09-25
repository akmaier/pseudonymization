"""A2 is where H1 lives, so these tests assert the hypothesis's mechanics, not just execution.

Rewritten 2026-09-22 when the attack stopped being an upper bound (AM: *"what we want to report is
real risks, not theoretical bounds"*).  The old suite asserted ``accuracy_top1 == 1.0`` under a
deterministic policy, which was true only because the attacker's prior was the corpus's own entity
frequencies and its observation was the defender's own assignment records — the same list sorted two
ways.  What is asserted now is that the attack behaves like an adversary: it reads the released text,
it pays for collisions instead of deleting them, it declines when it cannot tell, and it does better
with better background knowledge.
"""

import pytest

from pseudonymkit.attacks import spearman
from pseudonymkit.attacks.frequency import (
    A2Score, FrequencyAttack, Prior, capitalised_spans, degrade, observe,
)
from pseudonymkit.domain import Corpus, Document, Mention, Span
from pseudonymkit.engine import Pseudonymiser
from pseudonymkit.inventories import SyntheticInventory
from pseudonymkit.keys import NORMALISERS
from pseudonymkit.policies import POLICIES
from pseudonymkit.surrogates import SURROGATES
from pseudonymkit.techniques import TECHNIQUES

PLAN = [("Weber", 20), ("Meyer", 8), ("Schulz", 3), ("Kraus", 2), ("Vogt", 1)]


def zipfian_corpus(annotate: bool = True) -> Corpus:
    """One document per mention, with a steep name-frequency distribution.

    Skew is the point: frequency analysis works precisely because real names are not uniform.
    ``annotate=False`` leaves the mentions unmarked, which models a detector that missed them.
    """
    docs = []
    n = 0
    for name, times in PLAN:
        for _ in range(times):
            text = f"{name} testified."
            mentions = (
                (Mention(f"d{n}", "m0", Span(0, len(name), name, "PERSON"), gold_entity_id=name),)
                if annotate else ()
            )
            docs.append(Document(f"d{n}", text, "en", mentions))
            n += 1
    return Corpus("zipf", tuple(docs))


def run(policy: str, technique: str, annotate: bool = True) -> object:
    engine = Pseudonymiser(
        NORMALISERS.create("N2"),
        POLICIES.create(policy),
        TECHNIQUES.create(technique),
        SURROGATES.create("realistic", inventory=SyntheticInventory()),
    )
    return engine.pseudonymise_corpus(zipfian_corpus(annotate))


def oracle(result) -> A2Score:
    return FrequencyAttack(Prior.corpus_internal(result, "PERSON")).score(result, "PERSON")


# --------------------------------------------------------------------- the adversary's view


def test_the_observation_comes_from_the_released_text_not_the_assignments():
    """The attacker counts strings on the page; it never sees `pdoc.assignments`."""
    result = run("deterministic", "hmac")
    counted = observe(result)
    surrogates = {a.surface for pdoc in result.documents for a in pdoc.assignments}
    assert counted, "the attacker's tagger found nothing"
    # Every surrogate that is capitalised is visible to the attacker, and the counts are read off
    # the text rather than copied from the mapping.
    assert any(s in counted for s in surrogates)
    total_in_text = sum(pdoc.text.count(s) for pdoc in result.documents for s in surrogates)
    assert sum(counted[s] for s in surrogates if s in counted) <= total_in_text


def test_a_missed_mention_is_recovered_by_reading_it():
    """A name the detector missed sits in the release in plain sight.

    The previous implementation counted only what the detector caught, so these were invisible to
    the attack — the one direction of error that *under*-states risk.
    """
    missed = run("deterministic", "hmac", annotate=False)
    counted = observe(missed)
    assert counted["Weber"] == 20, "the unreplaced name should be readable in the release"


# --------------------------------------------------------------------- collisions are paid for


def test_collisions_are_attempted_and_never_dropped():
    """Neglecting a collision would need the mapping, which an attacker does not have.

    Scoring must therefore contain every surface the attacker found, whether or not the surrogate
    behind it is unique.
    """
    result = run("deterministic", "hmac")
    scored = oracle(result)
    assert scored.observed == scored.attempted + scored.abstained
    assert scored.attempted == (scored.correct_1_to_1 + scored.correct_1_to_many
                                + scored.correct_many_to_1 + scored.correct_many_to_many
                                + scored.wrong)


def test_a_colliding_surrogate_scores_fractionally_not_fully():
    """Rocher's rule: k entities behind one surrogate is one chance in k."""
    scored = A2Score(observed=2, attempted=2, abstained=0,
                     correct_1_to_1=1, correct_1_to_many=1, expected_correct=1.0 + 1.0 / 3.0)
    assert scored.correct == 2
    assert scored.expected_correct == pytest.approx(1.3333, abs=1e-4)
    assert scored.expected_correct < scored.correct


# --------------------------------------------------------------------- abstention


def test_c_at_1_is_bounded_by_the_blind_rate_and_rewards_declining():
    """Both numbers are reported; neither may be quoted alone (PAN convention).

    ``c@1`` credits an abstention at the rate achieved where the attacker did answer, so it can
    never exceed the abstention-blind rate and never falls below raw accuracy over everything.
    """
    scored = A2Score(observed=100, attempted=40, abstained=60,
                     correct_1_to_1=20, correct_1_to_many=0)
    raw = scored.correct / scored.observed
    assert raw <= scored.c_at_1 <= scored.accuracy_attempted
    assert scored.accuracy_attempted == pytest.approx(0.5)


def test_declining_everything_does_not_score_well():
    """The failure c@1 exists to prevent: answer one sure case, decline the rest."""
    cheat = A2Score(observed=100, attempted=1, abstained=99, correct_1_to_1=1, correct_1_to_many=0)
    assert cheat.accuracy_attempted == 1.0
    assert cheat.c_at_1 < 0.05


def test_abstention_is_decided_without_ground_truth():
    """Raising phi makes the attacker more cautious; nothing about the truth enters the rule."""
    result = run("deterministic", "hmac")
    prior = Prior.corpus_internal(result, "PERSON")
    cautious = FrequencyAttack(prior, eccentricity=1e9).score(result, "PERSON")
    assert cautious.attempted == 0 and cautious.abstained == cautious.observed
    assert cautious.c_at_1 == 0.0


# --------------------------------------------------------------------- priors


def test_the_oracle_prior_is_labelled_a_bound_in_every_row():
    result = run("deterministic", "hmac")
    scored = oracle(result)
    assert scored.prior["prior_kind"] == "oracle"
    assert "upper bound" in scored.prior["prior_provenance"]


def test_an_external_prior_that_disagrees_recovers_less_than_the_oracle():
    """Kuzu et al.'s finding, as a test: a realistic prior is weaker, and that is the result."""
    result = run("deterministic", "hmac")
    internal = oracle(result)
    external = FrequencyAttack(
        Prior.from_names(
            [("Vogt", 99.0), ("Kraus", 50.0), ("Weber", 1.0)],
            "PERSON", NORMALISERS.create("N2"),
            label="inverted gazetteer", provenance="a list whose ordering disagrees with the corpus",
        )
    ).score(result, "PERSON")
    assert external.prior["prior_kind"] == "external"
    assert external.expected_correct <= internal.expected_correct


def test_degrade_truncates_the_prior_and_says_so():
    """One cell of the Bindschaedler sweep: the size axis."""
    full = Prior.from_names([(n, c) for n, c in PLAN], "PERSON", NORMALISERS.create("N2"),
                            label="full", provenance="test")
    small = degrade(full, top=2)
    assert small.size == 2 and full.size == len(PLAN)
    assert "top-2" in small.label
    assert sum(small.weights.values()) == pytest.approx(1.0)
    # The head of the distribution survives truncation; that is what a public list gives you.
    assert small.ranked()[0] == full.ranked()[0]


def test_degrade_records_the_vintage_for_the_age_axis():
    full = Prior.from_names([(n, c) for n, c in PLAN], "PERSON", NORMALISERS.create("N2"),
                            label="register", provenance="test", vintage="1930-1969")
    older = degrade(full, vintage="1990-1999")
    assert older.vintage == "1990-1999" and full.vintage == "1930-1969"


# --------------------------------------------------------------------- H1 and the chance baseline


def test_all_techniques_give_the_same_leakage():
    """H1 stated as an equality across the axis practitioners agonise over."""
    scores = {
        t: oracle(run("deterministic", t)).expected_correct for t in TECHNIQUES.names()
    }
    assert len(set(scores.values())) == 1


def test_randomising_every_mention_weakens_the_attack():
    """Every mention gets its own pseudonym, so every frequency is 1 and ranking is meaningless."""
    deterministic = oracle(run("deterministic", "hmac"))
    full = oracle(run("full", "hmac"))
    assert full.expected_correct <= deterministic.expected_correct


def test_a_chance_baseline_is_reported_beside_every_rate():
    """Carrell et al. report the rate expected by chance next to the measured one."""
    scored = oracle(run("deterministic", "hmac"))
    assert 0.0 < scored.chance <= 1.0
    assert scored.mean_candidate_set >= 1
    if scored.attempted:
        assert scored.lift_over_chance == pytest.approx(
            scored.accuracy_attempted / scored.chance)


def test_attacking_a_type_with_no_entities_is_scored_not_crashed():
    """The attacker does not know entity types: its tagger still fires, and it is still wrong.

    Reporting zero candidates here would be the old behaviour, which quietly told the attacker
    which surfaces were LOC.
    """
    result = run("deterministic", "hmac")
    scored = FrequencyAttack(Prior.corpus_internal(result, "PERSON")).score(result, "LOC")
    assert scored.correct == 0


def test_spearman_edge_cases():
    assert spearman([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert spearman([1], [1]) is None
    assert spearman([1, 1, 1], [1, 2, 3]) is None


def test_capitalised_spans_finds_names_without_gold():
    text = "Weber testified. Later Anna Meyer and Herr Schulz arrived."
    found = capitalised_spans(text)
    assert "Weber" in found
    assert any("Meyer" in f for f in found)
