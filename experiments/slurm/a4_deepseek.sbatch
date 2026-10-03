#!/usr/bin/env bash
#SBATCH --job-name=a4_deep
#SBATCH --ntasks=1 --cpus-per-task=8 --mem=64G --time=24:00:00
#SBATCH --output=logs/a4_deep_%j.out
#SBATCH --error=logs/a4_deep_%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"; . config/env.sh; cd "${PSEUDONYMKIT_WORK:-$PWD}"
export OMP_NUM_THREADS=2
# Qwen3.6 is a reasoning model: 4,484 s per cell at concurrency 4, so 45 cells is 42 h. It is a
# planned model and scope is not negotiable, so it gets its own job and far more queries in
# flight rather than being dropped. Its own job also means it cannot be starved by, or starve,
# the seven fast models.
# **One allocation per corpus, not one for both** (2026-10-03). The loop ran the corpora in
# sequence and at these per-cell times a 24 h allocation never reached the second: job 779096
# spent its whole wall clock on CARDIO:DE and left all 44 Enron cells untouched. CORPORA splits
# them; the resume index reads every shard, so two writers never repeat a cell.
#
# DeepSeek took 32 cells in 24 h with zero 429s, so it keeps the full concurrency per corpus.
for CORPUS in ${CORPORA:-cardiode enron}; do
  echo "=== $CORPUS === $(date -Is)"
  PYTHONPATH=src .venv/bin/python experiments/run_a4_sample.py --corpus "$CORPUS" \
      --models 'deepseek-ai/DeepSeek-V4-Flash-0731' --limit 200 --concurrency "${CONC:-24}"
done
