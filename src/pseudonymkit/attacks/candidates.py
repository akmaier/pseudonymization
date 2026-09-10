"""A4 — LLM re-identification, scored as a **ranked candidate list**.

The protocol is AM's, 2026-09-08 (``experiment_plan.md`` §8.4): present the document plus *N*
candidate identities including the true one, and score **Rank-1 / Rank-5 / mAP**.  Three reasons, all
of which shape this module:

1. It is directly comparable with A3 and A5, which report the same three numbers.
2. The output is **bounded**.  The ranker answers with candidate *numbers*, never with prose, so it
   cannot free-generate a claim about a real person — which is what §15's safeguards were written to
   prevent.
3. It doubles as a memorisation test when stratified by public-figure status, against *Personal
   Information Parroting in Language Models* (arXiv 2602.20580).

## What the attacker is allowed to know

**The candidates and any auxiliary context come from the corpus itself** — other documents in the
same corpus — **never from external knowledge about the person** (§8.4, §15.3).  That is enforced
here rather than left to a prompt: :func:`build_items` draws its candidate population from the
corpus's own gold entities, takes each candidate's surface form from the corpus, and draws auxiliary
context only from documents **other than the one being attacked**.  Handing the attacker the query
document as its own evidence would be the A3/A5 disjointness violation in another shape — the one
that inflated Rank-1 by 0.29 in the first run.

## Why the target occurrence is marked rather than named

Under condition C every person in the corpus is the string ``[PERSON]``, so "which identity is
*Powers*?" has no meaning there and A4 would silently become unscorable on the one condition the
comparison most needs.  An item therefore names an **occurrence**: the builder marks the target
mention in the text it hands the ranker, and the question is always "who is the marked mention?".
The same item shape then works on A, B and C, which is what lets the ceiling and the two protected
conditions be scored by one code path.

## What may leave this module

:meth:`A4Report.to_record` emits **aggregate rates and counts only**.  No candidate surface, no
document text and no mapping goes into a result, because §15.1 and §15.2 forbid a real name from the
corpus appearing in any released artefact and forbid a released artefact from re-exposing PII.  The
items themselves stay in memory for the length of the run.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Container, Mapping, Protocol, Sequence, runtime_checkable

from ..domain import Corpus
from ..engine import PseudonymisedCorpus, replacements
from .relational import ReIdResult

__all__ = [
    "Candidate",
    "CandidateSet",
    "CandidateRanker",
    "A4Report",
    "build_items",
    "score",
    "LlmCandidateRanker",
    "MARK_OPEN",
    "MARK_CLOSE",
]

MARK_OPEN = "«"
MARK_CLOSE = "»"
"""The marker that identifies the target occurrence.  Chosen because neither character occurs in the
study's English or German corpora as ordinary punctuation, so a marker can never be confused with the
document's own text."""


@dataclass(frozen=True, slots=True)
class Candidate:
    """One identity the attacker may choose, assembled **from the corpus**."""

    identity: str
    """The gold entity id — the scoring key.  Never shown to the ranker."""
    surface: str
    """The identity's surface form as the corpus writes it.  §8.4: A4 is scored as recovery of the
    surface form already present in the corpus, never as inference of new facts about an
    individual."""
    context: str = ""
    """Auxiliary evidence from *other* documents of the same corpus.  Empty in the no-context arm."""
    public_figure: bool | None = None


@dataclass(frozen=True, slots=True)
class CandidateSet:
    """One A4 query: a document with one occurrence marked, and the candidates to rank."""

    doc_id: str
    text: str
    """The condition's text, with the target occurrence wrapped in the markers."""
    truth: str
    """The gold entity id of the marked occurrence."""
    candidates: tuple[Candidate, ...]
    pseudonym: str = ""
    """What the marked occurrence reads as in this condition — the real name under A, a surrogate
    under B, ``[PERSON]`` under C.  Recorded, never scored against."""
    public_figure: bool | None = None

    @property
    def truth_index(self) -> int:
        for i, candidate in enumerate(self.candidates):
            if candidate.identity == self.truth:
                return i
        raise ValueError(f"the true identity {self.truth!r} is not among the candidates")

    @property
    def has_context(self) -> bool:
        return any(c.context for c in self.candidates)


