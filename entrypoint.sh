#!/bin/bash
# CompliSense container entrypoint — FastAPI (uvicorn:8000), not Streamlit.
set -euo pipefail

DATA_DIR="${RBI_DATA_PATH:-/app/data}"
CHROMA_PATH="${CHROMA_DB_PATH:-/app/data/chroma_db}"
AUTO_INGEST="${CS_AUTO_INGEST:-false}"

mkdir -p "$DATA_DIR" "$CHROMA_PATH" "${HF_HOME:-/app/.cache/huggingface}"

echo "=== CompliSense ==="
echo "  data:   $DATA_DIR"
echo "  chroma: $CHROMA_PATH"
echo "  hf:     ${HF_HOME:-/app/.cache/huggingface}"

# Optional first-boot corpus build (slow: downloads PDFs + embedding model).
# Prefer: docker compose --profile ingest run --rm ingest
if [ "$AUTO_INGEST" = "true" ]; then
  if [ ! -f "$CHROMA_PATH/chroma.sqlite3" ]; then
    echo "Chroma empty — running ingest (CS_AUTO_INGEST=true)…"
    python ingest_data.py
  else
    echo "Chroma present — skipping ingest."
  fi
elif [ ! -f "$CHROMA_PATH/chroma.sqlite3" ]; then
  echo "NOTE: no Chroma store at $CHROMA_PATH."
  echo "      RBI/compliance Ask AI legs need: docker compose --profile ingest run --rm ingest"
  echo "      Other lenses (competitor / PESTEL / trend) still work without it."
fi

echo "Starting uvicorn on :8000 …"
# exec so uvicorn is PID 1 and receives SIGTERM cleanly
exec "$@"
