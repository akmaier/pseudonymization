#!/usr/bin/env python3
"""Build condition A — the full-data text — for every corpus in ``experiment_plan.md`` §11.

Condition A is *"the text as the corpus ships it"* (§7).  For three of the four corpora that is
literally true and this script only reads, checks and serialises them.

**CodEAlltag is not here, and that is deliberate.**  It was built on 2026-09-10 and withdrawn on
2026-09-11: the release ships no gold spans, so nothing measured on it is attributable to a method
(§11).  The adapter stays; the corpus is not a member of this study.  CARDIO:DE is the exception:
it was de-identified before release and its identifiers are IOB tag tokens in the running text, so
its condition-A letter has to be built.  :mod:`pseudonymkit.adapters.cardiode_fill` does that and
writes the run → entity map beside it; the map is the gold, because after the fill we know where
every identifier is and who it refers to.

Every corpus is checked the same way before it is written, and the checks are reported rather than
asserted away:

1. **document count**, against what §11 records;
2. **offset integrity** over *every* mention — ``text[span.start:span.end] == span.text``, not a
   sample, because an offset defect is silent and poisons detection scoring downstream;
3. **gold layers** — which documents carry co-reference, mentions per harmonised type;
4. **round trip** — the file is read back and the counts must match what went in.

Usage::

    python experiments/build_A.py --all --out /cluster/maier/pseudonymization/data/conditionA
    python experiments/build_A.py --corpus cardiode --out /cluster/maier/dua-restricted/cardiode/A

**CARDIO:DE never goes to a shared directory.**  The script refuses to write it under
``/cluster/shared_dataset`` — the DUA is single-user (``CLAUDE.md`` §3) and a path slip would breach
it silently.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from pseudonymkit.detokenise import unescape_corpus
from pseudonymkit.domain import Corpus, Document
from pseudonymkit.serialisation import read_corpus, write_corpus

CORPORA = Path("/cluster/shared_dataset/pseudonymization-corpora")
ONTONOTES = Path("/cluster/maier/pseudonymization/data/ontonotes")
CARDIODE = Path("/cluster/maier/dua-restricted/cardiode")
SUBLISTS = Path("/cluster/maier/pseudonymization/data/codealltag_sublists")

EXPECTED = {"tab": 1268, "ontonotes": None, "cardiode": 500, "enron": None}
"""Document counts §11 records.  ``None`` where the count depends on the sampling scheme."""


def log(message: str, started: float = time.time()) -> None:
    print(f"[{time.time() - started:7.1f}s] {message}", flush=True)


def check(corpus: Corpus, name: str) -> dict:
    """Offset integrity over every mention, plus what gold layers came through."""
    bad = 0
    types: Counter[str] = Counter()
    with_coref = 0
    mentions = 0
    for document in corpus.documents:
        chained = False
        for mention in document.mentions:
            mentions += 1
            types[mention.span.type] += 1
            if document.text[mention.span.start : mention.span.end] != mention.span.text:
                bad += 1
            chained = chained or mention.gold_entity_id is not None
        with_coref += chained
    summary = {
        "corpus": name,
        "documents": len(corpus),
        "mentions": mentions,
        "characters": sum(len(d.text) for d in corpus.documents),
        "offset_errors": bad,
        "documents_with_coreference": with_coref,
        "mentions_by_type": dict(types.most_common()),
        "languages": sorted(corpus.languages),
    }
    log(
        f"{name}: {len(corpus)} documents, {mentions} mentions, {bad} offset errors, "
        f"{with_coref} with co-reference"
    )
    if bad:
        log(f"  !! {bad} mentions do not match their own offsets — NOT written")
    return summary


def emit(corpus: Corpus, out: Path, name: str, summary: dict) -> dict:
    """Write, read back, and confirm the round trip carried everything."""
    if summary["offset_errors"]:
        summary["written"] = False
        return summary
    if name == "cardiode" and "shared" in str(out):
        raise SystemExit(f"refusing to write CARDIO:DE under a shared path: {out}")
    path = out / f"{name}_A.jsonl.gz"
    written = write_corpus(corpus, path)
    back = read_corpus(path)
    round_trip = (
        len(back) == len(corpus)
        and sum(len(d.mentions) for d in back) == summary["mentions"]
        and back.name == corpus.name
    )
    summary.update(
        written=True,
        path=str(path),
        bytes=path.stat().st_size,
        documents_written=written,
        round_trip_exact=round_trip,
    )
    log(f"  wrote {written} documents to {path} ({path.stat().st_size / 1e6:.0f} MB), "
        f"round trip {'exact' if round_trip else 'MISMATCH'}")
    return summary


# --------------------------------------------------------------------------------------------
# the corpora that ship a condition-A text


def build_tab(out: Path) -> dict:
    from pseudonymkit.adapters import tab

    log("TAB — reading the released annotation as it ships")
    corpus = tab.load(CORPORA / "tab")
    corpus = Corpus("tab[A]", tuple(_stamp(d, "real") for d in corpus.documents))
    return emit(corpus, out, "tab", check(corpus, "tab"))


def build_ontonotes(out: Path) -> dict:
    from pseudonymkit.adapters import ontonotes

    log("OntoNotes — reading en/zh/ar as they ship")
    report: dict = {}
    corpus = ontonotes.load(ONTONOTES, report=report)
    # OntoNotes is Penn-Treebank tokenised and ships its brackets escaped — 3,792 `-LRB-`, 3,813
    # `-RRB-`, 924 `-AMP-`, 188 `-RCB-`. No model in the study met those in training, so they are a
    # systematic distortion of the input rather than a blemish. Offsets move with the text.
    unescape: dict = {}
    corpus = unescape_corpus(corpus.documents, "ontonotes[A]", report=unescape)
    log(f"  PTB escapes: {unescape}")
    corpus = Corpus("ontonotes[A]", tuple(_stamp(d, "real") for d in corpus.documents))
    summary = check(corpus, "ontonotes")
    summary["ptb_unescaped"] = unescape
    summary["per_language"] = {
        language: sum(1 for d in corpus.documents if d.language == language)
        for language in sorted(corpus.languages)
    }
    summary["load_report"] = {k: str(v) for k, v in report.items()}
    log(f"  per language: {summary['per_language']}")
    return emit(corpus, out, "ontonotes", summary)


def build_enron(out: Path, source: Path | None) -> dict:
    """Enron's condition A was built on 2026-09-10 (66,432 documents, 887,800 mentions).

    Rebuilding needs the 443 MB tarball and a machine that can hold the identity table, so this
    verifies the existing artefact by default and rebuilds only when the tarball is given.
    """
    if source is None:
        existing = sorted(out.glob("enron_A.jsonl.gz")) or sorted(
            Path("../pseudonymization-data").glob("enron_A.jsonl.gz")
        )
        if not existing:
            log("enron: no condition-A file found and no --enron-source given — SKIPPED")
            return {"corpus": "enron", "written": False, "reason": "no artefact, no source"}
        log(f"enron — verifying the existing artefact at {existing[0]}")
        corpus = read_corpus(existing[0])
        summary = check(corpus, "enron")
        summary.update(written=True, path=str(existing[0]), rebuilt=False)
        return summary
    raise SystemExit(
        "rebuilding Enron is experiments/build_enron.py — it needs the two-pass identity table"
    )


# --------------------------------------------------------------------------------------------
# the corpus whose condition-A text has to be built


def build_cardiode(out: Path, seed: int) -> dict:
    from pseudonymkit.adapters import cardiode
    from pseudonymkit.adapters.cardiode_fill import Inventories, fill_corpus

    log("CARDIO:DE — the tags are the identifiers; filling them")
    report: dict = {}
    corpus = cardiode.load(CARDIODE / "corpus", report=report)
    log(f"  loaded: {'; '.join(f'{k}: {v}' for k, v in report.items())}")

    inventories = Inventories.from_sublists(SUBLISTS, country="DE")
    log(f"  inventory: {len(inventories.family)} surnames, "
        f"{len(inventories.male)}/{len(inventories.female)} given names, "
        f"{len(inventories.city)} cities, {len(inventories.street)} streets")

    documents, mapping, fill = fill_corpus(corpus.documents, inventories, seed=seed)
    log(f"  {fill}")

    filled = Corpus(f"cardiode[A#{seed}]", tuple(documents))
    summary = check(filled, "cardiode")
    summary["fill"] = {
        "runs": fill.runs,
        "entities": fill.entities,
        "by_type": dict(fill.by_type or {}),
        "orphan_runs": fill.orphan_runs,
        "seed": seed,
    }
    summary["roles"] = dict(Counter(e.role for e in mapping).most_common())
    log(f"  roles: {summary['roles']}")

    summary = emit(filled, out, "cardiode", summary)
    if summary.get("written"):
        map_path = out / f"cardiode_A_map_seed{seed}.jsonl"
        with map_path.open("w", encoding="utf-8") as handle:
            for entity in mapping:
                handle.write(json.dumps({
                    "start": entity.start,
                    "end": entity.end,
                    "type": entity.type,
                    "surface": entity.surface,
                    "entity_id": entity.entity_id,
                    "role": entity.role,
                    "tag": entity.run.text,
                    "tag_start": entity.run.start,
                    "tag_end": entity.run.end,
                }, ensure_ascii=False) + "\n")
        summary["map_path"] = str(map_path)
        log(f"  wrote the tag → entity map: {map_path} ({len(mapping)} rows)")
    return summary


def _stamp(document: Document, provenance: str) -> Document:
    from dataclasses import replace

    return replace(document, provenance=provenance) if document.provenance is None else document


# --------------------------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", nargs="+", default=[],
                    choices=["tab", "ontonotes", "cardiode", "enron"])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0, help="CARDIO:DE fill seed")
    ap.add_argument("--enron-source", type=Path, default=None)
    args = ap.parse_args()

    wanted = ["tab", "ontonotes", "cardiode", "enron"] if args.all else args.corpus
    if not wanted:
        ap.error("give --all or --corpus")
    args.out.mkdir(parents=True, exist_ok=True)

    summaries = []
    for name in wanted:
        try:
            if name == "tab":
                summaries.append(build_tab(args.out))
            elif name == "ontonotes":
                summaries.append(build_ontonotes(args.out))
            elif name == "cardiode":
                summaries.append(build_cardiode(args.out, args.seed))
            elif name == "enron":
                summaries.append(build_enron(args.out, args.enron_source))
        except Exception as error:                       # report, never substitute (§1)
            log(f"{name}: FAILED — {type(error).__name__}: {error}")
            summaries.append({"corpus": name, "written": False, "error": f"{type(error).__name__}: {error}"})


    # Merge by corpus, so building one corpus does not erase the record of the others.
    manifest = args.out / "conditionA_manifest.json"
    merged: dict[str, dict] = {}
    if manifest.exists():
        for entry in json.loads(manifest.read_text(encoding="utf-8")):
            merged[entry["corpus"]] = entry
    for entry in summaries:
        merged[entry["corpus"]] = entry
    manifest.write_text(
        json.dumps(list(merged.values()), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log(f"manifest: {manifest}")
    return 0 if all(s.get("written") for s in summaries) else 1


if __name__ == "__main__":
    sys.exit(main())
