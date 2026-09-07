#!/usr/bin/env bash
# Fetch the public members of the pseudonymisation meta corpus.
# DUA-bound corpora (BRONCO150, CARDIO:DE, n2c2, OntoNotes) are NOT fetched here --
# they are obtained per-signatory and stored outside the shared folder. See applications/.
# Idempotent: re-running skips anything already present.
set -uo pipefail
# Override with CORPORA_ROOT; defaults to the group shared dataset folder.
ROOT="${CORPORA_ROOT:-/cluster/shared_dataset/pseudonymization-corpora}"
mkdir -p "$ROOT" && cd "$ROOT"
log(){ echo "[$(date -Is)] $*"; }

clone(){ # url dir
  if [ -d "$2/.git" ]; then log "SKIP  $2 (present)"; return 0; fi
  log "CLONE $2"
  if git clone -q --depth 1 "$1" "$2"; then log "OK    $2"; else log "FAIL  $2"; fi
}
fetch(){ # url outfile
  if [ -s "$2" ]; then log "SKIP  $2 (present)"; return 0; fi
  log "FETCH $2"
  if curl -fsSL --retry 3 --retry-delay 5 -o "$2.part" "$1"; then mv "$2.part" "$2"; log "OK    $2"; else rm -f "$2.part"; log "FAIL  $2"; fi
}
zenodo(){ # record_id dir
  local rec=$1 dir=$2
  mkdir -p "$dir"
  python3 - "$rec" "$dir" <<'PY'
import json,sys,urllib.request,os,subprocess
rec,d=sys.argv[1],sys.argv[2]
try:
    meta=json.load(urllib.request.urlopen(f"https://zenodo.org/api/records/{rec}",timeout=60))
except Exception as e:
    print(f"ZENODO-FAIL {rec}: {e}"); sys.exit(0)
for f in meta.get("files",[]):
    key=f.get("key") or f.get("filename"); url=f["links"]["self"]
    out=os.path.join(d,key)
    if os.path.exists(out) and os.path.getsize(out)>0:
        print(f"SKIP  {out}"); continue
    print(f"FETCH {out}  ({f.get('size','?')} bytes)")
    subprocess.run(["curl","-fsSL","--retry","3","-o",out,url])
PY
}

log "=== Enron (443 MB) ==="
mkdir -p enron && fetch https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz enron/enron_mail_20150507.tar.gz

log "=== TAB / ECHR ==="
clone https://github.com/NorskRegnesentral/text-anonymization-benchmark.git tab

log "=== CodEAlltag ==="
mkdir -p codealltag && cd codealltag
clone https://github.com/codealltag/CodEAlltag_pS.git pS
clone https://github.com/codealltag/CodEAlltag_formality_scores.git formality_scores
clone https://github.com/codealltag/privacy_tagger.git privacy_tagger
for seg in EVENTS FINANCE GERMAN MOVIES PHILOSOPHY TEENS TRAVELS; do
  clone "https://github.com/codealltag/CodEAlltag_pXL_$seg.git" "pXL_$seg"
done
cd "$ROOT"

log "=== MEDDOCAN (Zenodo 4279323 corpus, 4279338 guidelines) ==="
zenodo 4279323 meddocan
zenodo 4279338 meddocan_guidelines
clone https://github.com/PlanTL-GOB-ES/SPACCC_MEDDOCAN.git meddocan_scripts

log "=== MedDeID (Zenodo 21992866) ==="
zenodo 21992866 meddeid

log "=== REDACT ==="
clone https://github.com/guneeshvats/REDACT-PII-Benchmark.git redact

log "=== PIIBench (pipeline + taxonomy) ==="
clone https://github.com/pritesh-2711/pii-bench.git piibench

log "=== E3C ==="
clone https://github.com/hltfbk/E3C-Corpus.git e3c

log "=== AI4Privacy (HuggingFace) ==="
mkdir -p ai4privacy
python3 - <<'PY'
import json,urllib.request,os,subprocess
repo="ai4privacy/pii-masking-300k"
try:
    info=json.load(urllib.request.urlopen(f"https://huggingface.co/api/datasets/{repo}",timeout=60))
except Exception as e:
    print("HF-FAIL",e); raise SystemExit
files=[s["rfilename"] for s in info.get("siblings",[])
       if s["rfilename"].endswith((".parquet",".json",".jsonl",".md",".csv"))]
print(f"{len(files)} files listed")
for fn in files:
    out=os.path.join("ai4privacy",fn.replace("/","__"))
    if os.path.exists(out) and os.path.getsize(out)>0: continue
    url=f"https://huggingface.co/datasets/{repo}/resolve/main/{fn}"
    print("FETCH",fn)
    subprocess.run(["curl","-fsSL","--retry","3","-o",out,url])
PY

log "=== DONE. Sizes: ==="
du -sh "$ROOT"/* 2>/dev/null | sort -h
