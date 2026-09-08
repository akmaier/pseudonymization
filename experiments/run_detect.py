#!/usr/bin/env python3
"""Run the LLM detector pool over corpora, writing through the resumable cache.

This is the only slow step in the study.  It writes once; every ensemble afterwards is a post-hoc
read of the cache, so the hybrid-versus-LLMs-only sweep costs no model calls at all.

Safe to kill and restart: documents already recorded are skipped, and a document that errored is
retried rather than frozen into the results.

    python experiments/run_detect.py --corpora tab enron codealltag --models gpt-oss-120b ...
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from pseudonymkit.adapters import cardiode, codealltag, enron, ontonotes, tab
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.detectors.llm import PROMPT_VERSION, LlmDetector
from pseudonymkit.domain import Corpus, Document
from pseudonymkit.sampling import sample

CORPORA = "/cluster/shared_dataset/pseudonymization-corpora"

# DeepSeek is excluded: the gateway backend is down (AM, 2026-09-08), and both DeepSeek ids
# returned HTTP 500 "cannot connect to host" on the 2026-09-06 capability probe.
DEFAULT_MODELS = (
    "gpt-oss-120b",
    "Qwen/Qwen3.6-35B-A3B-FP8",
    "RedHatAI/gemma-4-31B-it-FP8-block",
)


ONTONOTES_EXTRACT = "/cluster/maier/pseudonymization/data/ontonotes"
CARDIODE_ROOT = "/cluster/maier/dua-restricted/cardiode/corpus"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpora", nargs="+", default=["tab", "codealltag", "enron"])
    ap.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--config", type=Path, default=Path("config/llm_api.toml"))
    ap.add_argument("--limit", type=int, default=0, help="cap per corpus; 0 = all")
    ap.add_argument("--enron-rate", type=float, default=0.004)
    ap.add_argument("--enron-limit", type=int, default=600)
    ap.add_argument("--codealltag-limit", type=int, default=800)
    args = ap.parse_args()

    started = time.time()

    def log(msg: str) -> None:
        print(f"[{time.time() - started:7.1f}s] {msg}", flush=True)

    root = Path(CORPORA)
    sources: dict[str, Corpus] = {}
    if "tab" in args.corpora:
        sources["tab"] = tab.load(root / "tab", types=["PERSON", "LOC", "ORG", "DATETIME"])
        log(f"tab: {len(sources['tab'])} documents")
    if "codealltag" in args.corpora:
        sources["codealltag"] = codealltag.load(root / "codealltag", limit=args.codealltag_limit)
        log(f"codealltag: {len(sources['codealltag'])} documents")
    for language in ("english", "chinese", "arabic"):
        key = f"ontonotes-{language[:2]}"
        if key in args.corpora:
            report: dict = {}
            sources[key] = ontonotes.load(
                ONTONOTES_EXTRACT, languages=(language,), report=report)
            log(f"{key}: {len(sources[key])} documents — {report.get(language)}")
    if "cardiode" in args.corpora:
        report = {}
        sources["cardiode"] = cardiode.load(CARDIODE_ROOT, report=report, progress=log)
        log(f"cardiode: {len(sources['cardiode'])} documents — {report}")
    if "enron" in args.corpora:
        full = enron.load(root / "enron" / "enron_mail_20150507.tar.gz",
                          limit=6000, stride=40, progress=log)
        # Stratified: every mailbox stays represented, which is the fair scheme for detection.
        sources["enron"] = Corpus("enron", tuple(
            sample(full, "stratified", 0.5, seed=0).documents[: args.enron_limit]))
        log(f"enron: {len(sources['enron'])} documents ({sources['enron'].name})")

    for corpus_name, corpus in sources.items():
        cap = {"enron": args.enron_limit, "codealltag": args.codealltag_limit}.get(
            corpus_name, args.limit or len(corpus))
        docs = list(corpus.documents)[:cap]
        cache = DetectorCache(args.cache, corpus_name)
        for model in args.models:
            detector = LlmDetector(model, config_path=args.config)
            done = cache.done(detector.name)
            todo = [d for d in docs if d.doc_id not in done]
            log(f"{corpus_name} / {model}: {len(done)} cached, {len(todo)} to do")
            for i, doc in enumerate(todo, 1):
                t0 = time.time()
                try:
                    out = detector.detect(doc)
                    cache.append(detector.name, doc.doc_id, out.spans, model=model,
                                 prompt_version=PROMPT_VERSION, elapsed=time.time() - t0)
                except Exception as exc:                       # recorded, retried on the next run
                    cache.append(detector.name, doc.doc_id, (), model=model,
                                 prompt_version=PROMPT_VERSION, error=f"{type(exc).__name__}: {exc}",
                                 elapsed=time.time() - t0)
                if i % 25 == 0 or i == len(todo):
                    log(f"  {corpus_name} / {model}: {i}/{len(todo)}")
        log(f"{corpus_name} cache: {cache.stats()}")

    log("done")


if __name__ == "__main__":
    main()
