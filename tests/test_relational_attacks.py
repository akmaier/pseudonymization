"""A3 and A5 attack the profile pseudonymisation leaves behind, so the tests check that the
profile survives, that the learned attacker generalises, and that the policy axis controls both."""

import pytest

from pseudonymkit.attacks import (
    LearnedLinkage, StructuralLinkage, build_gallery, build_queries, truth_map,
)
from pseudonymkit.domain import Corpus, Document, Mention, Span
from pseudonymkit.engine import Pseudonymiser
from pseudonymkit.keys import NORMALISERS
from pseudonymkit.policies import POLICIES
from pseudonymkit.surrogates import SURROGATES
from pseudonymkit.techniques import TECHNIQUES

TOPICS = {
    "alice": "quarterly gas pipeline capacity nomination scheduling",
    "bob": "litigation deposition counsel subpoena discovery filing",
    "carol": "trading floor position limits hedging volatility desk",
    "dave": "recruiting interview candidate offer relocation package",
    "erin": "server outage database backup latency incident report",
    "frank": "budget forecast variance allocation headcount approval",
}


def corpus() -> Corpus:
    """Each person is written *about* by others, in a consistent topical context.

    That is the shape the attack exploits, and the shape stylometry could not: the identifying
    signal belongs to the subject, not to whoever typed the message.
    """
    docs = []
    n = 0
    for person, topic in TOPICS.items():
        for i in range(6):
            other = [p for p in TOPICS if p != person][i % (len(TOPICS) - 1)]
            text = f"{person.title()} discussed {topic} with {other.title()} again."
            mentions = []
            for who in (person, other):
                start = text.index(who.title())
                mentions.append(
                    Mention(f"d{n}", f"m{who}", Span(start, start + len(who), who.title(), "PERSON"),
                            gold_entity_id=who)
                )
            docs.append(Document(f"d{n}", text, "en", tuple(mentions)))
            n += 1
    return Corpus("profiles", tuple(docs))


def pseudonymise(policy: str, technique: str = "hmac"):
    engine = Pseudonymiser(
        NORMALISERS.create("N2"), POLICIES.create(policy),
        TECHNIQUES.create(technique), SURROGATES.create("tag"),
    )
    return engine.pseudonymise_corpus(corpus())


def parts(policy: str, technique: str = "hmac"):
    result = pseudonymise(policy, technique)
    return build_queries(result), build_gallery(corpus()), truth_map(result)


def test_the_profile_survives_pseudonymisation():
    """Names are replaced; context and relations are not. That is what the attacks consume."""
    queries, gallery, truth = parts("deterministic")
    assert len(queries) == len(gallery) == len(TOPICS)
    q = queries[next(iter(truth))]
    assert q.mentions > 0 and q.context and q.neighbours


def test_query_context_is_read_from_the_pseudonymised_text():
    """The attacker must never see anything a released corpus would not contain."""
    queries, _, _ = parts("deterministic")
    joined = " ".join(t for p in queries.values() for t in p.context)
    assert not any(name in joined for name in TOPICS)


def test_structural_attack_recovers_identity_under_a_deterministic_policy():
    queries, gallery, truth = parts("deterministic")
    r = StructuralLinkage().run(queries, gallery, truth, "deterministic", "hmac")
    assert r.rank1 == 1.0 and r.queries == len(TOPICS)


@pytest.mark.parametrize("technique", TECHNIQUES.names())
def test_the_attack_is_indifferent_to_the_technique(technique):
    """As A1 and A2 already showed: the cryptography is not what decides this."""
    queries, gallery, truth = parts("deterministic", technique)
    assert StructuralLinkage().run(queries, gallery, truth, "deterministic", technique).rank1 == 1.0


def test_full_randomisation_destroys_the_profile():
    """Every mention becomes a different pseudonym, so no entity profile can be assembled."""
    queries, gallery, truth = parts("full")
    r = StructuralLinkage().run(queries, gallery, truth, "full", "hmac")
    assert r.rank1 < 1.0


def test_learned_attacker_uses_disjoint_entities():
    """Evaluating on trained entities would measure memorisation, not attack strength."""
    queries, gallery, truth = parts("deterministic")
    r = LearnedLinkage(train_fraction=0.5, seed=1).run(queries, gallery, truth, "deterministic", "hmac")
    assert r.queries < len(TOPICS)
    assert "disjoint" in r.notes


def test_learned_attacker_refuses_a_split_it_cannot_make():
    queries, gallery, truth = parts("deterministic")
    tiny = dict(list(truth.items())[:2])
    r = LearnedLinkage().run(queries, gallery, tiny, "deterministic", "hmac")
    assert "too few entities" in r.notes


def test_results_carry_the_reidentification_metrics():
    """Rank-1, Rank-5 and mAP, so the numbers sit beside the imaging re-identification literature."""
    queries, gallery, truth = parts("deterministic")
    d = StructuralLinkage().run(queries, gallery, truth, "deterministic", "hmac").as_dict()
    assert {"rank1", "rank5", "mAP", "queries", "gallery"} <= set(d)


