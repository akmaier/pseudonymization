#!/bin/bash
# Qwen3.6 on OntoNotes' Chinese and Arabic documents, alongside the Enron run (AM, 2026-09-21).
# Two jobs on one deployment: the gateway interleaves them, so each is slower than it would be alone
# but the pair finishes sooner than running them back to back.
cd "${PSEUDONYMKIT_WORK:-$PWD}"
. config/env.sh
exec env PYTHONPATH=src .venv/bin/python experiments/detect_gateway.py \
    --corpora ontonotes --concurrency 6 --models Qwen/Qwen3.6-35B-A3B-FP8
