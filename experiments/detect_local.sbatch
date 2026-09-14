#!/bin/bash
# Axis D's neural detector levels, on a GPU.
#
# This is the one part of the pipeline that genuinely belongs in Slurm. Everything else in this
# study runs on the head node (AM, 2026-09-12): the gateway pool is a network client, Presidio is
# CPU. GLiNER, the three fine-tuned de-ID encoders and the flair privacy_tagger are transformer
# inference, and the head node has no GPU.
#
# One job per corpus, submitted smallest first so that Enron — 58,636 of the 66,298 documents —
# never parks the three small corpora behind a multi-day allocation:
#
#     cd /cluster/maier/pseudonymization
#     mkdir -p logs                          # Slurm redirects BEFORE the script runs (see below)
#     for c in cardiode tab ontonotes enron; do
#         sbatch --export=ALL,CORPUS=$c experiments/detect_local.sbatch
#     done
#
# **Resumable by design.** The detector cache is consulted before work is queued, and a record whose
# document has since been rebuilt is re-detected rather than skipped. So a job that hits the 24 h
# wall clock is simply resubmitted and continues; nothing is lost but the document in flight.
#
# **The GPU type is pinned, and it has to be.** Probed 2026-09-12, one job per type:
#
#     V100 (Volta 7.0)          torch.cuda.is_available()  True
#     Quadro RTX 8000 (7.5)     True
#     Quadro RTX 6000 (7.5)     True
#     GTX 1080 Ti / Titan Xp    FALSE — "CUDA error 804: forward compatibility was attempted on
#                               non supported HW"; the node driver does not match torch 2.5.1+cu121
#
# Leaving `--gres=gpu:1` unpinned looked right on memory grounds — the largest checkpoint is the
# 2.6 GB privacy_tagger and the runner loads one model at a time, so 11 GB is ample — and was wrong
# in fact: the 11 GB cards are the broken ones and they are the largest pool in the cluster, so
# unpinned jobs land preferentially where they cannot run. Override with `--gres=gpu:<type>:1`.
#
# A red herring to ignore: `Failed to initialize NVML: Driver/library version mismatch` appears on
# **every** node, including those where CUDA works perfectly. `nvidia-smi` is broken cluster-wide.
# The only thing that discriminates is `torch.cuda.is_available()`.
#
#SBATCH --job-name=detect_local
#SBATCH --partition=main
#SBATCH --account=miti
#SBATCH --gres=gpu:q8000:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=/cluster/maier/pseudonymization/logs/detect_local_%x_%j.out
#SBATCH --error=/cluster/maier/pseudonymization/logs/detect_local_%x_%j.err
#
# Slurm redirects stdout/stderr *before* this script runs. If logs/ does not exist at submit time the
# job dies instantly with RunTime=00:00:00 and **no log at all** — the failure mode that costs a
# whole run. It is created at submit time above and again here, because both are cheap.

set -euo pipefail
R=/cluster/maier/pseudonymization
mkdir -p "$R/logs"
cd "$R"

CORPUS="${CORPUS:-cardiode}"
DETECTORS="${DETECTORS:-gliner finetuned privacy_tagger}"
# LIMIT and CACHE exist so a smoke test runs *this* script rather than a lookalike: the thing worth
# testing is the allocation, the CUDA wheel and six model loads, and a separate script would test a
# different one of each. LIMIT=3 with a scratch CACHE touches nothing the real run will read.
LIMIT="${LIMIT:-0}"
CACHE="${CACHE:-results/detector_cache}"

echo "host      $(hostname)"
echo "job       ${SLURM_JOB_ID:-none}  corpus ${CORPUS}  detectors ${DETECTORS}"
echo "started   $(date -Is)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || echo "no nvidia-smi"

PYTHONPATH=src "$R/.venv/bin/python" experiments/detect_local.py \
    --detectors ${DETECTORS} \
    --corpora "${CORPUS}" \
    --device cuda \
    --limit "${LIMIT}" \
    --cache "${CACHE}"

echo "finished  $(date -Is)"
