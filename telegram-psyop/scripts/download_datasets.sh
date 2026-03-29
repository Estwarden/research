#!/usr/bin/env bash
# Download Tier 1 datasets for telegram-psyop research.
# Total: ~55GB. Run from telegram-psyop/ directory.
# Requires: wget or curl, ~60GB free disk space.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$DIR/data/raw"

mkdir -p "$RAW/kyrychenko" "$RAW/epfl" "$RAW/supplementary"

# ================================================================
# 1. Kyrychenko War Channels (49GB)
#    79.5M posts, 66K channels, 18.2M forwards, Leiden clusters
#    https://zenodo.org/records/16949193
# ================================================================
echo "=== Kyrychenko War Channels (49GB) ==="
KYRY="$RAW/kyrychenko"

# Channel metadata (16MB) -- always download
wget -nc -O "$KYRY/channels.csv" \
  "https://zenodo.org/records/16949193/files/channels.csv?download=1" || true

# Leiden clusters with labels (1.5MB)
wget -nc -O "$KYRY/leiden_clusters.csv" \
  "https://zenodo.org/records/16949193/files/leiden_clusters.csv?download=1" || true

# Forwarding graph (600MB)
wget -nc -O "$KYRY/post_fwd.csv" \
  "https://zenodo.org/records/16949193/files/post_fwd.csv?download=1" || true

# Post texts (8 parts, ~6GB each, 49GB total)
# Uncomment to download -- these are large
for i in $(seq 1 8); do
  if [ ! -f "$KYRY/post_texts_part_${i}.csv" ]; then
    echo "  Downloading post_texts_part_${i}.csv ..."
    wget -c -O "$KYRY/post_texts_part_${i}.csv" \
      "https://zenodo.org/records/16949193/files/post_texts_part_${i}.csv?download=1" || true
  else
    echo "  post_texts_part_${i}.csv already exists, skipping"
  fi
done

# ================================================================
# 2. EPFL Propaganda Dataset (6GB)
#    Labeled propaganda posts + embeddings + trained models
#    https://zenodo.org/records/14736756
# ================================================================
echo ""
echo "=== EPFL Propaganda Dataset (6GB) ==="
EPFL="$RAW/epfl"

wget -nc -O "$EPFL/dataset_v2.zip" \
  "https://zenodo.org/records/14736756/files/dataset_v2.zip?download=1" || true

wget -nc -O "$EPFL/final_models.zip" \
  "https://zenodo.org/records/14736756/files/final_models.zip?download=1" || true

wget -nc -O "$EPFL/INSTRUCTIONS.md" \
  "https://zenodo.org/records/14736756/files/INSTRUCTIONS.md?download=1" || true

# Embeddings (4.7GB) -- optional, can regenerate
# wget -nc -O "$EPFL/embeddings.zip" \
#   "https://zenodo.org/records/14736756/files/embeddings.zip?download=1" || true

# ================================================================
# 3. Supplementary GitHub datasets
# ================================================================
echo ""
echo "=== Supplementary datasets ==="
SUP="$RAW/supplementary"

# tg-misinfo-data: RU propaganda channels, first weeks of invasion
if [ ! -d "$SUP/tg-misinfo-data" ]; then
  git clone --depth 1 https://github.com/yarakyrychenko/tg-misinfo-data "$SUP/tg-misinfo-data" || true
fi

# WarNews: RU + UA channels, Feb-Mar 2022
if [ ! -d "$SUP/WarNews" ]; then
  git clone --depth 1 https://github.com/Aleksandr-Simanychev/WarNews "$SUP/WarNews" || true
fi

# VoynaSlov: multi-platform, topic modeling
if [ ! -d "$SUP/VoynaSlov" ]; then
  git clone --depth 1 https://github.com/chan0park/VoynaSlov "$SUP/VoynaSlov" || true
fi

# TGDataset: 120K+ channel metadata
if [ ! -d "$SUP/TGDataset" ]; then
  git clone --depth 1 https://github.com/SystemsLab-Sapienza/TGDataset "$SUP/TGDataset" || true
fi

echo ""
echo "=== Download complete ==="
echo "Kyrychenko: $(ls -1 "$KYRY"/*.csv 2>/dev/null | wc -l) files"
echo "EPFL:       $(ls -1 "$EPFL"/* 2>/dev/null | wc -l) files"
echo "Supplement: $(ls -1d "$SUP"/*/ 2>/dev/null | wc -l) repos"
echo ""
echo "Next: run scripts/extract.sh to unzip EPFL data"
