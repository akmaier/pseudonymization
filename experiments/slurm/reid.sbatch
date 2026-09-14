#!/usr/bin/env bash
#SBATCH --job-name=pseudo-reid
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=results/slurm/%x-%j.out
#SBATCH --error=results/slurm/%x-%j.err
# No GPU requested: the attacks are CPU-only. The head node is not the place to run them --
# a 20,000-message load was OOM-killed there.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p results/slurm          # Slurm redirects before the script runs; see METHODS on this trap
CORPORA="${PSEUDONYMKIT_WORK:?set it, see config/env.example.sh}/data/corpora"
echo "host=$(hostname) started=$(date -Is)"
./.venv/bin/python experiments/run_reid.py \
    --enron "$CORPORA/enron/enron_mail_20150507.tar.gz" \
    --limit "${LIMIT:-20000}" --stride "${STRIDE:-25}" \
    --out "results/reid_cells.jsonl"
echo "finished=$(date -Is)"
