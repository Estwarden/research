#!/usr/bin/env bash
# Setup the telegram-psyop workspace on the GPU box.
# Run from local machine. Creates dirs, installs deps, syncs code.
# Set PSYOP_REMOTE and PSYOP_REMOTE_DIR env vars before running.
set -euo pipefail

REMOTE="${PSYOP_REMOTE:?Set PSYOP_REMOTE=user@gpu-host}"
REMOTE_DIR="${PSYOP_REMOTE_DIR:-/data/telegram-psyop}"

echo "=== Setting up $REMOTE:$REMOTE_DIR ==="

# Create directory structure
ssh "$REMOTE" "mkdir -p $REMOTE_DIR/{data/{raw/kyrychenko,raw/epfl,processed,labels},scripts,notebooks,models,output}"

# Install Python deps (into user site-packages, no venv needed)
ssh "$REMOTE" "pip install --user --quiet \
  numpy pandas scikit-learn xgboost \
  torch torchvision torchaudio \
  transformers sentence-transformers \
  networkx scipy \
  pyarrow fastparquet \
  tqdm 2>&1 | tail -3"

echo ""
echo "=== Syncing code ==="
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
rsync -az --exclude='data/' --exclude='models/' --exclude='output/' \
  "$SCRIPT_DIR/" "$REMOTE:$REMOTE_DIR/"

echo ""
echo "=== Checking GPU ==="
ssh "$REMOTE" "python3 -c \"import torch; print(f'CUDA: {torch.cuda.is_available()}, GPU: {torch.cuda.get_device_name(0)}, VRAM: {torch.cuda.get_device_properties(0).total_mem // 1024**3}GB')\""

echo ""
echo "=== Disk space ==="
ssh "$REMOTE" "df -h $REMOTE_DIR | tail -1"

echo ""
echo "Done. Data downloads should run on remote:"
echo "  ssh $REMOTE"
echo "  cd $REMOTE_DIR"
echo "  bash scripts/download_datasets.sh"
