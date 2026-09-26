#!/bin/bash
#SBATCH --job-name=profile_leak
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=01:00:00
#SBATCH --output=logs/profile_leak_%j.out
#SBATCH --error=logs/profile_leak_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
PYTHONPATH=src .venv/bin/python profile_leak.py
