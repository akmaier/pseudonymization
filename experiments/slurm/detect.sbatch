#!/usr/bin/env bash
#SBATCH --job-name=pseudo-detect
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --time=24:00:00
#SBATCH --output=results/slurm/%x-%j.out
#SBATCH --error=results/slurm/%x-%j.err
# No GPU: the models run on the NHR@FAU gateway, not on ours. This job is network-bound.
# Resumable by design -- the detector cache skips documents already recorded, so a wall-clock
# kill costs at most the document in flight.
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p results/slurm results/detector_cache
echo "host=$(hostname) started=$(date -Is)"
./.venv/bin/python experiments/run_detect.py "$@"
echo "finished=$(date -Is)"
