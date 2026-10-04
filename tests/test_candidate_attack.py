"""A4 — the ranked candidate list (experiment_plan.md §8.4), and the §15 safeguards on it.

No gateway is called: the ranker is a stand-in.  What is tested is the part that decides whether the
attack measures what it claims — that candidates and context come from the corpus and never from the
document under attack, that the target occurrence is identifiable even under condition C where every
person is the same string, that the report carries rates and not names, and that the stratification
§8.4 requires says so when its labels are absent.
"""

from __future__ import annotations

import pytest

from pseudonymkit.attacks.candidates import (
    MARK_CLOSE,
    MARK_OPEN,
    A4Report,
    CandidateSet,
    LlmCandidateRanker,
    build_items,
    score,
)
from pseudonymkit.conditions import build as build_condition
from pseudonymkit.domain import Corpus, Document, Mention, Span
from pseudonymkit.inventories import SyntheticInventory

KEY = b"\x44" * 32


def condition(name: str):
    if name == "A":
        return build_condition("A")
    return build_condition(name, inventory=SyntheticInventory(pool_size=4096), key=KEY)


def doc(doc_id: str, text: str, entities) -> Document:
    cursor = 0
    mentions = []
    for i, (surface, chain) in enumerate(entities):
        start = text.index(surface, cursor)
        cursor = start + len(surface)
        mentions.append(
            Mention(doc_id, f"m{i}", Span(start, start + len(surface), surface, "PERSON"),
                    gold_entity_id=chain)
        )
    return Document(doc_id, text, "en", tuple(mentions))


@pytest.fixture
def corpus() -> Corpus:
    return Corpus("fixture", (
        doc("d1", "Weber signed the audit report.", [("Weber", "e1")]),
        doc("d2", "Meyer chaired the risk committee.", [("Meyer", "e2")]),
        doc("d3", "Weber wrote to Meyer about the audit.", [("Weber", "e1"), ("Meyer", "e2")]),
        doc("d4", "Schulz reviewed the contract.", [("Schulz", "e3")]),
    ))


class Ranker:
    """A ranker whose behaviour is knowable: it puts the named identity first."""

    def __init__(self, choose, name="stub-ranker"):
        self.name = name
        self._choose = choose
        self.prompts: list[CandidateSet] = []

    def rank(self, item):
        self.prompts.append(item)
        target = self._choose(item)
        rest = [i for i in range(len(item.candidates)) if i != target]
        return [target] + rest


def always_right(item):
    return item.truth_index


class SecondPlace:
    """Puts the true candidate second, whatever it is — so the reciprocal rank is exactly 1/2."""

    name = "second-place"

    def rank(self, item):
        others = [i for i in range(len(item.candidates)) if i != item.truth_index]
        return others[:1] + [item.truth_index] + others[1:]


# ---------------------------------------------------------------------------------- item building


def test_the_true_identity_is_always_among_the_candidates(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1)
    assert items
    for item in items:
        assert item.truth in {c.identity for c in item.candidates}
        assert 0 <= item.truth_index < len(item.candidates)


def test_candidate_surfaces_come_from_the_corpus(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1)
    corpus_surfaces = {m.surface for d in corpus for m in d.mentions}
    for item in items:
        assert {c.surface for c in item.candidates} <= corpus_surfaces


def test_the_candidate_list_is_deterministic_given_the_seed(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    one = build_items(result, corpus, n_candidates=3, seed=7)
    two = build_items(result, corpus, n_candidates=3, seed=7)
    assert [[c.identity for c in i.candidates] for i in one] == \
           [[c.identity for c in i.candidates] for i in two]


def test_the_marked_occurrence_is_the_one_being_attacked(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1)
    for item in items:
        assert item.text.count(MARK_OPEN) == 1
        marked = item.text.split(MARK_OPEN)[1].split(MARK_CLOSE)[0]
        assert marked == item.pseudonym


def test_condition_c_is_still_scorable_although_every_person_is_one_string(corpus):
    """Naming the pseudonym would make A4 unscorable on C; naming the occurrence does not."""
    result = condition("C").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1)
    assert items
    assert {i.pseudonym for i in items} == {"[PERSON]"}
    assert len({i.truth for i in items}) > 1