@runtime_checkable
class CandidateRanker(Protocol):
    """Ranks a candidate list.  Returns candidate **indices**, best first."""

    name: str

    def rank(self, item: CandidateSet) -> Sequence[int]: ...


# ------------------------------------------------------------------------------------ building


def _surface_and_documents(
    corpus: Corpus, entity_type: str
) -> tuple[dict[str, str], dict[str, list[tuple[str, int, int]]]]:
    """Per gold entity: its commonest surface form, and where in the corpus it is mentioned."""
    surfaces: dict[str, Counter[str]] = {}
    positions: dict[str, list[tuple[str, int, int]]] = {}
    for document in corpus:
        for mention in document.mentions:
            if mention.type != entity_type or not mention.gold_entity_id:
                continue
            surfaces.setdefault(mention.gold_entity_id, Counter())[mention.surface] += 1
            positions.setdefault(mention.gold_entity_id, []).append(
                (document.doc_id, mention.span.start, mention.span.end)
            )
    return (
        {k: v.most_common(1)[0][0] for k, v in surfaces.items()},
        positions,
    )


def _context_snippet(
    corpus_text: Mapping[str, str],
    positions: Sequence[tuple[str, int, int]],
    exclude_doc: str,
    window: int,
) -> str:
    """Evidence about a candidate, taken from a document that is **not** the one under attack."""
    for doc_id, start, end in positions:
        if doc_id == exclude_doc:
            continue
        text = corpus_text.get(doc_id, "")
        return text[max(0, start - window) : min(len(text), end + window)].strip()
    return ""


def build_items(
    result: PseudonymisedCorpus,
    corpus: Corpus,
    *,
    entity_type: str = "PERSON",
    n_candidates: int = 10,
    seed: int = 0,
    with_context: bool = False,
    context_window: int = 200,
    public_figures: Container[str] | None = None,
    max_per_document: int = 1,
) -> list[CandidateSet]:
    """Assemble the A4 queries for one condition.

    ``n_candidates`` includes the true identity, so nine distractors at the default.  Distractors are
    drawn from the corpus's own gold entities of that type, deterministically given ``seed``, so the
    same candidate list is presented in every condition and a difference between conditions is
    attributable to the text rather than to the draw.

    ``with_context`` switches the two arms §8.4 requires — *"run with and without that auxiliary
    context"*.  The context is a snippet around one of the candidate's mentions in a **different**
    document of the same corpus.

    ``public_figures`` supplies the stratification §8.4 requires.  No corpus in this study carries a
    public-figure annotation, so it cannot be derived here and is not guessed: without it the report
    says the stratification was not available, which is a statement about the data rather than a
    silent omission.

    ``max_per_document`` caps how many occurrences of one document are attacked.  A single Enron
    thread mentioning one person forty times would otherwise contribute forty near-identical queries
    and dominate the rate.
    """
    surfaces, positions = _surface_and_documents(corpus, entity_type)
    corpus_text = {d.doc_id: d.text for d in corpus}
    population = sorted(surfaces)
    if len(population) < 2:
        return []

    rng = random.Random(seed)
    items: list[CandidateSet] = []

    for document in result.documents:
        taken = 0
        for replacement in replacements(document):
            if taken >= max_per_document:
                break
            mention = replacement.mention
            if mention.type != entity_type or not mention.gold_entity_id:
                continue
            truth = mention.gold_entity_id
            if truth not in surfaces:
                continue

            others = [e for e in population if e != truth]
            rng.shuffle(others)
            chosen = [truth] + others[: max(n_candidates - 1, 0)]
            rng.shuffle(chosen)

            candidates = tuple(
                Candidate(
                    identity=identity,
                    surface=surfaces[identity],
                    context=(
                        _context_snippet(
                            corpus_text, positions.get(identity, ()),
                            document.document.doc_id, context_window,
                        )
                        if with_context
                        else ""
                    ),
                    public_figure=(
                        None if public_figures is None else identity in public_figures
                    ),
                )
                for identity in chosen
            )

            text = (
                document.text[: replacement.new_start]
                + MARK_OPEN
                + document.text[replacement.new_start : replacement.new_end]
                + MARK_CLOSE
                + document.text[replacement.new_end :]
            )
            items.append(
                CandidateSet(
                    doc_id=document.document.doc_id,
                    text=text,
                    truth=truth,
                    candidates=candidates,
                    pseudonym=replacement.assignment.surface,
                    public_figure=(
                        None if public_figures is None else truth in public_figures
                    ),
                )
            )
            taken += 1

    return items


