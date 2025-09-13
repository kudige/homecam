# backend/app/main.py
from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import os
import re
from pathlib import Path
import logging
import time
import subprocess
import tempfile
import shutil
from sqlalchemy.orm import Session
import threading
from typing import List
from .models import CameraStream
from .schemas import CameraStreamCreate, CameraStreamOut
from .ffprobe_utils import probe_rtsp
from .roles import resolve_role
import datetime as dt


from .db import Base, engine, get_session, SessionLocal
from .models import RoleMode, CameraStream, Camera
from .schemas import (
    CameraCreate, CameraUpdate,
    CameraStreamCreate, CameraStreamOut,
    CameraRoleUpdate, CameraAdminOut,
    CameraClientItem, CameraClientList,
    RecordingFile,
    ClipExportRequest,
    SavedVideo,
)
from .ffmpeg_manager import ffmpeg_manager
from .lease_static import LeaseRenewStaticFiles
from .recordings import list_recordings
from .config import settings, MEDIA_ROOT, LIVE_DIR, REC_DIR, CLIP_DIR
from .retention import run_retention_loop

app = FastAPI(title="HomeCam API", version="0.2.0")

# Suppress default uvicorn access logs and re-emit them at debug level
logging.getLogger("uvicorn.access").disabled = True
access_logger = logging.getLogger("homecam.access")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    client = request.client
    access_logger.debug(
        "%s - \"%s %s\" %d %.2fms",
        client.host if client else "-",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )
    return response

# CORS (open for now; tighten later when adding auth)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure media dirs exist
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
LIVE_DIR.mkdir(parents=True, exist_ok=True)
REC_DIR.mkdir(parents=True, exist_ok=True)
CLIP_DIR.mkdir(parents=True, exist_ok=True)

# DB schema
Base.metadata.create_all(bind=engine)

# Serve /media (used by both dev and docker)
app.mount("/media", LeaseRenewStaticFiles(directory=str(MEDIA_ROOT)), name="media")

# Background retention loop (daily)
threading.Thread(target=run_retention_loop, args=(get_session,), daemon=True).start()

def ensure_stream_probed(session: Session, s: CameraStream) -> CameraStream:
    """If stream has no width/height, run ffprobe and persist metadata."""
    if s.width and s.height:
        return s
    meta = probe_rtsp(s.rtsp_url)
    s.width = meta.get("width")
    s.height = meta.get("height")
    s.fps = meta.get("fps")
    s.bitrate_kbps = meta.get("bitrate_kbps")
    s.probed_at = meta.get("probed_at") or dt.datetime.utcnow()
    session.commit()
    session.refresh(s)
    return s

def pick_best_stream(cam: Camera, want_w: int, want_h: int):
    """
    Select the enabled stream whose resolution is the 'closest at or above' the target
    (fallback to closest below if none above). Returns CameraStream or None.
    """
    candidates = [s for s in cam.streams if s.enabled and s.width and s.height]
    if not candidates:
        return None
    def score(s):
        # prefer >= target with minimal overshoot; otherwise minimal undershoot
        over_w = max(0, s.width - want_w)
        over_h = max(0, s.height - want_h)
        under_w = max(0, want_w - s.width)
        under_h = max(0, want_h - s.height)
        over = over_w + over_h
        under = under_w + under_h
        # Streams that meet/exceed target get better base; tie-breaker by total diff
        return (0 if over > 0 else 1, over if over > 0 else under, - (s.width * s.height))
    return sorted(candidates, key=score)[0]

# ----------------------------- Startup: autostart --------------------------------
# backend/app/main.py
@app.on_event("startup")
def autostart():
    s = SessionLocal()
    try:
        cams = s.query(Camera).all()
        for cam in cams:
            ffmpeg_manager.start_by_config(cam)
            if cam.retention_days > 0:
                src, sw, sh, run = resolve_role(cam,"recording")
                if run and src: ffmpeg_manager.start_role(cam.id, cam.name, "recording", src, cam.high_crf)
    finally: s.close()

