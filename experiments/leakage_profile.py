"""How often an identifier survives — per document, per case, and per entity.

"Sensitivity 0.985" is a token rate over a whole corpus, and it is the least informative way to state
what a pseudonymisation run left behind.  Three other denominators matter more, and they disagree:

**per entity**   An entity is *protected* only when **every** one of its mentions was caught.  One
                 missed occurrence of a name puts that person back in the clear however many other
                 mentions were replaced, so entity exposure is always worse than token recall and
                 sometimes far worse.

**per document** A released document either does or does not still contain an identifier.  This is
                 what a reviewer checks and what a data-protection officer asks about, and a corpus
                 rate of 1.5 % can still mean most documents carry something.

**per case**     Where the corpus has cross-document identity — CARDIO:DE's patients (§12.1),
                 Enron's mailbox owners — a *case* is the person, not the file.  A case is exposed if
                 **any** of its documents leaks any of its identifiers, so the rate compounds over a
                 patient's letters.  TAB and OntoNotes have no cross-document identity (§8.2), so a
                 case is a document there and the column is reported as such rather than faked.

The sweep aggregates all of this away, so it is recomputed here for the chosen operating points only.

    python experiments/leakage_profile.py --corpus cardiode
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_detection import CORPORA, combine, load_pool  # noqa: E402

from pseudonymkit.conditions import CONSTRUCTED, POOLED, UNCHANGED  # noqa: E402
from pseudonymkit.detectors.cache import DetectorCache  # noqa: E402
from pseudonymkit.metrics.detection import covered_tokens, tokenise  # noqa: E402
from pseudonymkit.paths import work_dir  # noqa: E402
from pseudonymkit.serialisation import iter_documents  # noqa: E402


REPLACED = frozenset(POOLED) | frozenset(CONSTRUCTED)
"""The types condition B actually replaces, and therefore the only ones that can *leak*.

