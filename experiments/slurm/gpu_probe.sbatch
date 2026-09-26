#!/usr/bin/env bash
#SBATCH --job-name=gpu-probe
#SBATCH --partition=main
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=results/slurm/%x-%j.out
#SBATCH --error=results/slurm/%x-%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p results/slurm
echo "host=$(hostname)"
nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv
