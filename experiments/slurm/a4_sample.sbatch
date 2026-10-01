#!/usr/bin/env bash
# A4 at the 22 pre-registered points, both conditions, every live gateway model in parallel.
#
# ONE job, not an array: the gateway client holds no GPU and lives in recv(), and an earlier
# version as a nine-task array occupied eight of the association's slots doing nothing
# (detect_gateway.py:3-8). A single slot is taken because Enron's released corpus does not fit
# comfortably on the head node -- score_recommended.py was OOM-killed there on 2026-09-29.
#
# Corpora run in SEQUENCE. Two processes would contend for the same per-model token budget, which
# is exactly the resource the model-parallelism is there to exploit.
#SBATCH --job-name=a4_sample
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=logs/a4_sample_%j.out
#SBATCH --error=logs/a4_sample_%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/phase1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
echo "host=$(hostname) started=$(date -Is)"
for CORPUS in ${CORPORA:-cardiode enron}; do
  echo "=== $CORPUS === $(date -Is)"
  PYTHONPATH=src .venv/bin/python experiments/run_a4_sample.py \
      --corpus "$CORPUS" --limit "${LIMIT:-200}" --concurrency "${CONC:-4}" \
      ${MODELS:+--models $MODELS}
done
echo "finished=$(date -Is)"
