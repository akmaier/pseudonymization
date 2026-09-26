#!/bin/bash
# Rebuild Enron condition A with the word-boundary fix in the adapter's name matcher.
#
# Written to a NEW file. The detector cache and both patch sets validate on text_sha256, and
# build_text() does not depend on the mention layer, so the text should come out byte-identical and
# every cached detection stay valid. That is the first thing the comparison checks.
#
#SBATCH --job-name=rebuild_enron_a2
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=08:00:00
#SBATCH --output=logs/rebuild_enron_a2_%j.out
#SBATCH --error=logs/rebuild_enron_a2_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
. config/env.sh
export PYTHONPATH=src
.venv/bin/python experiments/build_enron.py \
    --source "$PSEUDONYMKIT_CORPORA/enron/enron_mail_20150507.tar.gz" \
    --out data/conditionA/enron_A_fixed.jsonl.gz --rate 0.10 --seed 0
