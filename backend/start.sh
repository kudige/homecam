#!/usr/bin/env bash
set -euo pipefail

# Ensure ffmpeg exists
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required in the container/host" >&2
  exit 1
fi

API_PORT=${API_PORT:-8091}
uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT"
