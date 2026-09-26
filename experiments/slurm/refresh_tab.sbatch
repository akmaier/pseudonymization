#!/bin/bash
# Re-sweep CARDIO:DE under the fixed union, then re-derive the operating points and the leakage
# profile from it. One allocation, because the head node reaps a sweep at about five minutes and the
# QOS submit limit is eight jobs.
#
# The sweep RESUMES: the 1,292 rows already on disk were scored after the union fix, so only the
# remaining sources need computing.
#SBATCH --job-name=refresh_tab
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=logs/refresh_tab_%j.out
#SBATCH --error=logs/refresh_tab_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
export PYTHONPATH=src
echo "=== sweep === $(date -Is)"
.venv/bin/python experiments/score_detection.py --corpus tab
echo "=== operating points === $(date -Is)"
.venv/bin/python experiments/operating_points.py --corpus tab --out results/detection
echo "=== leakage profile === $(date -Is)"
.venv/bin/python experiments/leakage_profile.py --corpus tab --out results/detection
echo "=== done === $(date -Is)"
