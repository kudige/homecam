# HomeCam (MVP)

A minimal home camera system: RTSP in → HLS live grid + recorded chunks, with a React frontend, FastAPI backend, and Nginx for serving.

## Features
- Add cameras with RTSP URLs and retention days.
- Live grid (low-res) and high-res view per camera.
- Continuous recording into 5-minute MP4 chunks.
- Browse recordings by camera + date and play chunks.
- Daily retention cleanup.

## Requirements
- Docker & Docker Compose (recommended), or
- Local: Python 3.11, Node 18+, FFmpeg installed.

## Quick Start (Docker)

```bash
# In repo root
cd frontend && npm i && npm run build && cd ..

# Launch services
cd deploy
docker compose up --build -d

# Open
open http://localhost:8080
````

### Add a camera

1. In the UI, add a Name and your `rtsp://` URL.
2. Click **Start** on a camera card to spawn the FFmpeg processes.
3. The grid shows low-res; open high-res via the button.

### Where files live

* Live HLS: `media/live/<camera>/(low|high)/index.m3u8`
* Recordings: `media/recordings/<camera>/YYYY-MM-DD/HH/HH-MM-SS.mp4`

### Retention

* Runs daily in the backend container.
* Default = 7 days; per-camera can be configured when adding/updating a camera.

## Dev Mode (no Docker)

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export MEDIA_ROOT=$(pwd)/../media
export DB_PATH=$(pwd)/../data/homecam.db
mkdir -p "$MEDIA_ROOT" ../data
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm i
npm run dev
# visit http://localhost:5173 (proxied to backend via vite.config.js)
```

## Notes & Future Work

* Motion detection: add a `POST /api/cameras/{id}/zones` and run a parallel ffmpeg/gstreamer + OpenCV process.
* Recorded HLS playlists per time range can be generated instead of MP4 chunks for seamless scrub.
* Auth: protect `/api/*` and `/media/*` via Nginx auth or JWT.
* Health checks & restart policy for FFmpeg can be made more robust (exponential backoff, logs).

```
