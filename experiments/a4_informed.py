#!/usr/bin/env python3
"""A4 against an adversary who knows the release was pseudonymised.

AM, 2026-09-25: *"It does not make sense that surrogates protect better than placeholders.
Surrogates can be mapped deterministically to placeholders with an injective map."*

The objection is right, and the patch sets prove the premise rather than assume it: conditions B and
C replace **identical spans** on every document, so overwriting each replaced span of the B release
with ``[PERSON]`` reproduces the C release character for character (verified on 1268/1268 TAB and
5994/5994 OntoNotes documents).  A release cannot be safer than a text anyone can compute from it,
so the measured gap --- Rank-1 0.085 on B against 0.290 on C --- cannot be protection.  It is the
ranker believing the surrogate.

That argument bounds the risk with an adversary who knows exactly which spans were replaced.  This
script measures the *realistic* version, who does not: it tags the released text with the same crude
capitalised-run tagger the A2 adversary uses, keeps only spans carrying a public-name-list token,
overwrites them with ``[PERSON]``, and ranks the result.  Everything else --- items, candidate
lists, seed, model, marker --- is what ``run_leakage.py --attacks a4`` already ran, so the new rate
is directly comparable with the naive one.

    .venv/bin/python experiments/a4_informed.py --corpus tab --rule union --a4-limit 200
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from dataclasses import dataclass

from pseudonymkit.attacks import LlmCandidateRanker, build_items, score_candidates
from pseudonymkit.attacks.candidates import MARK_CLOSE, MARK_OPEN, CandidateSet
from pseudonymkit.attacks.frequency import _NAME_LIKE
from pseudonymkit.construction import check_current, read_patchset, to_pseudonymised_corpus
from pseudonymkit.domain import Corpus
from pseudonymkit.paths import cardiode_a, cardiode_conditions, condition_a_dir, work_dir
from pseudonymkit.serialisation import iter_documents

SOURCES = {
    "cardiode": (cardiode_a, cardiode_conditions),
    "tab": (lambda: condition_a_dir() / "tab_A.jsonl.gz", lambda: work_dir() / "results/conditions"),
    "ontonotes": (lambda: condition_a_dir() / "ontonotes_A.jsonl.gz",
                  lambda: work_dir() / "results/conditions"),
    "enron": (lambda: condition_a_dir() / "enron_A.jsonl.gz",
              lambda: work_dir() / "results/conditions"),
}

PLACEHOLDER = "[PERSON]"
_TOKEN = re.compile(r"[A-Za-zÀ-ÿ'’\-]+")


def log(message: str, t0: float = time.time()) -> None:
    print(f"[{time.time() - t0:7.1f}s] {message}", flush=True)


def public_name_tokens() -> set[str]:
    """Given names and surnames from the two public lists A2's realistic prior already uses.

    The adversary is allowed a public name list and nothing else.  Using the study's own detectors
    here would make the attack's reach a function of the defence, which is the mistake the A2
    rewrite exists to avoid.
    """
    from pseudonymkit.attacks.priors import load_census_surnames, load_uci_given_names
    from pseudonymkit.paths import shared_corpora

    gazetteers = shared_corpora() / "gazetteers"
    tokens: set[str] = set()
    for loader, filename in ((load_census_surnames, "Names_2010Census.csv"),
                             (load_uci_given_names, "name_gender_dataset.csv")):
        path = gazetteers / filename
        if not path.exists():           # a missing list is reported, never silently narrowed
            log(f"  WARNING: {filename} not found at {path}")
            continue
        tokens.update(name.casefold() for name in loader(path))
    return tokens


def neutralise(text: str, names: set[str]) -> tuple[str, int]:
    """Overwrite every name-like span that a public list recognises with ``[PERSON]``.

    The markers around the target occurrence are kept: the attacker is told which mention to name,
    exactly as in every other A4 arm, and would in any case see ``[PERSON]`` there under C.
    """
    out: list[str] = []
    last = 0
    masked = 0
    for match in _NAME_LIKE.finditer(text):
        if not any(t.casefold() in names for t in _TOKEN.findall(match.group(0))):
            continue
        out.append(text[last:match.start()])
        out.append(PLACEHOLDER)
        last = match.end()
        masked += 1
    out.append(text[last:])
    return "".join(out), masked


def rewrite(item: CandidateSet, names: set[str]) -> tuple[CandidateSet, int]:
    head, _, rest = item.text.partition(MARK_OPEN)
    marked, _, tail = rest.partition(MARK_CLOSE)
    new_head, a = neutralise(head, names)
    new_tail, b = neutralise(tail, names)
    return (
        CandidateSet(
            doc_id=item.doc_id,
            text=new_head + MARK_OPEN + PLACEHOLDER + MARK_CLOSE + new_tail,
            truth=item.truth,
            candidates=item.candidates,
            pseudonym=PLACEHOLDER,
            public_figure=item.public_figure,
        ),
        a + b + 1,
    )


@dataclass
class ForewarnedRanker(LlmCandidateRanker):
    """The same ranker, told what Kerckhoffs says it already knows: that names were replaced.

    The masking arm neutralises the surrogate by deleting it, which also deletes whatever ordinary
    capitalised words the public list happens to contain.  This arm deletes nothing and changes only
    what the attacker believes, so the two together separate *being misled by the surrogate* from
    *losing the context around it*.
    """

    SYSTEM = (
        "You are given a document with one mention marked between "
        f"{MARK_OPEN} and {MARK_CLOSE}, and a numbered list of candidates. "
        "The document has been pseudonymised: person names in it, including the marked one, have "
        "been replaced by unrelated surrogate names drawn from a public name list. The surface "
        "form of the marked mention is therefore not evidence of who it is -- rank on the "
        "surrounding context alone. "
        "Rank the candidates by how likely each is the marked mention. "
        "Answer with ONLY a JSON array of candidate numbers, most likely first, no prose."
    )

    @property
    def name(self) -> str:
        return f"llm:{self.model}/a4-forewarned"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(SOURCES))
    ap.add_argument("--rule", default="union")
    ap.add_argument("--entity-type", default="PERSON")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--a4-candidates", type=int, default=10)
    ap.add_argument("--a4-limit", type=int, default=200)
    ap.add_argument("--a4-model", default="gpt-oss-120b")
    ap.add_argument("--mode", choices=("mask", "forewarned"), default="mask",
                    help="mask = neutralise name-like spans with a public list; "
                         "forewarned = leave the text alone and tell the ranker the scheme")
    ap.add_argument("--config", type=Path, default=Path("config/llm_api.toml"))
    ap.add_argument("--out", type=Path, default=Path("results/leakage"))
    args = ap.parse_args()

    documents = list(iter_documents(SOURCES[args.corpus][0]()))
    corpus = Corpus(args.corpus, tuple(documents))
    root = SOURCES[args.corpus][1]()
    found = sorted(root.glob(f"{args.corpus}_B_{args.rule}*.patch.jsonl"))
    if not found:
        log(f"no condition-B patch set for rule {args.rule!r} — STOPPED")
        return 1
    patchset = read_patchset(found[0])
    check = check_current(documents, patchset)
    log(f"{args.corpus}: {len(documents)} documents, {found[0].name}, "
        f"digests verified ({check['patches']} patches)")

    result = to_pseudonymised_corpus(documents, patchset)
    items = build_items(result, corpus, entity_type=args.entity_type,
                        n_candidates=args.a4_candidates, seed=args.seed, with_context=False)
    if args.a4_limit:
        items = items[: args.a4_limit]
    if not items:
        log("no queries — STOPPED")
        return 1

    if args.mode == "mask":
        names = public_name_tokens()
        log(f"  public name list: {len(names):,} tokens")
        rewritten, masked = [], 0
        for item in items:
            new, count = rewrite(item, names)
            rewritten.append(new)
            masked += count
        per_document = masked / len(items)
        log(f"  {len(items)} queries, {per_document:.1f} spans neutralised per document")
        ranker = LlmCandidateRanker(model=args.a4_model, config_path=str(args.config))
    else:
        rewritten, per_document = list(items), 0.0
        log(f"  {len(items)} queries, text unchanged; the ranker is told the scheme")
        ranker = ForewarnedRanker(model=args.a4_model, config_path=str(args.config))

    condition = f"B-{args.mode}"
    report = score_candidates(rewritten, ranker, condition=condition)
    o = report.overall
    log(f"  A4/{condition}: Rank-1 {o.rank1:.3f} Rank-5 {o.rank5:.3f} "
        f"mAP {o.mean_average_precision:.3f} over {len(rewritten)} queries")

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"{args.corpus}_{args.rule}_{args.entity_type}_informed_{args.mode}.jsonl"
    row = report.to_record() | {
        "corpus": args.corpus, "rule": args.rule, "condition": condition,
        "entity_type": args.entity_type, "seed": args.seed, "model": args.a4_model,
        "queries": len(rewritten), "spans_neutralised_per_document": per_document,
        "adversary": ("public name list over the released text, replaced spans unknown"
                      if args.mode == "mask" else
                      "told the release is pseudonymised; the text itself is unchanged"),
    }
    destination.write_text(json.dumps(row) + "\n", encoding="utf-8")
    log(f"wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
