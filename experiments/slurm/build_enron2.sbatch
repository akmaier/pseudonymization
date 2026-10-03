#!/usr/bin/env bash
# Build ENRON 2.0 (AM, 2026-10-03): body and subject only, deduplicated, CARDIO:DE-sized.
#
# One streaming pass over all 517,401 messages of the archive, holding every distinct body in
# memory (a few GB), then a seeded draw and the gold for the ~4,300 drawn messages. CPU only, no
# gateway. Not on the head node: score_recommended.py was OOM-killed there on Enron.
#
#SBATCH --job-name=enron2
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --output=logs/enron2_%j.out
#SBATCH --error=logs/enron2_%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/enron2
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
echo "host=$(hostname) started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/build_enron2.py ${EXTRA:-}
rc=$?
echo "finished=$(date -Is) exit=$rc"
exit $rc
