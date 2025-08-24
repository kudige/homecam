#!/usr/bin/env bash
set -euo pipefail

# Ensure ffmpeg exists
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required in the container/host" >&2
  exit 1
fi

uvicorn app.main:app --host 0.0.0.0 --port 8091
