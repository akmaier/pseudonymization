#!/bin/bash
#SBATCH --job-name=codealltag_A
#SBATCH --partition=main
#SBATCH --account=miti
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=logs/codealltag_A_%j.out
#SBATCH --error=logs/codealltag_A_%j.err
# No GPU: this is a file walk over 1,468,942 small files plus a serialisation pass.
# Slurm redirects stdout/stderr BEFORE the script runs, so logs/ must exist at submit time.
set -euo pipefail
R="${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p "$R/logs" "$R/data/conditionA"
echo "host $(hostname)  started $(date -Is)"

echo "=== 1/2  size distribution and eligibility, all seven segments ==="
"$R/.venv/bin/python" "$R/xlq2.py"

echo
echo "=== 2/2  condition A ==="
cd "$R"
"$R/.venv/bin/python" "$R/experiments/build_A.py" \
    --corpus codealltag --out "$R/data/conditionA"

echo "finished $(date -Is)"