@app.on_event("shutdown")
def shutdown_event():
    ffmpeg_manager.shutdown()

@app.put("/api/admin/cameras/{cam_id}/roles", response_model=CameraAdminOut)
def admin_update_roles(cam_id: int, body: CameraRoleUpdate, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Not found")

    # 1) Apply incoming role fields (+ retention_days)
    payload = body.dict(exclude_unset=True)

    # If recording is disabled, force retention to 0
    if payload.get("recording_mode") == RoleMode.disabled:
        payload["retention_days"] = 0

    # If retention_days provided but negative/null, clamp to 0..365 (or any sane max)
    if "retention_days" in payload:
        rd = payload["retention_days"]
        payload["retention_days"] = max(0, int(rd)) if rd is not None else 0

    for f, v in payload.items():
        setattr(cam, f, v)
    session.commit()
    session.refresh(cam)

    # 2) (Re)apply always-on roles (grid and recording-if-enabled)
    ffmpeg_manager.start_by_config(cam)

    # 3) If recording should not run, stop it explicitly (covers mode=disabled or retention=0)
    _, _, _, rec_run = resolve_role(cam, "recording")
    if not rec_run:
        ffmpeg_manager.stop_role(cam.id, cam.name, "recording")

    return cam    

# Medium/high on-demand controls
@app.post("/api/admin/cameras/{cam_id}/medium/start")
def start_medium(cam_id:int, session:Session=Depends(get_session)):
    cam = session.get(Camera, cam_id);  assert cam
    src, sw, sh, run = resolve_role(cam,"medium")
    if not run or not src: return {"ok": False, "reason":"disabled"}
    ffmpeg_manager.start_role(cam.id, cam.name, "medium", src, cam.low_crf)
    return {"ok": True}

@app.post("/api/admin/cameras/{cam_id}/medium/stop")
def stop_medium(cam_id: int, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id); assert cam
    ffmpeg_manager.stop_role(cam.id, cam.name, "medium")
    return {"ok": True}

@app.post("/api/admin/cameras/{cam_id}/high/start")
def start_high(cam_id:int, session:Session=Depends(get_session)):
    cam = session.get(Camera, cam_id);  assert cam
    src, sw, sh, run = resolve_role(cam,"high")
    if not run or not src: return {"ok": False, "reason":"disabled"}
    ffmpeg_manager.start_role(cam.id, cam.name, "high", src, cam.high_crf)
    return {"ok": True}

@app.post("/api/admin/cameras/{cam_id}/high/stop")
def stop_high(cam_id: int, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id); assert cam
    ffmpeg_manager.stop_role(cam.id, cam.name, "high")
    return {"ok": True}

# ----------------------------- Admin API (with RTSP) ------------------------------

@app.get("/api/admin/cameras", response_model=list[CameraAdminOut])
def admin_list_cameras(session: Session = Depends(get_session)):
    return session.query(Camera).order_by(Camera.id.asc()).all()


@app.post("/api/admin/cameras", response_model=CameraAdminOut)
def admin_create_camera(body: CameraCreate, session: Session = Depends(get_session)):
    # backend/app/main.py (inside admin_create_camera)
    cam = Camera(
        name=body.name,
        rtsp_url=body.rtsp_url,
        retention_days=body.retention_days or settings.DEFAULT_RETENTION_DAYS,
    )
    session.add(cam); session.commit(); session.refresh(cam)
    
    # seed master stream
    from .models import CameraStream
    master = CameraStream(camera_id=cam.id, name="master", rtsp_url=cam.rtsp_url, enabled=True, is_master=True)
    session.add(master); session.commit(); session.refresh(cam)
    return cam

@app.put("/api/admin/cameras/{cam_id}", response_model=CameraAdminOut)
def admin_update_camera(cam_id: int, body: CameraUpdate, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Not found")

    old_ret = cam.retention_days or 0

    for f, v in body.dict(exclude_unset=True).items():
        setattr(cam, f, v)
    session.commit()
    session.refresh(cam)

    new_ret = cam.retention_days or 0

    # If recordings were enabled and are now disabled:
    if old_ret > 0 and new_ret <= 0:
        # OPTION A (recommended): live-only reconfigure
        # Resolve preferred/auto streams (same as in start)
        low_stream = next((s for s in cam.streams if s.id == cam.preferred_low_stream_id), None)
        high_stream = next((s for s in cam.streams if s.id == cam.preferred_high_stream_id), None)

        if not low_stream:
            low_stream = pick_best_stream(cam, cam.grid_target_w or 640, cam.grid_target_h or 360)
        if not high_stream:
            high_stream = pick_best_stream(cam, cam.full_target_w or 1920, cam.full_target_h or 1080)

        low_url = (low_stream.rtsp_url if low_stream else cam.rtsp_url)
        high_url = (high_stream.rtsp_url if high_stream else cam.rtsp_url)
        same_source = (low_url == high_url)

        # Restart camera in live-only mode according to STREAM_MODE
        ffmpeg_manager.start_camera_dual(
            cam_id=cam.id,
            cam_name=cam.name,
            low_src=low_url,
            high_src=high_url,
            same_source=same_source,
            grid_w=cam.grid_target_w or 640,
            grid_h=cam.grid_target_h or 360,
            low_crf=cam.low_crf,
            high_crf=cam.high_crf,
        )

        # OPTION B (alternative): stop everything instead
        # ffmpeg_manager.stop_camera(cam.id)

    return cam

@app.delete("/api/admin/cameras/{cam_id}")
def admin_delete_camera(cam_id: int, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id)
    if not cam:
        return {"ok": True}
    ffmpeg_manager.stop_camera(cam_id, cam.name)
    session.delete(cam)
    session.commit()
    return {"ok": True}

@app.post("/api/admin/cameras/{cam_id}/start")
def admin_start_camera(cam_id: int, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Not found")

    # resolve low/high inputs (same as you have)
    low_stream = next((s for s in cam.streams if s.id == cam.preferred_low_stream_id), None)
    high_stream = next((s for s in cam.streams if s.id == cam.preferred_high_stream_id), None)

    if not low_stream:
        low_stream = pick_best_stream(cam, cam.grid_target_w, cam.grid_target_h)
    if not high_stream:
        high_stream = pick_best_stream(cam, cam.full_target_w, cam.full_target_h)

    low_url = (low_stream.rtsp_url if low_stream else cam.rtsp_url)
    high_url = (high_stream.rtsp_url if high_stream else cam.rtsp_url)

    same_source = (low_url == high_url)

    # >>> IMPORTANT: pass grid target to the manager (NOT low_width/low_height)
    ffmpeg_manager.start_camera_dual(
        cam_id=cam.id,
        cam_name=cam.name,
        low_src=low_url,
        high_src=high_url,
        same_source=same_source,
        # Use your grid FULL numbers here:
        grid_w=cam.grid_target_w or 640,
        grid_h=cam.grid_target_h or 360,
        low_crf=cam.low_crf,
        high_crf=cam.high_crf,
    )
    return {"ok": True, "same_source": same_source}


@app.post("/api/admin/cameras/{cam_id}/stop")
def admin_stop_camera(cam_id: int, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Not found")
    ffmpeg_manager.stop_camera(cam.id, cam.name)
    return {"ok": True}

@app.post("/api/admin/cameras/{cam_id}/grid/start")
def start_grid(cam_id: int, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Not found")

    # Resolve the grid role (uses auto/manual + grid_target_*)
    # If you moved the resolver to roles.py, import resolve_role and use it here.
    src, sw, sh, run = resolve_role(cam, "grid")  # returns (rtsp_url, scale_w, scale_h, should_run)
    if not run or not src:
        return {"ok": False, "reason": "grid_disabled_or_unavailable"}

    # Grid always uses low_crf; scaling only if sw/sh provided (auto mode)
    res = ffmpeg_manager.start_role(cam.id, cam.name, "grid", src, cam.low_crf, sw, sh)
    return {"ok": True, **(res if isinstance(res, dict) else {})}


# ----------------------------- Client API (no RTSP) -------------------------------

@app.get("/api/cameras", response_model=CameraClientList)
def client_list_cameras(session: Session = Depends(get_session)):
    """
    Returns:
    {
      "cameras": [
        {
          "id": "1",
          "name": "Front Door",
          "urls": {
            "grid":   "/media/live/<camera>/grid/index.m3u8",
            "medium": "/media/live/<camera>/medium/index.m3u8",
            "high":   "/media/live/<camera>/high/index.m3u8"
          }
        },
        ...
      ]
    }
    """
    cams = session.query(Camera).order_by(Camera.id.asc()).all()
    items: list[CameraClientItem] = []
    for cam in cams:
        urls = {
            role: f"/media/live/{cam.name}/{role}/index.m3u8"
            for role in ("grid", "medium", "high")
        }
        items.append(CameraClientItem(
            id=str(cam.id),
            name=cam.name,
            urls=urls,
        ))
    return CameraClientList(cameras=items)


# Recordings listing (client-accessible; paths are media-relative)
# replace the recordings_for_date endpoint body
@app.get("/api/cameras/{cam_id}/recordings/{date}", response_model=list[RecordingFile])
def recordings_for_date(cam_id: int, date: str, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Not found")

    rows = list_recordings(cam.name, date)
    out = []
    for it in rows:
        parts = it.get("rel_parts")
        if not parts or len(parts) < 4:
            # fallback: parse from legacy "path"
            p = Path(it["path"].lstrip("/"))
            parts = list(p.parts)  # ["camera","YYYY-MM-DD","HH","file.mp4"]
        camera, date_part, hour_part, filename = parts[0], parts[1], parts[2], parts[3]
        api_path = f"/api/recordings/{camera}/{date_part}/{hour_part}/{filename}"
        out.append({
            "path": api_path,
            "start_ts": it["start_ts"],
            "size_bytes": it["size_bytes"],
        })
    return out

@app.get("/api/recordings/{camera}/{date}/{hour}/{filename}")
def get_recording_file(camera: str, date: str, hour: str, filename: str, request: Request):
    """Return MP4 content with basic Range support for seeking."""
    file_path = REC_DIR / camera / date / hour / filename
    if not file_path.exists():
        raise HTTPException(404, "Recording not found")

    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")
    if range_header:
        m = re.match(r"bytes=(\d+)-(\d+)?", range_header)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else file_size - 1
            end = min(end, file_size - 1)
        else:
            start, end = 0, file_size - 1

        chunk_size = 1024 * 1024

        def iter_file():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    read_len = min(chunk_size, remaining)
                    data = f.read(read_len)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
        }
        return StreamingResponse(iter_file(), status_code=206, headers=headers, media_type="video/mp4")

    headers = {"Accept-Ranges": "bytes"}
    return FileResponse(file_path, media_type="video/mp4", headers=headers)


@app.post("/api/recordings/{camera}/{date}/{hour}/{filename}/export")
def export_recording_segment(
    camera: str,
    date: str,
    hour: str,
    filename: str,
    body: ClipExportRequest,
    background: BackgroundTasks,
):
    """Export a time range from a recording. If save is True, store on server; otherwise return file."""
    file_path = REC_DIR / camera / date / hour / filename
    if not file_path.exists():
        raise HTTPException(404, "Recording not found")

    start = max(0.0, body.start)
    end = max(start, body.end)

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(file_path),
        "-ss",
        str(start),
        "-to",
        str(end),
        "-c",
        "copy",
        str(tmp_path),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise HTTPException(500, f"ffmpeg failed: {proc.stderr.decode('utf-8', 'ignore')}")

    if body.save:
        name = body.name or f"clip_{int(time.time())}.mp4"
        safe = re.sub(r"[^\w\-]+", "_", name)
        if not safe.endswith(".mp4"):
            safe += ".mp4"
        dest = CLIP_DIR / safe
        try:
            shutil.move(str(tmp_path), dest)
        except Exception as e:
            raise HTTPException(500, f"Failed to save clip: {e}")
        return {"path": f"/api/saved/{dest.name}", "name": dest.name}

    download_name = body.name or "clip.mp4"
    if not download_name.endswith(".mp4"):
        download_name += ".mp4"
    background.add_task(lambda p: os.remove(p), tmp_path)
    return FileResponse(tmp_path, media_type="video/mp4", filename=download_name)


@app.get("/api/saved", response_model=list[SavedVideo])
def list_saved_videos():
    items: List[SavedVideo] = []
    if not CLIP_DIR.exists():
        return []
    for f in sorted(CLIP_DIR.glob("*.mp4")):
        items.append(
            SavedVideo(name=f.stem, path=f"/api/saved/{f.name}", size_bytes=f.stat().st_size)
        )
    return items


@app.get("/api/saved/{filename}")
def get_saved_video(filename: str, request: Request):
    file_path = CLIP_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "Not found")

    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")
    if range_header:
        m = re.match(r"bytes=(\d+)-(\d+)?", range_header)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else file_size - 1
            end = min(end, file_size - 1)
        else:
            start, end = 0, file_size - 1

        chunk_size = 1024 * 1024

        def iter_file():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    read_len = min(chunk_size, remaining)
                    data = f.read(read_len)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
        }
        return StreamingResponse(
            iter_file(), status_code=206, headers=headers, media_type="video/mp4"
        )

    headers = {"Accept-Ranges": "bytes"}
    return FileResponse(file_path, media_type="video/mp4", headers=headers)

@app.get("/api/admin/cameras/{cam_id}/streams", response_model=list[CameraStreamOut])
def admin_list_streams(cam_id: int, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Not found")
    return cam.streams

@app.post("/api/admin/cameras/{cam_id}/streams", response_model=CameraStreamOut)
def admin_add_stream(cam_id: int, body: CameraStreamCreate, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Not found")
    # create first
    from .models import CameraStream
    s = CameraStream(camera_id=cam.id, name=body.name, rtsp_url=body.rtsp_url, enabled=True)
    session.add(s)
    session.commit()
    session.refresh(s)
    # probe (best-effort)
    try:
        meta = probe_rtsp(s.rtsp_url)
        s.width = meta["width"]; s.height = meta["height"]
        s.fps = meta["fps"]; s.bitrate_kbps = meta["bitrate_kbps"]; s.probed_at = meta["probed_at"]
        session.commit(); session.refresh(s)
    except Exception as e:
        # leave as enabled but without metadata; admin can re-probe later
        pass
    return s

@app.post("/api/admin/cameras/{cam_id}/streams/{stream_id}/probe", response_model=CameraStreamOut)
def admin_probe_stream(cam_id: int, stream_id: int, session: Session = Depends(get_session)):
    from .models import CameraStream
    s = session.get(CameraStream, stream_id)
    if not s or s.camera_id != cam_id:
        raise HTTPException(404, "Not found")
    meta = probe_rtsp(s.rtsp_url)
    s.width = meta["width"]; s.height = meta["height"]
    s.fps = meta["fps"]; s.bitrate_kbps = meta["bitrate_kbps"]; s.probed_at = meta["probed_at"]
    session.commit(); session.refresh(s)
    return s

@app.get("/api/admin/cameras/{cam_id}/status")
def admin_camera_status(cam_id: int):
    # returns: {"running": bool, "roles": {"grid": bool, "medium": bool, "high": bool, "recording": bool}}
    return ffmpeg_manager.status(cam_id)
