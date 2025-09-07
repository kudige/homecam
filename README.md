# HomeCam (MVP)

A minimal home camera system: RTSP in → HLS live grid + recorded chunks, with a React frontend, FastAPI backend, and Nginx for serving.

## Features
- Add cameras with RTSP URLs and retention days.
- Live grid (low-res) and high-res view per camera.
- Continuous recording into 5-minute MP4 chunks (default, configurable).
- Browse recordings by camera + date and play chunks.
- Daily retention cleanup.

## Requirements
- Docker & Docker Compose (recommended), or
- Local: Python 3.11, Node 18+, FFmpeg installed.

## Quick Start (Docker)

```bash
# Build image
docker build -t homecam .

# Run frontend + backend
docker run -d --name homecam \
  -p 8090:8090 -p 8091:8091 \
  -v /mnt/homecam/media:/media \
  -v /mnt/homecam/data:/data \
  -v /mnt/homecam:/recordings \
  -e MEDIA_ROOT=/media \
  -e DB_PATH=/data/homecam.db \
  -e RECORDINGS_ROOT=/recordings \
  homecam

# Open
open http://localhost:8090
```

Run just one service or change ports via options:

```bash
# backend only on port 9001
docker run --rm -p 9001:9001 homecam --backend-only --api-port 9001

# frontend only on port 9000
docker run --rm -p 9000:9000 homecam --frontend-only --port 9000 --backend host:8091
```

The `--backend` option causes the frontend to proxy both `/api/` and `/media/` requests to the given host and port.

The repo also includes a `deploy/docker-compose.yml` which can be used in place of `docker run`. Supply environment variables via an `.env` file and pass options with the `command` field.

## Configuration

The container reads several environment variables (they can be supplied with `-e` flags or an env file):

| Variable | Default | Description |
|----------|---------|-------------|
| `MEDIA_ROOT` | `/media` | Path for live HLS and recordings served via `/media/`. |
| `RECORDINGS_ROOT` | `/recordings` | Optional separate location for MP4 recordings. |
| `DB_PATH` | `/data/homecam.db` | SQLite database path. |
| `DEFAULT_RETENTION_DAYS` | `7` | Days to keep recordings by default. |
| `RECORDING_SEGMENT_SEC` | `300` | Length of recording segments in seconds. |
| `PORT` | `8090` | Frontend (Nginx) port inside the container. Overridden by `--port`. |
| `API_PORT` | `8091` | Backend (FastAPI) port inside the container. Overridden by `--api-port`. |
| `API_BACKEND` | `127.0.0.1:8091` | Backend host:port for frontend proxy. Overridden by `--backend`. |

The entrypoint accepts:

- `--frontend-only` – run only the frontend
- `--backend-only` – run only the backend
- `--port <n>` – set frontend port
- `--api-port <n>` – set backend port
- `--backend <host:port>` – set backend host:port for frontend-only mode

### Add a camera

1. In the UI, add a Name and your `rtsp://` URL.
2. Click **Start** on a camera card to spawn the FFmpeg processes.
3. The grid shows low-res; open high-res via the button.

### Where files live

* Live HLS: `media/live/<camera>/(low|high)/index.m3u8`
* Recordings: `media/recordings/<camera>/YYYY-MM-DD/HH/HH-MM-SS.mp4` (or `$RECORDINGS_ROOT/<camera>/...` if `RECORDINGS_ROOT` is set)

### Retention

* Runs daily in the backend container.
* Default = 7 days; per-camera can be configured when adding/updating a camera.

### Recording segment length

* Recording segments default to 5 minutes (300 seconds).
* To change the duration, set the `RECORDING_SEGMENT_SEC` environment variable
  (or add it to a `.env` file) with the desired number of seconds, e.g.,

  ```bash
  echo "RECORDING_SEGMENT_SEC=60" >> .env  # 1-minute segments
  ```

## Dev Mode (no Docker)

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export MEDIA_ROOT=$(pwd)/../media
export DB_PATH=$(pwd)/../data/homecam.db
mkdir -p "$MEDIA_ROOT" ../data
uvicorn app.main:app --reload --port 8091
```

Frontend:

```bash
cd frontend
npm i
npm run dev
# visit http://localhost:8090 (proxied to backend via vite.config.js)
```

## Notes & Future Work

* Motion detection: add a `POST /api/cameras/{id}/zones` and run a parallel ffmpeg/gstreamer + OpenCV process.
* Recorded HLS playlists per time range can be generated instead of MP4 chunks for seamless scrub.
* Auth: protect `/api/*` and `/media/*` via Nginx auth or JWT.
* Health checks & restart policy for FFmpeg can be made more robust (exponential backoff, logs).
