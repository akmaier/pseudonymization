"""A2 is where H1 lives, so these tests assert the hypothesis's mechanics, not just execution."""

import pytest

from pseudonymkit.attacks import FrequencyAttack, spearman
from pseudonymkit.domain import Corpus, Document, Mention, Span
from pseudonymkit.engine import Pseudonymiser
from pseudonymkit.inventories import SyntheticInventory
from pseudonymkit.keys import NORMALISERS
from pseudonymkit.policies import POLICIES
from pseudonymkit.surrogates import SURROGATES
from pseudonymkit.techniques import TECHNIQUES


def zipfian_corpus() -> Corpus:
    """One document per mention, with a steep name-frequency distribution.

    Skew is the point: frequency analysis works precisely because real names are not uniform.
    """
    plan = [("Weber", 20), ("Meyer", 8), ("Schulz", 3), ("Kraus", 2), ("Vogt", 1)]
    docs = []
    n = 0
    for name, times in plan:
        for _ in range(times):
            text = f"{name} testified."
            docs.append(
                Document(
                    f"d{n}", text, "en",
                    (Mention(f"d{n}", "m0", Span(0, len(name), name, "PERSON"),
                             gold_entity_id=name),),
                )
            )
            n += 1
    return Corpus("zipf", tuple(docs))


def run(policy: str, technique: str) -> object:
    engine = Pseudonymiser(
        NORMALISERS.create("N2"),
        POLICIES.create(policy),
        TECHNIQUES.create(technique),
        SURROGATES.create("realistic", inventory=SyntheticInventory()),
    )
    return engine.pseudonymise_corpus(zipfian_corpus())


@pytest.mark.parametrize("technique", TECHNIQUES.names())
def test_deterministic_policy_leaks_completely_whatever_the_technique(technique):
    """H1: under a deterministic policy A2 succeeds regardless of technique.

    Pseudonym frequency mirrors real frequency exactly, so rank alignment recovers everything and
    the cryptography is irrelevant.  hash and hmac leak identically.
    """
    result = FrequencyAttack().run(run("deterministic", technique), "PERSON", "deterministic", technique)
    assert result.rank_correlation == pytest.approx(1.0)
    assert result.accuracy_top1 == 1.0


def test_all_techniques_give_the_same_leakage():
    """The claim stated as an equality across the axis practitioners agonise over."""
    scores = {
        t: FrequencyAttack().run(run("deterministic", t), "PERSON", "deterministic", t).accuracy_top1
        for t in TECHNIQUES.names()
    }
    assert len(set(scores.values())) == 1


def test_full_randomisation_destroys_the_signal():
    """Every mention gets its own pseudonym, so every frequency is 1 and ranking is meaningless."""
    result = FrequencyAttack().run(run("full", "hmac"), "PERSON", "full", "hmac")
    assert result.accuracy_top1 < 0.2
    assert result.candidates == 34


def test_document_randomisation_sits_between_the_two():
    det = FrequencyAttack().run(run("deterministic", "hmac"), "PERSON", "deterministic", "hmac")
    doc = FrequencyAttack().run(run("document", "hmac"), "PERSON", "document", "hmac")
    full = FrequencyAttack().run(run("full", "hmac"), "PERSON", "full", "hmac")
    assert det.accuracy_top1 >= doc.accuracy_top1 >= full.accuracy_top1


def test_frequent_names_fall_first():
    """The curve the hash-vs-HMAC question turns on: accuracy against frequency band."""
    result = FrequencyAttack().run(run("deterministic", "hash"), "PERSON", "deterministic", "hash")
    assert result.by_frequency_band["20+"] == 1.0


def test_external_reference_is_weaker_than_the_corpus_itself():
    """A gazetteer whose ordering disagrees with the corpus recovers less. The realistic setting."""
    result = run("deterministic", "hmac")
    internal = FrequencyAttack().run(result, "PERSON", "deterministic", "hmac")
    external = FrequencyAttack(
        reference={"PERSON\x1fvogt": 99.0, "PERSON\x1fkraus": 50.0, "PERSON\x1fweber": 1.0}
    ).run(result, "PERSON", "deterministic", "hmac")
    assert external.accuracy_top1 < internal.accuracy_top1
    assert external.notes.startswith("reference: external")


def test_empty_type_is_reported_not_crashed():
    result = FrequencyAttack().run(run("deterministic", "hmac"), "LOC", "deterministic", "hmac")
    assert result.candidates == 0 and result.accuracy_top1 == 0.0


def test_spearman_edge_cases():
    assert spearman([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert spearman([1], [1]) is None
    assert spearman([1, 1, 1], [1, 2, 3]) is None
