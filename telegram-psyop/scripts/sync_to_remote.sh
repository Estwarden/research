#!/usr/bin/env bash
# Sync code to GPU box. Run after editing notebooks/scripts locally.
set -euo pipefail

REMOTE="${PSYOP_REMOTE:?Set PSYOP_REMOTE=user@gpu-host}"
REMOTE_DIR="${PSYOP_REMOTE_DIR:-/data/telegram-psyop}"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

rsync -az --delete \
  --exclude='data/' --exclude='models/' --exclude='output/' \
  --exclude='__pycache__/' --exclude='.git/' \
  "$SCRIPT_DIR/" "$REMOTE:$REMOTE_DIR/"

echo "Synced to $REMOTE:$REMOTE_DIR"
