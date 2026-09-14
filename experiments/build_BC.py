#!/usr/bin/env python3
"""Build conditions B and C from condition A, as patches, for one corpus.

One invocation = one cell of ``experiment_plan.md`` §7: one corpus, one detector set, one
combination rule, and **both** conditions from the same span set. B and C are one axis level apart,
so driving them from different spans would confound the condition with detector coverage; that is
why this script emits both and there is no way to ask it for only one half of a pair.

Detection is never run here. It is read from the cache written by ``detect_gateway.py`` (and by the
local-model runners), so **any detector subset and any rule is re-derivable with no model calls** —
which is what makes the hybrid-versus-LLMs-only sweep of H5 affordable at all.

    # list what the cache actually holds for a corpus
    python experiments/build_BC.py --corpus tab --list

    # one cell
    python experiments/build_BC.py --corpus tab --detectors llm:gpt-oss-120b llm:Qwen/... \
        --rule union --key-file ~/.config/pseudonymkit/hmac.key --out results/conditions

    # the perfect-detection ceiling: gold is just another detector (§7, axis D)
    python experiments/build_BC.py --corpus tab --detectors gold --rule union ...

**The key never enters the repo, a log or a result** (§4). Only its id — a digest prefix — is
recorded with the patch set. ``--make-key`` writes a fresh 32-byte key at mode 600 and prints only
its id; losing it means every B built with it becomes unreproducible, so keep it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path

from pseudonymkit.conditions import POOLED
from pseudonymkit.construction import construct, detected_documents, write_patchset
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.gazetteers import (
    build_inventory,
    load_census_surnames,
    load_geonames_cities,
    load_given_names,
)
from pseudonymkit.gazetteers_intl import (
    build_arabic_inventory,
    build_chinese_inventory,
    build_attested_inventory,
    build_german_inventory,
    merge_inventories,
)
from pseudonymkit.serialisation import iter_documents

CONDITION_A = Path("data/conditionA")
CARDIODE_A = Path("/cluster/maier/dua-restricted/cardiode/A/cardiode_A.jsonl.gz")
GAZETTEERS = Path("/cluster/shared_dataset/pseudonymization-corpora/gazetteers")
SUBLISTS = Path("data/codealltag_sublists")
CHINESE = Path("data/gazetteers/chinese_names")

SOURCES = {
    "tab": CONDITION_A / "tab_A.jsonl.gz",
    "ontonotes": CONDITION_A / "ontonotes_A.jsonl.gz",
    "enron": CONDITION_A / "enron_A.jsonl.gz",
    "cardiode": CARDIODE_A,
}


def log(message: str, started: float = time.time()) -> None:
    print(f"[{time.time() - started:7.1f}s] {message}", flush=True)


def key_id(key: bytes) -> str:
    """A stable, non-invertible name for a key. Twelve hex characters names it; it does not leak it."""
    return hashlib.sha256(key).hexdigest()[:12]


def make_key(path: Path) -> bytes:
    if path.exists():
        raise SystemExit(f"refusing to overwrite an existing key: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    path.write_bytes(key)
    os.chmod(path, 0o600)
    return key


def read_key(path: Path) -> bytes:
    if not path.exists():
        raise SystemExit(
            f"no key at {path}. Create one with --make-key, and keep it: every B built with a key "
            "is reproducible only while that key survives."
        )
    if path.stat().st_mode & 0o077:
        raise SystemExit(f"key file {path} is group- or world-readable; chmod 600 it first")
    key = path.read_bytes()
    if len(key) < 16:
        raise SystemExit(f"key at {path} is {len(key)} bytes; want at least 16")
    return key


def inventory_for(languages: set[str], documents=None):
    """One inventory covering every language the corpus actually contains.

    §14's three gazetteers are English only, so a corpus in another language needs its own pool
    (:mod:`pseudonymkit.gazetteers_intl`).  An uncovered language raises from the inventory rather
    than falling back — §12.2's defect was a silent English fallback that would have given 1,911
    Chinese and 446 Arabic documents English surrogates.
    """
    parts, notes = [], {}
    if "en" in languages:
        parts.append(build_inventory(
            surnames=load_census_surnames(GAZETTEERS / "Names_2010Census.csv"),
            given_names=load_given_names(GAZETTEERS / "name_gender_dataset.csv"),
            cities=load_geonames_cities(GAZETTEERS / "cities15000.txt"),
            language="en",
        ))
        notes["en"] = "US Census surnames + UCI given names + GeoNames cities (§14)"
    if "de" in languages:
        parts.append(build_german_inventory(SUBLISTS))
        notes["de"] = f"CodEAlltag substitute lists at {SUBLISTS} — unweighted by construction"
    if "zh" in languages:
        if not CHINESE.exists():
            raise SystemExit(
                f"no Chinese names at {CHINESE}. Fetch them first (CC BY-NC-SA, fetch never "
                "vendor):\n"
                "  python -c \"from pseudonymkit.gazetteers_intl import fetch_chinese_names as f; "
                f"f('{CHINESE}')\""
            )
        parts.append(build_chinese_inventory(CHINESE))
        notes["zh"] = "ChineseNames, 2008 NCIIC extract — true population counts"
    if "ar" in languages:
        if documents is None:
            raise SystemExit("the Arabic pool is built from the corpus's own attested name parts")
        inventory, report = build_arabic_inventory(documents)
        parts.append(inventory)
        notes["ar"] = f"recombined from the corpus's own diacritised parts: {report}"
    if not parts:
        raise SystemExit(f"no inventory for {sorted(languages)}")
    gazetteer = merge_inventories(*parts)

    # §14's gazetteers do not cover every (type, language) the corpora contain: English ORG, Chinese
    # and Arabic LOC/ORG, and DEMOGRAPHIC in all four languages are absent — nine pools, ~129,000
    # mentions, and condition B raises on the first one it meets.  Whatever is still missing is
    # compiled from the corpus's own attested values (see
    # :func:`pseudonymkit.gazetteers_intl.attested_pool`), which is what this repo already does for
    # Arabic names and what i2b2 did for professions and hospital departments.
    missing = []
    for entity_type in POOLED:
        for language in sorted(languages):
            try:
                covered = gazetteer.size(entity_type, language) > 0
            except LookupError:
                covered = False
            if not covered:
                missing.append((entity_type, language))
    if not missing:
        notes["attested"] = "none needed — the gazetteers cover every type and language present"
        return gazetteer, notes
    if documents is None:
        notes["attested"] = f"NOT BUILT — {missing} need the corpus to compile a pool from"
        return gazetteer, notes
    compiled, reports = build_attested_inventory(documents, missing)
    notes["attested"] = f"compiled from the corpus's own attested values: {reports}"
    return merge_inventories(gazetteer, compiled), notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", choices=sorted(SOURCES),
                    help="required except for --make-key")
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--detectors", nargs="+", default=None,
                    help="detector ids, or 'gold'; default is everything the cache holds")
    ap.add_argument("--rule", default="union")
    ap.add_argument("--link", default="single", choices=["single", "iou"])
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--conditions", nargs="+", default=["B", "C"])
    ap.add_argument("--language", default=None, help="surrogate pool language; default per corpus")
    ap.add_argument("--require-all", action="store_true",
                    help="skip a document unless every named detector has a record for it")
    ap.add_argument("--keep-truncated", action="store_true",
                    help="believe truncated LLM responses — they are runaways, so do not")
    ap.add_argument("--out", type=Path, default=Path("results/conditions"))
    ap.add_argument("--key-file", type=Path,
                    default=Path.home() / ".config" / "pseudonymkit" / "hmac.key")
    ap.add_argument("--make-key", action="store_true")
    ap.add_argument("--list", action="store_true", help="show what the cache holds, then stop")
    args = ap.parse_args()

    if args.make_key:
        # Before the --corpus check: making a key has nothing to do with a corpus.
        key = make_key(args.key_file)
        log(f"wrote a new key to {args.key_file} (mode 600), id {key_id(key)}")
        return 0

    if not args.corpus:
        ap.error("--corpus is required (except with --make-key)")

    cache = DetectorCache(args.cache, args.corpus)
    held = cache.stats()
    if args.list:
        print(f"{args.corpus}: cache at {cache.root}")
        for detector, counts in sorted(held.items()):
            print(f"  {detector:<58} {counts}")
        if not held:
            print("  (nothing cached — run experiments/detect_gateway.py first)")
        return 0

    source = SOURCES[args.corpus]
    if not source.exists():
        raise SystemExit(f"no condition A for {args.corpus} at {source}; run build_A.py first")
    log(f"reading condition A: {source}")
    documents = list(iter_documents(source))
    log(f"  {len(documents)} documents")

    detectors = args.detectors or sorted(held)
    if not detectors:
        raise SystemExit(f"no detectors given and nothing cached for {args.corpus}")
    log(f"detectors ({len(detectors)}): {', '.join(detectors)}")

    detected, summary = detected_documents(
        documents, cache, detectors, args.rule,
        rule_kwargs={"link": args.link, "iou": args.iou},
        drop_truncated=not args.keep_truncated,
        require_all=args.require_all,
    )
    log(f"combined: {summary}")
    if not detected:
        raise SystemExit("no document survived the detector pool — nothing to construct")

    # Every language the corpus actually contains — OntoNotes is three.
    languages = ({args.language} if args.language
                 else {d.language for d in detected if d.language})
    needs_inventory = any(c.upper() == "B" for c in args.conditions)
    key = read_key(args.key_file)
    inventory = notes = None
    if needs_inventory:
        inventory, notes = inventory_for(languages, documents=detected)
        for language, note in sorted(notes.items()):
            log(f"  inventory [{language}]: {note}")
    log(f"key id {key_id(key)}, languages {sorted(languages)}")

    patchsets = construct(
        detected, args.corpus, args.conditions,
        inventory=inventory, key=key, key_id=key_id(key),
        provenance={
            "source": str(source),
            "languages": sorted(languages),
            "inventories": notes or {},
            "detectors": list(detectors),
            **{k: v for k, v in summary.items() if k != "detectors"},
        },
    )

    # CARDIO:DE's derived artefacts never leave the restricted tree (CLAUDE.md §3).
    out = args.out
    if args.corpus == "cardiode":
        out = Path("/cluster/maier/dua-restricted/cardiode/conditions")
        if "shared" in str(args.out):
            log(f"  redirecting CARDIO:DE output away from {args.out} to {out}")
    out.mkdir(parents=True, exist_ok=True)

    tag = f"{args.rule}-{args.link}{args.iou:g}-{len(detectors)}det"
    written = {}
    for condition, patchset in patchsets.items():
        path = out / f"{args.corpus}_{condition}_{tag}.patch.jsonl"
        write_patchset(patchset, path)
        size = path.stat().st_size
        written[condition] = {
            "path": str(path),
            "documents": len(patchset),
            "replacements": patchset.replacements,
            "bytes": size,
        }
        log(f"  {condition}: {len(patchset)} documents, {patchset.replacements} replacements, "
            f"{size / 1e6:.1f} MB -> {path.name}")

    manifest = out / f"{args.corpus}_{tag}.manifest.json"
    manifest.write_text(json.dumps({
        "corpus": args.corpus, "tag": tag, "combined": summary,
        "key_id": key_id(key), "conditions": written,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"manifest: {manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