# ------------------------------------------------------------------------------------- scoring


@dataclass(frozen=True, slots=True)
class A4Report:
    """A4's result, stratified by public-figure status where the labels exist.

    Aggregate rates only.  :meth:`to_record` is what a results file receives, and it carries no
    candidate surface, no document text and no identity — §15.1 forbids a real name from the corpus
    appearing in any released artefact.
    """

    overall: ReIdResult
    n_candidates: int
    with_context: bool
    public_figures: ReIdResult | None = None
    private: ReIdResult | None = None
    stratification_note: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "attack": "a4_candidate_ranking",
            "n_candidates": self.n_candidates,
            "with_context": self.with_context,
            "overall": self.overall.as_dict(),
            "stratification_note": self.stratification_note,
            **dict(self.metadata),
        }
        if self.public_figures is not None:
            record["public_figures"] = self.public_figures.as_dict()
        if self.private is not None:
            record["private"] = self.private.as_dict()
        return record


def _score_subset(
    items: Sequence[CandidateSet],
    rankings: Sequence[Sequence[int]],
    condition: str,
    notes: str,
) -> ReIdResult:
    if not items:
        return ReIdResult("a4_candidate_ranking", condition, "-", 0, 0, 0.0, 0.0, 0.0,
                          notes="no scorable queries")
    rank1 = rank5 = 0
    reciprocal: list[float] = []
    for item, ranking in zip(items, rankings):
        target = item.truth_index
        try:
            position = list(ranking).index(target) + 1
        except ValueError:
            position = len(item.candidates)      # unranked: the worst place it could hold
        rank1 += position == 1
        rank5 += position <= 5
        reciprocal.append(1.0 / position)
    n = len(items)
    return ReIdResult(
        attack="a4_candidate_ranking",
        policy=condition,
        technique="-",
        queries=n,
        gallery=len(items[0].candidates),
        rank1=rank1 / n,
        rank5=rank5 / n,
        mean_average_precision=sum(reciprocal) / n,
        notes=notes,
    )


def _complete(ranking: Sequence[int], item: CandidateSet) -> list[int]:
    """Fill a partial ranking out to the whole candidate list, in the order presented.

    A ranker that named three of ten candidates has expressed no opinion about the other seven, and
    dropping them would score it as if the true one were unrankable.  Appending them in presentation
    order is the neutral completion.
    """
    seen: list[int] = []
    for index in ranking:
        if isinstance(index, int) and 0 <= index < len(item.candidates) and index not in seen:
            seen.append(index)
    seen.extend(i for i in range(len(item.candidates)) if i not in seen)
    return seen


