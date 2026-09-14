#!/usr/bin/env python3
"""Axis D's non-gateway detectors, into the same cache the gateway writes.

``experiment_plan.md`` §7 axis D has seven levels besides the gateway pool, and §17.7 recorded them
as having no adapter. They do — ``PresidioDetector``, ``GlinerDetector``,
``TokenClassificationDetector``, ``PrivacyTagger``. What was missing is this: something that runs
them over condition A and writes to :class:`~pseudonymkit.detectors.cache.DetectorCache`, so their
spans join the gateway's in any ensemble with no special handling.

Two kinds of work, and they belong in different places:

* **``presidio``** is CPU — spaCy pipelines and recognisers. It runs on the head node beside the
  gateway pool, which is where all CPU work in this study runs (AM, 2026-09-12).
* **``gliner``, ``finetuned``, ``privacy_tagger``** are transformer inference. They want a GPU, and a
  GPU means a Slurm allocation — the one part of this pipeline that genuinely does. ``--device cpu``
  works and is only for smoke-testing; on Enron's 58,636 documents it is not a plan.

Everything else matches ``detect_gateway.py`` deliberately, because the two write the same records:
the same condition-A sources, the same corpus order with **Enron last**, the same ``text_sha256``
guard that refuses a record whose document has been rebuilt, and the same resume-by-cache.

    # CPU, head node — start now, no GPU needed
    python experiments/detect_local.py --detectors presidio

    # GPU, inside a Slurm allocation
    python experiments/detect_local.py --detectors gliner finetuned privacy_tagger --device cuda

    # fetch the five HuggingFace checkpoints first; they are not on the cluster
    python experiments/detect_local.py --download
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import replace as _replace
from pathlib import Path

from pseudonymkit.paths import cardiode_a_optional
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.detectors.domain import PrivacyTagger
from pseudonymkit.detectors.finetuned import FINETUNED_MODELS, TokenClassificationDetector
from pseudonymkit.detectors.rule import PresidioDetector
from pseudonymkit.detectors.runner import run_detector
from pseudonymkit.detectors.zeroshot import GLINER_MODELS, GlinerDetector
from pseudonymkit.domain import Document
from pseudonymkit.serialisation import iter_documents

CONDITION_A = Path("data/conditionA")
CARDIODE_A = cardiode_a_optional()
PRIVACY_TAGGER = Path("models/privacy_tagger.pt")

# Enron last, for the same reason as in detect_gateway: it is 58,636 of 66,298 documents, so running
# it first would park the three small corpora behind a multi-day job.
# CARDIO:DE is present only when PSEUDONYMKIT_DUA is configured. Absent, it is dropped from
# the table and reported at startup — the other three corpora still run (§1: report, do not
# substitute), and a reproducer without the DUA is not blocked from the whole study.
CORPORA: tuple[tuple[str, int, Path], ...] = tuple(e for e in (
    ("cardiode", 400, CARDIODE_A),
    ("tab", 1268, CONDITION_A / "tab_A.jsonl.gz"),
    ("ontonotes", 5994, CONDITION_A / "ontonotes_A.jsonl.gz"),
    ("enron", 58636, CONDITION_A / "enron_A.jsonl.gz"),
) if e[2] is not None)
HF_MODELS: tuple[str, ...] = GLINER_MODELS + FINETUNED_MODELS
"""The five checkpoints §14 fixes that are **not** on the cluster (measured 2026-09-12)."""


def log(message: str, started: float = time.time()) -> None:
    print(f"[{time.time() - started:8.1f}s] {message}", flush=True)


def stream_batches(path: Path, size: int, limit: int = 0):
    """Yield lists of at most ``size`` documents, gold mentions stripped.

    **The corpus is never held whole.** The head node has 7 GB of RAM shared between users, and
    materialising Enron's 58,636 documents beside three spaCy pipelines is what got Presidio
    SIGKILLed at 425/1268 and again SIGTERMed at 4,005/58,636 — silently both times, the log simply
    stopping mid-progress. Peak memory is now one batch, whatever the corpus.

    Re-reading the file once per detector costs a few seconds of gzip; holding it costs the job.
    """
    batch: list[Document] = []
    seen = 0
    for document in iter_documents(path):
        batch.append(_replace(document, mentions=()))
        seen += 1
        if limit and seen >= limit:
            break
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def build(kind: str, device: str, gliner_threshold: float) -> list:
    """The detector instances for one family.  Each is a separate level of axis D."""
    if kind == "presidio":
        return [PresidioDetector()]
    if kind == "gliner":
        return [
            GlinerDetector(model=model, threshold=gliner_threshold, device=device)
            for model in GLINER_MODELS
        ]
    if kind == "finetuned":
        return [
            TokenClassificationDetector(
                model=model, device=device, path=_converted_snapshot(model)
            )
            for model in FINETUNED_MODELS
        ]
    if kind == "privacy_tagger":
        if not PRIVACY_TAGGER.exists():
            raise SystemExit(
                f"privacy_tagger weights not at {PRIVACY_TAGGER}. They are 2.6 GB from a single "
                "university host with no mirror; see experiment_plan.md §14."
            )
        return [PrivacyTagger(model_path=PRIVACY_TAGGER)]
    raise SystemExit(f"unknown detector family {kind!r}")


def _converted_snapshot(model: str) -> str | None:
    """A local snapshot directory carrying a ``model.safetensors`` we converted ourselves, or None.

    ``transformers`` 4.57 refuses ``torch.load`` on a ``.bin`` under torch < 2.6 (CVE-2025-32434),
    and ``StanfordAIMI/stanford-deidentifier-base`` ships only a ``.bin``.  Upgrading torch would
    change the CUDA build that the Volta and Turing cards are currently working with, so the
    checkpoint is converted instead — but ``from_pretrained`` resolves against the *repo's* file
    list, which has no ``model.safetensors``, so it has to be pointed at the directory.
    """
    root = Path.home() / ".cache/huggingface/hub" / f"models--{model.replace('/', '--')}"
    if not root.is_dir():
        return None
    for snapshot in (root / "snapshots").iterdir():
        if (snapshot / "model.safetensors").exists() and not (
            snapshot / "model.safetensors"
        ).is_symlink():
            return str(snapshot)
    return None


def download() -> int:
    """Fetch the five HuggingFace checkpoints. Nothing else in this script touches the network."""
    from huggingface_hub import snapshot_download

    for model in HF_MODELS:
        log(f"downloading {model}")
        path = snapshot_download(model)
        size = sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())
        log(f"  {model}: {size / 1e9:.2f} GB at {path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--detectors", nargs="+",
                    default=["presidio"],
                    choices=["presidio", "gliner", "finetuned", "privacy_tagger"],
                    help="presidio is CPU; the rest want a GPU")
    ap.add_argument("--corpora", nargs="+",
                    default=[name for name, _, _ in CORPORA],
                    choices=[name for name, _, _ in CORPORA])
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--device", default="cpu",
                    help="'cpu' or 'cuda'; cpu is for smoke tests, not for Enron")
    ap.add_argument("--gliner-threshold", type=float, default=0.5)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="cap documents per corpus; 0 = all")
    ap.add_argument("--stream-batch", type=int, default=2000,
                    help="documents held in memory at once; the corpus is never held whole")
    ap.add_argument("--download", action="store_true",
                    help="fetch the HuggingFace checkpoints, then stop")
    args = ap.parse_args()

    if args.download:
        return download()

    if args.device.startswith("cuda"):
        import torch

        if not torch.cuda.is_available():
            # Say which of the two it is.  Inside an allocation that *has* a GPU, "the head node has
            # no GPU" sends the reader to the wrong problem — and that is the case that happened:
            # on a Pascal node the driver/library versions did not match and CUDA raised error 804,
            # "forward compatibility was attempted on non supported HW".
            allocated = os.environ.get("SLURM_JOB_ID")
            where = (f"inside Slurm job {allocated}" if allocated else "outside Slurm")
            raise SystemExit(
                f"--device cuda but torch.cuda.is_available() is False, {where}. "
                f"torch {torch.__version__} is built for CUDA {torch.version.cuda}. "
                "If this is an allocation that was granted a GPU, the node's driver does not match "
                "this wheel — try another GPU type (--gres=gpu:<type>:1) rather than assuming the "
                "wheel is wrong (experiment_plan.md §14, and the probe of 2026-09-12)."
            )
        log(f"cuda: {torch.cuda.get_device_name(0)}")

    assert CORPORA[-1][0] == "enron", "Enron must be processed last"
    log(f"detectors: {', '.join(args.detectors)}  device: {args.device}")

    failures = 0
    for name, expected, path in CORPORA:
        if name not in args.corpora:
            continue
        if not path.exists():
            log(f"{name}: no condition A at {path} — SKIPPED")
            failures += 1
            continue
        log(f"=== {name} (expected {expected}) ===")
        cache = DetectorCache(args.cache, name)

        for kind in args.detectors:
            for detector in build(kind, args.device, args.gliner_threshold):
                started = time.time()
                try:
                    detector.load()
                except Exception as exc:                       # report, never substitute (§1)
                    log(f"  {detector.name}: LOAD FAILED — {type(exc).__name__}: {exc}")
                    failures += 1
                    continue
                # One load, then the corpus streamed past it in batches.
                written = cached = failed = spans = seen = 0
                for batch in stream_batches(path, args.stream_batch, args.limit):
                    report = run_detector(
                        detector,
                        batch,
                        cache,
                        batch_size=args.batch_size if kind != "presidio" else None,
                    )
                    written += report.written
                    cached += report.skipped
                    failed += report.failed
                    spans += report.spans
                    seen += len(batch)
                    log(f"    {name} / {detector.name}: {seen} seen, {written} written, "
                        f"{cached} cached, {failed} failed, {spans} spans")
                log(f"  {detector.name}: {seen} documents, {written} written, {cached} cached, "
                    f"{failed} failed, {spans} spans in {time.time() - started:.0f}s")
                failures += failed > 0
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
