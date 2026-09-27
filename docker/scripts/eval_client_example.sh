#!/usr/bin/env bash
# Пример скрипта, аналогичного тому, что запускает кейсодержатель:
# последовательно отправляет фотографии в сервис и печатает {"slug": "..."}.
#
# Использование:
#   ./eval_client_example.sh /path/to/photos_dir [http://localhost:8000]

set -euo pipefail

PHOTOS_DIR="${1:?Укажите папку с фотографиями}"
BASE_URL="${2:-http://localhost:8000}"

for img in "$PHOTOS_DIR"/*; do
  [ -f "$img" ] || continue
  start=$(date +%s%3N)
  response=$(curl -s -X POST "$BASE_URL/api/predict" -F "file=@${img}")
  end=$(date +%s%3N)
  echo "${img##*/} -> ${response} ($((end-start)) ms)"
done
