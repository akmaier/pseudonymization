#!/bin/bash
#SBATCH --job-name=gpuprobe
#SBATCH --partition=main
#SBATCH --account=miti
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=logs/gpuprobe_%j.out
#SBATCH --error=logs/gpuprobe_%j.err
R="${PSEUDONYMKIT_WORK:-$PWD}"
echo "node $(hostname)  gres ${SLURM_JOB_GRES:-?}"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>&1 | head -2
"$R/.venv/bin/python" - <<'EOF'
import torch
print("torch", torch.__version__, "built for cuda", torch.version.cuda)
print("cuda available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device:", torch.cuda.get_device_name(0),
          "capability", torch.cuda.get_device_capability(0))
    x = torch.randn(256, 256, device="cuda") @ torch.randn(256, 256, device="cuda")
    print("matmul ok:", float(x.sum()) == float(x.sum()))
EOF