# --- the evaluation protocol itself -------------------------------------------

from pseudonymkit.attacks import disjoint_document_split  # noqa: E402


def test_split_is_disjoint_and_covers_everything():
    gallery_docs, query_docs = disjoint_document_split(corpus(), seed=0)
    assert not (gallery_docs & query_docs)
    assert len(gallery_docs | query_docs) == len(corpus())


def test_split_is_reproducible_from_the_seed():
    assert disjoint_document_split(corpus(), seed=3) == disjoint_document_split(corpus(), seed=3)
    assert disjoint_document_split(corpus(), seed=3) != disjoint_document_split(corpus(), seed=4)


def test_same_document_evaluation_is_easier_than_disjoint():
    """The point of the split.

    With the gallery drawn from the same documents as the queries, only the entity spans differ and
    the attack matches a corpus against itself. A disjoint split forces it to generalise across
    documents, which is what a real adversary faces -- and it must not score higher.
    """
    result = pseudonymise("deterministic")
    truth = truth_map(result)

    leaky = StructuralLinkage().run(
        build_queries(result), build_gallery(corpus()), truth, "deterministic", "hmac"
    )
    gallery_docs, query_docs = disjoint_document_split(corpus(), seed=0)
    honest = StructuralLinkage().run(
        build_queries(result, documents=query_docs),
        build_gallery(corpus(), documents=gallery_docs),
        truth, "deterministic", "hmac",
    )
    assert honest.rank1 <= leaky.rank1


# ------------------------------------------------------- condition A as the ceiling (§8.4)
#
# "A3, A4 and A5 are run on condition A as well, where nothing has been replaced. That is the
# ceiling — what the adversary recovers with no protection at all — and without it a leakage rate
# on B or C has no scale."  No attack needs a special case: conditions.Unmodified produces a
# PseudonymisedCorpus whose text is the corpus's own and whose assignments map each mention to its
# own surface, so build_queries, truth_map and build_items all read it unchanged.


def _condition(name: str):
    from pseudonymkit.conditions import build as build_condition
    from pseudonymkit.inventories import SyntheticInventory

    if name == "A":
        return build_condition("A")
    return build_condition(name, inventory=SyntheticInventory(pool_size=4096), key=b"\x55" * 32)


def _condition_parts(name: str):
    source = corpus()
    result = _condition(name).pseudonymise_corpus(source)
    return build_queries(result), build_gallery(source), truth_map(result)


def test_condition_a_leaves_the_corpus_untouched_and_still_builds_queries():
    source = corpus()
    result = _condition("A").pseudonymise_corpus(source)
    assert [d.text for d in result.documents] == [d.text for d in source.documents]
    queries, gallery, truth = _condition_parts("A")
    assert queries and gallery and truth


def test_a3_runs_on_condition_a_as_the_ceiling():
    queries, gallery, truth = _condition_parts("A")
    result = StructuralLinkage().run(queries, gallery, truth, policy="none", technique="none")
    assert result.queries > 0
    assert result.rank1 == 1.0, "with no protection at all the adversary recovers everything"


def test_a5_runs_on_condition_a_too():
    queries, gallery, truth = _condition_parts("A")
    # 0.7 rather than the default 0.5: the fixture holds six entities, and an even split leaves
    # three to train on, which LearnedLinkage refuses as too few to make a disjoint split from.
    result = LearnedLinkage(train_fraction=0.7, seed=1).run(
        queries, gallery, truth, policy="none", technique="none"
    )
    assert result.queries > 0
    assert "disjoint" in result.notes
    assert result.rank1 == 1.0


def test_the_ceiling_is_at_least_as_high_as_the_protected_conditions():
    """The number that gives a leakage rate on B or C its scale."""
    scores = {}
    for name in ("A", "B", "C"):
        queries, gallery, truth = _condition_parts(name)
        scores[name] = StructuralLinkage().run(
            queries, gallery, truth, policy="none", technique="none"
        ).rank1
    assert scores["A"] >= scores["B"] >= scores["C"]


def test_condition_c_leaves_the_attacker_almost_nothing_to_link():
    """Every person is one string, so there is no per-entity query left to score."""
    queries, gallery, truth = _condition_parts("C")
    assert set(queries) == {"[PERSON]"}
    assert truth == {}, "one pseudonym over many gold entities cannot be scored either way"


def test_a4_runs_on_condition_a():
    from pseudonymkit.attacks.candidates import build_items
    from pseudonymkit.attacks.candidates import score as score_candidates

    source = corpus()
    result = _condition("A").pseudonymise_corpus(source)
    items = build_items(result, source, n_candidates=6, seed=0)
    assert items

    class Surface:
        """Picks the candidate whose corpus surface is the marked text — trivial with no protection."""

        name = "surface-match"

        def rank(self, item):
            marked = item.text.split("«")[1].split("»")[0]
            order = sorted(
                range(len(item.candidates)),
                key=lambda i: item.candidates[i].surface != marked,
            )
            return order

    report = score_candidates(items, Surface(), condition="A")
    assert report.overall.rank1 == 1.0
