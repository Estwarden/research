#!/usr/bin/env bash
# Pull results from GPU box back to local.
set -euo pipefail

REMOTE="${PSYOP_REMOTE:?Set PSYOP_REMOTE=user@gpu-host}"
REMOTE_DIR="${PSYOP_REMOTE_DIR:-/data/telegram-psyop}"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

rsync -az "$REMOTE:$REMOTE_DIR/output/" "$SCRIPT_DIR/output/"

echo "Pulled output/ from $REMOTE:$REMOTE_DIR"