def test_condition_a_marks_the_real_name(corpus):
    result = condition("A").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1)
    assert {i.pseudonym for i in items} <= {"Weber", "Meyer", "Schulz"}


def test_one_document_contributes_a_bounded_number_of_queries(corpus):
    """A thread mentioning one person forty times must not dominate the rate."""
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1, max_per_document=1)
    assert len({i.doc_id for i in items}) == len(items)


# ------------------------------------------------------------------------------ auxiliary context


def test_without_context_no_candidate_carries_any(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1, with_context=False)
    assert all(not item.has_context for item in items)


def test_context_comes_from_another_document_never_the_one_under_attack(corpus):
    """Handing the attacker the query document as its own evidence is the disjointness violation."""
    result = condition("C").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=4, seed=1, with_context=True,
                        context_window=100)
    contexts = [c.context for item in items for c in item.candidates if c.context]
    assert contexts
    for item in items:
        own_text = next(d.text for d in corpus if d.doc_id == item.doc_id)
        for candidate in item.candidates:
            assert candidate.context == "" or candidate.context not in own_text


def test_both_arms_are_available_because_8_4_requires_both(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    without = build_items(result, corpus, n_candidates=3, seed=1, with_context=False)
    with_ = build_items(result, corpus, n_candidates=3, seed=1, with_context=True)
    assert len(without) == len(with_)
    assert any(item.has_context for item in with_)


# ------------------------------------------------------------------------------------- scoring


def test_a_perfect_ranker_scores_one(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=5, seed=1)
    report = score(items, Ranker(always_right), condition="B")
    assert report.overall.rank1 == 1.0
    assert report.overall.rank5 == 1.0
    assert report.overall.mean_average_precision == 1.0


def test_a_ranker_one_place_off_loses_rank_1_but_keeps_rank_5(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=5, seed=1)
    report = score(items, SecondPlace(), condition="B")
    assert report.overall.rank1 == 0.0
    assert report.overall.rank5 == 1.0
    assert report.overall.mean_average_precision == pytest.approx(0.5)


def test_map_is_the_mean_reciprocal_rank_so_a3_a4_and_a5_are_comparable(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=5, seed=1)

    class Third:
        name = "third"

        def rank(self, item):
            others = [i for i in range(len(item.candidates)) if i != item.truth_index]
            return others[:2] + [item.truth_index] + others[2:]

    report = score(items, Third(), condition="B")
    assert report.overall.mean_average_precision == pytest.approx(1 / 3)


def test_an_unranked_candidate_is_completed_rather_than_dropped(corpus):
    """A ranker that named three of ten has no opinion about the rest; that is not unrankable."""
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1)

    class Silent:
        name = "silent"

        def rank(self, item):
            return []

    report = score(items, Silent(), condition="B")
    assert report.overall.queries == len(items)
    assert 0.0 < report.overall.mean_average_precision <= 1.0


def test_no_items_reports_no_scorable_queries():
    report = score([], Ranker(always_right), condition="B")
    assert report.overall.queries == 0
    assert "no scorable queries" in report.overall.notes


# --------------------------------------------------------------------------------- stratification


def test_stratification_says_so_when_the_labels_are_missing(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1)
    report = score(items, Ranker(always_right), condition="B")
    assert report.public_figures is None
    assert report.private is None
    assert "no public-figure labels" in report.stratification_note


def test_stratification_splits_the_rate_when_the_labels_exist(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1, public_figures={"e1"})

    class Cheating:
        """Right about the public figure, wrong about everyone else — the memorisation pattern."""

        name = "cheating"

        def rank(self, item):
            target = item.truth_index if item.public_figure else (item.truth_index + 1) % 3
            return [target] + [i for i in range(len(item.candidates)) if i != target]

    report = score(items, Cheating(), condition="B")
    assert report.public_figures is not None and report.private is not None
    assert report.public_figures.rank1 == 1.0
    assert report.private.rank1 == 0.0
    assert "stratified" in report.stratification_note


