#!/usr/bin/env bash
# Download Tier 1 datasets for telegram-psyop research.
# Total: ~55GB. Run ON THE REMOTE (Gaming PC) after setup_remote.sh.
# Requires: curl, ~60GB free disk space.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$DIR/data/raw"

mkdir -p "$RAW/kyrychenko" "$RAW/epfl" "$RAW/supplementary"

dl() {
  local dest="$1" url="$2"
  if [ -f "$dest" ]; then
    echo "  $(basename "$dest") already exists, skipping"
  else
    echo "  Downloading $(basename "$dest") ..."
    curl -L -C - -o "$dest" "$url"
  fi
}

# ================================================================
# 1. Kyrychenko War Channels (49GB)
#    79.5M posts, 66K channels, 18.2M forwards, Leiden clusters
#    https://zenodo.org/records/16949193
# ================================================================
echo "=== Kyrychenko War Channels ==="
KYRY="$RAW/kyrychenko"
KYRY_BASE="https://zenodo.org/records/16949193/files"

dl "$KYRY/channels.csv"        "$KYRY_BASE/channels.csv?download=1"
dl "$KYRY/leiden_clusters.csv" "$KYRY_BASE/leiden_clusters.csv?download=1"
dl "$KYRY/post_fwd.csv"        "$KYRY_BASE/post_fwd.csv?download=1"

for i in $(seq 1 8); do
  dl "$KYRY/post_texts_part_${i}.csv" "$KYRY_BASE/post_texts_part_${i}.csv?download=1"
done

# ================================================================
# 2. EPFL Propaganda Dataset (1.2GB dataset + 135MB models)
#    Labeled propaganda posts + trained models
#    https://zenodo.org/records/14736756
# ================================================================
echo ""
echo "=== EPFL Propaganda Dataset ==="
EPFL="$RAW/epfl"
EPFL_BASE="https://zenodo.org/records/14736756/files"

dl "$EPFL/dataset_v2.zip"    "$EPFL_BASE/dataset_v2.zip?download=1"
dl "$EPFL/final_models.zip"  "$EPFL_BASE/final_models.zip?download=1"
dl "$EPFL/INSTRUCTIONS.md"   "$EPFL_BASE/INSTRUCTIONS.md?download=1"

# Unzip if not already extracted
if [ -f "$EPFL/dataset_v2.zip" ] && [ ! -d "$EPFL/dataset_v2" ]; then
  echo "  Extracting dataset_v2.zip ..."
  unzip -q -o "$EPFL/dataset_v2.zip" -d "$EPFL/dataset_v2"
fi
if [ -f "$EPFL/final_models.zip" ] && [ ! -d "$EPFL/final_models" ]; then
  echo "  Extracting final_models.zip ..."
  unzip -q -o "$EPFL/final_models.zip" -d "$EPFL/final_models"
fi

# ================================================================
# 3. Supplementary GitHub datasets
# ================================================================
echo ""
echo "=== Supplementary datasets ==="
SUP="$RAW/supplementary"

for repo in \
  "yarakyrychenko/tg-misinfo-data" \
  "Aleksandr-Simanychev/WarNews" \
  "chan0park/VoynaSlov" \
  "SystemsLab-Sapienza/TGDataset"; do
  name="${repo##*/}"
  if [ ! -d "$SUP/$name" ]; then
    git clone --depth 1 "https://github.com/$repo" "$SUP/$name" || true
  else
    echo "  $name already cloned"
  fi
done

echo ""
echo "=== Download complete ==="
echo "Kyrychenko: $(ls -1 "$KYRY"/*.csv 2>/dev/null | wc -l) CSV files"
echo "EPFL:       $(ls -1 "$EPFL"/* 2>/dev/null | wc -l) files"
echo "Supplement: $(ls -1d "$SUP"/*/ 2>/dev/null | wc -l) repos"
du -sh "$RAW"
