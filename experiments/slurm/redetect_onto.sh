#!/bin/bash
# OntoNotes zh/ar re-detection, without Qwen3.6 — it shares a deployment with the Enron run.
cd "${PSEUDONYMKIT_WORK:-$PWD}"
. config/env.sh
exec env PYTHONPATH=src .venv/bin/python experiments/detect_gateway.py \
    --corpora ontonotes --concurrency 8 \
    --models gpt-oss-120b RedHatAI/gemma-4-31B-it-FP8-block \
             RedHatAI/Mistral-Small-3.2-24B-Instruct-2506-FP8 \
             GaleneAI/Magistral-Small-2509-FP8-Dynamic google/gemma-4-E4B-it \
             Microsoft/Phi-4-mini-instruct ibm-granite/granite-4.1-3b
