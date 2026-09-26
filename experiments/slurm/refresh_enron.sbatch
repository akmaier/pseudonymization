#!/bin/bash
# Re-sweep CARDIO:DE under the fixed union, then re-derive the operating points and the leakage
# profile from it. One allocation, because the head node reaps a sweep at about five minutes and the
# QOS submit limit is eight jobs.
#
# The sweep is RESTARTED: every union row was computed under the old rule.
# remaining sources need computing.
#SBATCH --job-name=refresh_enron
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=16:00:00
#SBATCH --output=logs/refresh_enron_%j.out
#SBATCH --error=logs/refresh_enron_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
export PYTHONPATH=src
echo "=== sweep === $(date -Is)"
.venv/bin/python experiments/score_detection.py --corpus enron --restart
echo "=== operating points === $(date -Is)"
.venv/bin/python experiments/operating_points.py --corpus enron --out results/detection
echo "=== leakage profile === $(date -Is)"
.venv/bin/python experiments/leakage_profile.py --corpus enron --out results/detection
echo "=== done === $(date -Is)"
