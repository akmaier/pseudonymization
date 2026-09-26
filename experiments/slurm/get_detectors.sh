set -uo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
export HF_HOME="${PSEUDONYMKIT_WORK:-$PWD}"/hf_cache
mkdir -p "$HF_HOME" models
echo "=== disk before ==="; df -h /cluster | tail -1
echo "=== torch before ==="; .venv/bin/python -c "import torch;print(torch.__version__, torch.version.cuda)"

echo; echo "=== pip installs ==="
.venv/bin/pip install -q presidio-analyzer gliner flair SoMaJo 2>&1 | tail -15
echo "--- resolved ---"
.venv/bin/pip list 2>/dev/null | grep -iE "^(presidio|gliner|flair|SoMaJo|spacy|torch|transformers) " 

echo; echo "=== torch after (did anything replace it?) ==="
.venv/bin/python -c "import torch;print(torch.__version__, torch.version.cuda)"

echo; echo "=== spacy pipelines ==="
for m in en_core_web_lg de_core_news_lg xx_ent_wiki_sm; do
  .venv/bin/python -m spacy download $m >/dev/null 2>&1 && echo "  $m ok" || echo "  $m FAILED"
done

echo; echo "=== privacy_tagger model (2.6 GB) ==="
curl -sL --retry 3 -o models/privacy_tagger.pt https://privacy-tagger.aau.at/model.pt
ls -lh models/privacy_tagger.pt
.venv/bin/python - <<'PY'
import hashlib, pathlib
p = pathlib.Path("models/privacy_tagger.pt")
h = hashlib.sha256()
with p.open("rb") as f:
    for chunk in iter(lambda: f.read(1 << 22), b""):
        h.update(chunk)
print("  sha256", h.hexdigest())
PY

echo; echo "=== HuggingFace models ==="
.venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download
models = ["urchade/gliner_multi-v2.1", "urchade/gliner_multi_pii-v1",
          "obi/deid_roberta_i2b2", "StanfordAIMI/stanford-deidentifier-base",
          "Davlan/xlm-roberta-large-ner-hrl", "biu-nlp/lingmess-coref",
          "Qwen/Qwen2.5-0.5B", "intfloat/multilingual-e5-large"]
for m in models:
    try:
        p = snapshot_download(m, ignore_patterns=["*.msgpack", "*.h5", "*.onnx", "*.tflite"])
        print(f"  {m:<45} ok")
    except Exception as e:
        print(f"  {m:<45} FAILED {type(e).__name__}: {e}")
PY

echo; echo "=== disk after ==="; df -h /cluster | tail -1; du -sh hf_cache models