# ----------------------------------------------------------------------------- the §15 safeguards


def test_the_released_record_carries_rates_and_never_a_name(corpus):
    """§15.1: no real name from the corpus appears in any released artefact."""
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1, with_context=True,
                        public_figures={"e1"})
    record = score(items, Ranker(always_right), condition="B").to_record()
    blob = repr(record)
    for name in ("Weber", "Meyer", "Schulz"):
        assert name not in blob
    assert "audit" not in blob and "committee" not in blob
    assert record["overall"]["rank1"] == 1.0


def test_the_report_states_which_arm_produced_it(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    with_context = build_items(result, corpus, n_candidates=3, seed=1, with_context=True)
    record = score(with_context, Ranker(always_right), condition="B").to_record()
    assert record["with_context"] is True
    assert record["n_candidates"] == 3


# ------------------------------------------------------------------------------- the LLM ranker


class FakeClient:
    def __init__(self, reply):
        self._reply = reply
        self.prompts: list[tuple[str, str]] = []

    def ask(self, system, user, **kwargs):
        from pseudonymkit.gateway import Reply

        self.prompts.append((system, user))
        return Reply(text=self._reply, finish_reason="stop")


def test_the_llm_ranker_answers_with_numbers_not_names(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1)
    client = FakeClient("[2, 0, 1]")
    ranker = LlmCandidateRanker().use(client)
    assert ranker.rank(items[0]) == [2, 0, 1]
    system, user = client.prompts[0]
    assert "JSON array of candidate numbers" in system
    assert user.startswith("Candidates:\n0. ")


def test_the_llm_ranker_tolerates_prose_around_the_array(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1)
    ranker = LlmCandidateRanker().use(FakeClient("Here you go: [1,0,2]. Hope that helps!"))
    assert ranker.rank(items[0]) == [1, 0, 2]


def test_the_llm_ranker_drops_numbers_outside_the_candidate_list(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    items = build_items(result, corpus, n_candidates=3, seed=1)
    ranker = LlmCandidateRanker().use(FakeClient("[9, 1, 1, -3, 0]"))
    assert ranker.rank(items[0]) == [1, 0]


def test_the_llm_prompt_shows_context_only_in_the_context_arm(corpus):
    result = condition("B").pseudonymise_corpus(corpus)
    with_context = build_items(result, corpus, n_candidates=4, seed=1, with_context=True)
    ranker = LlmCandidateRanker().use(FakeClient("[0]"))
    prompt = ranker.prompt(with_context[0])
    assert "known from the corpus" in prompt

    without = build_items(result, corpus, n_candidates=4, seed=1, with_context=False)
    assert "known from the corpus" not in ranker.prompt(without[0])


# ------------------------------------------------------- outcome classes and regimes (§8.4, 2026-10-04)


from pseudonymkit.attacks.candidates import OUTCOMES, Abstention, query_key  # noqa: E402


class Abstainer:
    name = "abstainer"
    allows_abstention = True

    def rank(self, item):
        return Abstention()


class Silent:
    """A ranker whose reply named nothing — a failed call, not an answer."""

    name = "silent"
    allows_abstention = True

    def rank(self, item):
        return []


def b_items(corpus, n=3, seed=1):
    return build_items(condition("B").pseudonymise_corpus(corpus), corpus, n_candidates=n,
                       seed=seed)


def test_a_right_first_choice_is_recovered(corpus):
    report = score(b_items(corpus), Ranker(always_right), condition="B")
    assert report.outcome_counts()["recovered"] == len(report.outcomes) > 0
    assert set(report.outcome_counts()) == set(OUTCOMES)


def test_a_wrong_choice_named_like_the_surrogate_is_misled_and_only_under_b(corpus):
    items = b_items(corpus)
    item = items[0]
    wrong = next(i for i in range(len(item.candidates)) if i != item.truth_index)
    # The surrogate is made to share a name with the wrong candidate, as a gazetteer name can.
    named = CandidateSet(doc_id=item.doc_id, text=item.text, truth=item.truth,
                         candidates=item.candidates,
                         pseudonym=item.candidates[wrong].surface, target=item.target)
    picks_wrong = Ranker(lambda _: wrong)
    assert score([named], picks_wrong, condition="B").outcomes[0]["outcome"] == "misled"
    assert score([named], picks_wrong, condition="C").outcomes[0]["outcome"] == "failed"
    unrelated = CandidateSet(doc_id=item.doc_id, text=item.text, truth=item.truth,
                             candidates=item.candidates, pseudonym="Qzxv", target=item.target)
    assert score([unrelated], picks_wrong, condition="B").outcomes[0]["outcome"] == "failed"


def test_an_explicit_abstention_is_its_own_class_and_never_recovers(corpus):
    report = score(b_items(corpus), Abstainer(), condition="B")
    assert report.outcome_counts()["abstained"] == len(report.outcomes)
    assert report.overall.rank1 == 0.0
    assert all(r["rank"] == len(b_items(corpus)[0].candidates) for r in report.outcomes)


def test_an_empty_reply_is_not_an_abstention(corpus):
    report = score(b_items(corpus), Silent(), condition="B")
    assert report.outcome_counts()["abstained"] == 0
    assert report.metadata["unanswered"] == len(report.outcomes)


def test_a_forced_ranker_cannot_abstain(corpus):
    class Forced(Abstainer):
        allows_abstention = False

    assert score(b_items(corpus), Forced(), condition="B").outcome_counts()["abstained"] == 0


def test_the_pairing_key_is_the_same_under_b_and_c_and_carries_no_identity(corpus):
    b = build_items(condition("B").pseudonymise_corpus(corpus), corpus, n_candidates=3, seed=1)
    c = build_items(condition("C").pseudonymise_corpus(corpus), corpus, n_candidates=3, seed=1)
    assert [query_key(i) for i in b] == [query_key(i) for i in c]
    assert len({query_key(i) for i in b}) == len(b)
    record = score(b, Ranker(always_right), condition="B")
    blob = repr(record.per_query()) + repr(record.to_record())
    for name in ("Weber", "Meyer", "Schulz", "e1", "e2", "e3"):
        assert name not in blob


def test_per_query_columns_line_up(corpus):
    report = score(b_items(corpus), SecondPlace(), condition="B")
    columns = report.per_query()
    assert len(columns["key"]) == len(columns["rank"]) == len(columns["outcome"])
    assert set(columns["rank"]) == {2}
    assert set(columns["outcome"]) <= {"m", "f"}


def test_the_free_prompt_allows_none_and_reads_an_explicit_empty_array(corpus):
    item = b_items(corpus)[0]
    ranker = LlmCandidateRanker(regime="free").use(FakeClient("[]"))
    assert isinstance(ranker.rank(item), Abstention)
    assert "may or may not be one of the candidates" in ranker.client.prompts[0][0]
    assert ranker.name.endswith("/a4-free")
    prose = LlmCandidateRanker(regime="free").use(FakeClient("I cannot tell."))
    assert not isinstance(prose.rank(item), Abstention)


def test_the_forced_ranker_keeps_its_name_and_prompt(corpus):
    item = b_items(corpus)[0]
    ranker = LlmCandidateRanker().use(FakeClient("[]"))
    assert not isinstance(ranker.rank(item), Abstention)
    assert ranker.name == "llm:gpt-oss-120b/a4"
    assert ranker.client.prompts[0][0] == LlmCandidateRanker.SYSTEM


def test_an_unknown_regime_is_refused():
    with pytest.raises(ValueError):
        LlmCandidateRanker(regime="open")
