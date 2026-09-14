#!/usr/bin/env bash
#SBATCH --job-name=pseudo-detect
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --array=0-8
#SBATCH --output=results/slurm/%x-%A_%a.out
#SBATCH --error=results/slurm/%x-%A_%a.err
# One task per (corpus, model). No GPU: the models run on the NHR@FAU gateway, so this is
# network-bound and many tasks can share a node. Each task is independently resumable -- the
# detector cache skips documents already recorded, so a wall-clock kill costs one document.
#
# DeepSeek is excluded from the pool: the gateway backend is down (AM, 2026-09-08).
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p results/slurm results/detector_cache

CORPORA=(tab tab tab codealltag codealltag codealltag enron enron enron)
MODELS=("gpt-oss-120b" "Qwen/Qwen3.6-35B-A3B-FP8" "RedHatAI/gemma-4-31B-it-FP8-block"
        "gpt-oss-120b" "Qwen/Qwen3.6-35B-A3B-FP8" "RedHatAI/gemma-4-31B-it-FP8-block"
        "gpt-oss-120b" "Qwen/Qwen3.6-35B-A3B-FP8" "RedHatAI/gemma-4-31B-it-FP8-block")

CORPUS="${CORPORA[$SLURM_ARRAY_TASK_ID]}"
MODEL="${MODELS[$SLURM_ARRAY_TASK_ID]}"
echo "host=$(hostname) task=$SLURM_ARRAY_TASK_ID corpus=$CORPUS model=$MODEL started=$(date -Is)"
./.venv/bin/python experiments/run_detect.py --corpora "$CORPUS" --models "$MODEL"
echo "finished=$(date -Is)"
