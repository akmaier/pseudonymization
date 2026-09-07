"""A1's results are mostly statements about the threat model; the tests say which is which."""

import pytest

from pseudonymkit.attacks import DictionaryAttack, deterministic_inverter
from pseudonymkit.domain import Corpus, Document, Mention, Span
from pseudonymkit.engine import Pseudonymiser
from pseudonymkit.inventories import SyntheticInventory
from pseudonymkit.keys import NORMALISERS
from pseudonymkit.policies import POLICIES
from pseudonymkit.surrogates import SURROGATES
from pseudonymkit.techniques import TECHNIQUES

NAMES = ["Weber", "Meyer", "Schulz", "Kraus", "Vogt"]
DICTIONARY = [("Weber", 50_000.0), ("Meyer", 20_000.0), ("Schulz", 5_000.0), ("Kraus", 50.0)]
# 'Vogt' is deliberately absent: a dictionary attack cannot recover what it never enumerates.


def corpus() -> Corpus:
    docs = []
    for i, name in enumerate(NAMES):
        text = f"{name} testified."
        docs.append(Document(f"d{i}", text, "en",
                             (Mention(f"d{i}", "m0", Span(0, len(name), name, "PERSON"),
                                      gold_entity_id=name),)))
    return Corpus("dict", tuple(docs))


def run(policy: str, technique_name: str):
    normaliser = NORMALISERS.create("N2")
    technique = TECHNIQUES.create(technique_name)
    surrogate = SURROGATES.create("realistic", inventory=SyntheticInventory())
    engine = Pseudonymiser(normaliser, POLICIES.create(policy), technique, surrogate)
    result = engine.pseudonymise_corpus(corpus())
    # The attacker rebuilds the same public chain, with a fresh surrogate of the same kind.
    attacker_surrogate = SURROGATES.create("realistic", inventory=SyntheticInventory())
    inverter = deterministic_inverter(normaliser, technique, attacker_surrogate, "PERSON")
    return result, technique, inverter


def test_unkeyed_hash_is_inverted_for_every_dictionary_name():
    result, technique, inverter = run("deterministic", "hash")
    r = DictionaryAttack(DICTIONARY).run(result, "PERSON", "deterministic", technique, inverter)
    assert r.recovered_top1 == 4          # the four names in the dictionary
    assert r.accuracy_top1 == pytest.approx(4 / 5)


def test_a_name_absent_from_the_dictionary_survives():
    """The attack recovers what it enumerates and nothing else."""
    result, technique, inverter = run("deterministic", "hash")
    r = DictionaryAttack(DICTIONARY).run(result, "PERSON", "deterministic", technique, inverter)
    assert r.by_frequency_band["not in dictionary"] == 0.0
    assert r.by_frequency_band["very common"] == 1.0


@pytest.mark.parametrize("technique", ["hmac", "aes_siv", "table"])
def test_keyed_techniques_are_out_of_scope_not_resistant(technique):
    """Refusing to score is the honest outcome: the attacker cannot evaluate the function at all."""
    result, tech, inverter = run("deterministic", technique)
    r = DictionaryAttack(DICTIONARY).run(result, "PERSON", "deterministic", tech, inverter)
    assert r.accuracy_top1 == 0.0
    assert "threat model, not a measured resistance" in r.notes


def test_non_deterministic_policies_are_out_of_scope():
    result, technique, inverter = run("document", "hash")
    r = DictionaryAttack(DICTIONARY).run(result, "PERSON", "document", technique, inverter)
    assert r.accuracy_top1 == 0.0 and "document or mention id" in r.notes


def test_missing_inverter_is_refused_rather_than_guessed():
    result, technique, _ = run("deterministic", "hash")
    r = DictionaryAttack(DICTIONARY).run(result, "PERSON", "deterministic", technique, None)
    assert r.accuracy_top1 == 0.0


def test_length_bands_are_reported():
    result, technique, inverter = run("deterministic", "hash")
    r = DictionaryAttack(DICTIONARY).run(result, "PERSON", "deterministic", technique, inverter)
    assert "5-7=" in r.notes