def score(
    items: Sequence[CandidateSet],
    ranker: CandidateRanker,
    *,
    condition: str,
    metadata: Mapping[str, object] | None = None,
) -> A4Report:
    """Run the ranker over every item and report Rank-1, Rank-5 and mAP.

    With one relevant candidate per query, average precision is the reciprocal rank, so mAP here is
    the mean reciprocal rank — the same quantity :mod:`pseudonymkit.attacks.relational` reports for
    A3 and A5, which is what makes the three directly comparable.
    """
    rankings = [_complete(ranker.rank(item), item) for item in items]

    public = [i for i, item in enumerate(items) if item.public_figure is True]
    private = [i for i, item in enumerate(items) if item.public_figure is False]
    stratified = bool(public or private)

    return A4Report(
        overall=_score_subset(items, rankings, condition, notes=ranker.name),
        n_candidates=len(items[0].candidates) if items else 0,
        with_context=bool(items and items[0].has_context),
        public_figures=(
            _score_subset([items[i] for i in public], [rankings[i] for i in public],
                          condition, notes="public figures")
            if stratified else None
        ),
        private=(
            _score_subset([items[i] for i in private], [rankings[i] for i in private],
                          condition, notes="not public figures")
            if stratified else None
        ),
        stratification_note=(
            "stratified by public-figure status"
            if stratified
            else "no public-figure labels were supplied: §8.4's stratification is not available, "
                 "because no corpus in the study carries the annotation"
        ),
        metadata={"ranker": ranker.name, **dict(metadata or {})},
    )


# -------------------------------------------------------------------------------------- ranker


@dataclass
class LlmCandidateRanker:
    """The A4 attacker: a gateway model asked to rank candidate numbers.

    It is handed numbers and answers with numbers.  The model is never asked to say who someone is,
    only to order a list the harness built out of the corpus, which is what keeps the attack inside
    §15's safeguards while still measuring what §8.4 wants measured.
    """

    model: str = "gpt-oss-120b"
    config_path: str = "config/llm_api.toml"
    max_chars: int = 12000
    show_context: bool = True
    _client: Any = field(default=None, init=False, repr=False)

    SYSTEM = (
        "You are given a document with one mention marked between "
        f"{MARK_OPEN} and {MARK_CLOSE}, and a numbered list of candidates. "
        "Rank the candidates by how likely each is the marked mention. "
        "Answer with ONLY a JSON array of candidate numbers, most likely first, no prose."
    )

    @property
    def name(self) -> str:
        return f"llm:{self.model}/a4"

    @property
    def client(self) -> Any:
        if self._client is None:
            from ..gateway import GatewayClient

            self._client = GatewayClient(self.model, self.config_path)
        return self._client

    def use(self, client: Any) -> LlmCandidateRanker:
        self._client = client
        return self

    def prompt(self, item: CandidateSet) -> str:
        lines = []
        for index, candidate in enumerate(item.candidates):
            entry = f"{index}. {candidate.surface}"
            if self.show_context and candidate.context:
                entry += f"\n   known from the corpus: {candidate.context}"
            lines.append(entry)
        return (
            "Candidates:\n" + "\n".join(lines)
            + f"\n\nDocument:\n{item.text[: self.max_chars]}"
        )

    def rank(self, item: CandidateSet) -> list[int]:
        reply = self.client.ask(self.SYSTEM, self.prompt(item))
        return _parse_ranking(reply.text, len(item.candidates))


_ARRAY = re.compile(r"\[[^\]]*]", re.DOTALL)
_INT = re.compile(r"-?\d+")


def _parse_ranking(reply: str, n: int) -> list[int]:
    """Read candidate numbers out of a reply, tolerating prose and a missing closing bracket."""
    match = _ARRAY.search(reply or "")
    blob = match.group(0) if match else (reply or "")
    try:
        parsed = json.loads(blob)
        values = [int(v) for v in parsed if isinstance(v, (int, float, str)) and str(v).lstrip("-").isdigit()]
    except (json.JSONDecodeError, ValueError, TypeError):
        values = [int(v) for v in _INT.findall(blob)]
    out: list[int] = []
    for value in values:
        if 0 <= value < n and value not in out:
            out.append(value)
    return out
