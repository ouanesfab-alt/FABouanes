#!/usr/bin/env bash
# FABOuanes ERP — Script de téléchargement des dépendances hors-ligne
set -e
REQ_FILE="${1:-requirements.txt}"
OUT_DIR="${2:-wheels}"

echo "Téléchargement des wheels depuis $REQ_FILE vers $OUT_DIR..."
mkdir -p "$OUT_DIR"
python3 -m pip download -r "$REQ_FILE" -d "$OUT_DIR" --prefer-binary
echo "Téléchargement terminé avec succès dans $OUT_DIR."