``UNCHANGED`` — DATETIME, QUANTITY, MISC — is passed through by design (AM, 2026-09-13), and on
CARDIO:DE that is **84.7 % of the gold tokens**: 102,233 of 120,701 are dates. Counting them as
exposure measures a decision, not a failure, and the first version of this driver did exactly that —
reporting 94.8 % of patients "exposed" when most of what it found was dates the pipeline was never
asked to touch. Exposure is therefore scored over REPLACED, with the retained types reported
separately so the choice stays visible rather than silently excluded."""

PATIENT_ROLES = frozenset({"patient", "patient_body"})
"""CARDIO:DE marks who a PERSON mention is: `patient` and `patient_body` against `signature` and
`referring` for the physicians. The patient is the case."""


def case_of(document, corpus: str) -> tuple[str, bool]:
    """``(case id, is a real case)`` for one document.

    Enron supplies the mailbox owner in ``subject_id``. CARDIO:DE does not use ``subject_id`` at all
    — §12.1's constructed identity lives in the co-reference chain — so the case is the gold entity
    of the PERSON mention the corpus marks as the patient. TAB and OntoNotes have no cross-document
    identity (§8.2), so a case is a document and the caller is told so rather than shown a number
    that pretends otherwise.
    """
    if corpus == "cardiode":
        for mention in document.mentions:
            if mention.type == "PERSON" and (mention.attributes or {}).get("role") in PATIENT_ROLES:
                if mention.gold_entity_id:
                    return mention.gold_entity_id, True
        return document.doc_id, False
    if document.subject_id:
        return document.subject_id, True
    return document.doc_id, False


def profile(documents, spans_by_doc, corpus: str, types: frozenset[str]) -> dict:
    """Exposure at three denominators, over one set of entity types."""
    per_doc_tokens: list[int] = []
    per_doc_findings: list[int] = []
    docs_exposed = 0
    entities_total = entities_exposed = 0
    per_type_missed: dict[str, int] = defaultdict(int)
    per_type_gold: dict[str, int] = defaultdict(int)
    per_class_missed: dict[str, int] = defaultdict(int)
    per_class_gold: dict[str, int] = defaultdict(int)
    case_leaks: dict[str, int] = defaultdict(int)
    cases_seen: set[str] = set()
    corpus_cases = True

    for document in documents:
        case, real = case_of(document, corpus)
        if not real:
            corpus_cases = False
        cases_seen.add(case)

        tokens = list(tokenise(document.text))
        caught = covered_tokens(tokens, spans_by_doc.get(document.doc_id, ()))
        gold_by_entity: dict[str, set[int]] = defaultdict(set)
        gold_all: set[int] = set()
        survivors = 0
        for mention in document.mentions:
            if mention.type not in types:
                continue
            indices = covered_tokens(tokens, (mention.span,))
            gold_all |= indices
            # A *finding*: one mention of which at least one token survives. Partial coverage still
            # counts — "Anna Müller" with only "Anna" replaced leaves a surname in the clear, and an
            # attacker reads what is there, not what the scorer intended.
            if indices - caught:
                survivors += 1
            gold_by_entity[mention.gold_entity_id or mention.mention_id] |= indices
            per_type_gold[mention.type] += len(indices)
            per_type_missed[mention.type] += len(indices - caught)
            cls = (mention.attributes or {}).get("identifier_class")
            if cls:
                per_class_gold[cls] += len(indices)
                per_class_missed[cls] += len(indices - caught)

        missed = gold_all - caught
        per_doc_findings.append(survivors)
        per_doc_tokens.append(len(missed))
        if missed:
            docs_exposed += 1
            case_leaks[case] += len(missed)
        for indices in gold_by_entity.values():
            if not indices:
                continue
            entities_total += 1
            if indices - caught:
                entities_exposed += 1

    documents_n = max(len(documents), 1)
    cases_n = max(len(cases_seen), 1)

    # **The shape, not just the rate.** A document with one surviving name and a document with twenty
    # present an attacker with different problems: one is a single guess against the corpus-wide
    # candidate pool, the other is a cross-referenced profile. A single "% of documents exposed"
    # hides that difference completely, and it is the difference the attack results turn on.
    buckets = {"0": 0, "1": 0, "2": 0, "3-5": 0, "6-10": 0, "11+": 0}
    for n in per_doc_findings:
        key = ("0" if n == 0 else "1" if n == 1 else "2" if n == 2
               else "3-5" if n <= 5 else "6-10" if n <= 10 else "11+")
        buckets[key] += 1
    return {
        "findings_per_document": {k: {"documents": v, "rate": v / documents_n}
                                  for k, v in buckets.items()},
        "findings_total": sum(per_doc_findings),
        "findings_per_document_mean": statistics.fmean(per_doc_findings) if per_doc_findings else 0.0,
        "findings_per_document_median": (statistics.median(per_doc_findings)
                                         if per_doc_findings else 0.0),
        "types_scored": sorted(types),
        "documents": len(documents),
        "tokens_gold": sum(per_type_gold.values()),
        "tokens_leaked": sum(per_doc_tokens),
        "tokens_per_document_mean": statistics.fmean(per_doc_tokens) if per_doc_tokens else 0.0,
        "tokens_per_document_median": statistics.median(per_doc_tokens) if per_doc_tokens else 0.0,
        "documents_exposed": docs_exposed,
        "documents_exposed_rate": docs_exposed / documents_n,
        "entities": entities_total,
        "entities_exposed": entities_exposed,
        "entities_exposed_rate": entities_exposed / max(entities_total, 1),
        "cases": len(cases_seen),
        "cases_are_documents": not corpus_cases,
        "cases_exposed": len(case_leaks),
        "cases_exposed_rate": len(case_leaks) / cases_n,
        "tokens_per_case_mean": (sum(case_leaks.values()) / cases_n) if cases_n else 0.0,
        "per_type": {t: {"gold": per_type_gold[t], "leaked": per_type_missed[t],
                         "rate": per_type_missed[t] / max(per_type_gold[t], 1)}
                     for t in sorted(per_type_gold)},
        "per_identifier_class": {c: {"gold": per_class_gold[c], "leaked": per_class_missed[c],
                                     "rate": per_class_missed[c] / max(per_class_gold[c], 1)}
                                 for c in sorted(per_class_gold)},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(CORPORA))
    ap.add_argument("--points", type=Path, default=None)
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    points_path = args.points or (work_dir() / "results" / "detection"
                                  / f"{args.corpus}_operating_points.json")
    chosen = json.loads(points_path.read_text(encoding="utf-8"))["points"]

    documents = list(iter_documents(CORPORA[args.corpus]()))
    texts = {d.doc_id: d.text for d in documents}
    pool = load_pool(DetectorCache(args.cache, args.corpus), args.corpus, texts)
    print(f"=== {args.corpus}: {len(documents)} documents ===\n")

    out = {}
    for name, point in chosen.items():
        rule = point["rule"]
        kwargs = {"k": 2} if rule == "vote" else {}
        names = tuple(point["ensemble"])
        spans = (pool[names[0]] if len(names) == 1
                 else combine(pool, names, rule if rule != "single" else "union", kwargs, texts))
        got = profile(documents, spans, args.corpus, REPLACED)
        person = profile(documents, spans, args.corpus, frozenset({"PERSON"}))
        retained = profile(documents, spans, args.corpus, frozenset(UNCHANGED))
        out[name] = {"ensemble": list(names), "rule": rule,
                     "sensitivity": point["sensitivity"], "specificity": point["specificity"],
                     "replaced_types": got, "person_only": person, "retained_types": retained}
        unit = "documents (no cross-document identity)" if got["cases_are_documents"] else "cases"
        print(f"{name}  (sensitivity {point['sensitivity']:.3f})")
        print(f"  over the types condition B replaces ({got['tokens_gold']:,} gold tokens)")
        fpd = got["findings_per_document"]
        print(f"    documents with >=1 finding left : {got['documents_exposed']:,}"
              f"/{got['documents']:,} ({got['documents_exposed_rate']:.1%})")
        print(f"    findings per document           : " + "  ".join(
            f"{k}: {v['rate']:.1%}" for k, v in fpd.items())
            + f"   (mean {got['findings_per_document_mean']:.2f}, "
              f"median {got['findings_per_document_median']:.0f})")
        print(f"    tokens left per document        : "
              f"{got['tokens_per_document_mean']:.2f} "
              f"(median {got['tokens_per_document_median']:.0f})")
        print(f"    per case     : {got['cases_exposed']:,}/{got['cases']:,} {unit} "
              f"({got['cases_exposed_rate']:.1%}), {got['tokens_per_case_mean']:.2f} tokens each")
        print(f"    per entity   : {got['entities_exposed']:,}/{got['entities']:,} "
              f"({got['entities_exposed_rate']:.1%}) keep a mention in the clear")
        print(f"    by type      : " + ", ".join(
            f"{t} {v['leaked']:,}/{v['gold']:,} ({v['rate']:.1%})"
            for t, v in got["per_type"].items()))
        if got["per_identifier_class"]:
            print(f"    by class     : " + ", ".join(
                f"{c} {v['leaked']:,}/{v['gold']:,} ({v['rate']:.1%})"
                for c, v in got["per_identifier_class"].items()))
        print(f"  PERSON only    : {person['cases_exposed']:,}/{person['cases']:,} {unit} "
              f"({person['cases_exposed_rate']:.1%}), "
              f"{person['entities_exposed']:,}/{person['entities']:,} entities "
              f"({person['entities_exposed_rate']:.1%})")
        print(f"  retained by design ({', '.join(sorted(UNCHANGED))}): "
              f"{retained['tokens_gold']:,} gold tokens, never replaced\n")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        dest = args.out / f"{args.corpus}_leakage_profile.json"
        dest.write_text(json.dumps({"corpus": args.corpus, "points": out}, indent=2),
                        encoding="utf-8")
        print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
