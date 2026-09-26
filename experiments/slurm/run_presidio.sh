#!/bin/bash
cd "${PSEUDONYMKIT_WORK:-$PWD}"
for c in ontonotes enron; do
  echo "=== $c $(date -Is) ==="
  PYTHONPATH=src ./.venv/bin/python experiments/detect_local.py       --detectors presidio --corpora "$c" --stream-batch 1000 --cache results/detector_cache
  echo "=== $c rc=$? ==="
done
