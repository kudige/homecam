# backend/app/main.py
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from sqlalchemy.orm import Session
import threading
from typing import List
from .schemas import CameraStreamCreate, CameraStreamOut
from .ffprobe_utils import probe_rtsp
import datetime as dt


from .db import Base, engine, get_session, SessionLocal
from .models import Camera
from .schemas import (
    CameraCreate,
    CameraUpdate,
    CameraAdminOut,
    CameraClientOut,
    CameraClientItem,
    CameraClientList,
    RecordingFile,
)
from .ffmpeg_manager import ffmpeg_manager
from .recordings import list_recordings
from .config import settings, MEDIA_ROOT, LIVE_DIR, REC_DIR
from .retention import run_retention_loop

app = FastAPI(title="HomeCam API", version="0.2.0")

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

# DB schema
Base.metadata.create_all(bind=engine)

# Serve /media (used by both dev and docker)
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")

# Background retention loop (daily)
threading.Thread(target=run_retention_loop, args=(get_session,), daemon=True).start()

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
@app.on_event("startup")
def autostart_cameras() -> None:
    """
    Auto-start any camera with recordings enabled (retention_days > 0).
    """
    session = SessionLocal()
    try:
        cams: List[Camera] = session.query(Camera).filter(Camera.retention_days > 0).all()
        for cam in cams:
            ffmpeg_manager.start_camera(
                cam.id,
                cam.name,
                cam.rtsp_url,
                cam.low_width,
                cam.low_height,
                cam.low_crf,
                cam.high_crf,
            )
    finally:
        session.close()


# ----------------------------- Admin API (with RTSP) ------------------------------

@app.get("/api/admin/cameras", response_model=list[CameraAdminOut])
def admin_list_cameras(session: Session = Depends(get_session)):
    return session.query(Camera).order_by(Camera.id.asc()).all()


@app.post("/api/admin/cameras", response_model=CameraAdminOut)
def admin_create_camera(body: CameraCreate, session: Session = Depends(get_session)):
    if session.query(Camera).filter(Camera.name == body.name).first():
        raise HTTPException(400, "Camera name exists")
    cam = Camera(
        name=body.name,
        rtsp_url=body.rtsp_url,
        retention_days=body.retention_days or settings.DEFAULT_RETENTION_DAYS,
    )
    session.add(cam)
    session.commit()
    session.refresh(cam)
    return cam


@app.put("/api/admin/cameras/{cam_id}", response_model=CameraAdminOut)
def admin_update_camera(cam_id: int, body: CameraUpdate, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Not found")
    for f, v in body.dict(exclude_unset=True).items():
        setattr(cam, f, v)
    session.commit()
    session.refresh(cam)
    return cam


@app.delete("/api/admin/cameras/{cam_id}")
def admin_delete_camera(cam_id: int, session: Session = Depends(get_session)):
    cam = session.get(Camera, cam_id)
    if not cam:
        return {"ok": True}
    ffmpeg_manager.stop_camera(cam_id)
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
def admin_stop_camera(cam_id: int):
    ffmpeg_manager.stop_camera(cam_id)
    return {"ok": True}


# ----------------------------- Client API (no RTSP) -------------------------------

@app.get("/api/cameras", response_model=CameraClientList)
def client_list_cameras(request: Request, session: Session = Depends(get_session)):
    """
    Returns:
    {
      "cameras": [
        {
          "id": "1",
          "name": "Front Door",
          "low_url":  "http://<server>/media/live/<camera>/low/index.m3u8",
          "high_url": "http://<server>/media/live/<camera>/high/index.m3u8"
        },
        ...
      ]
    }
    """
    cams = session.query(Camera).order_by(Camera.id.asc()).all()
    base = str(request.base_url).rstrip("/")  # e.g. http://localhost:8091
    items: list[CameraClientItem] = []
    for cam in cams:
        # Build absolute URLs to the existing HLS outputs
        low  = f"/media/live/{cam.name}/low/index.m3u8"
        high = f"/media/live/{cam.name}/high/index.m3u8"
        items.append(CameraClientItem(
            id=str(cam.id),
            name=cam.name,
            low_url=low,
            high_url=high,
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
def get_recording_file(camera: str, date: str, hour: str, filename: str):
    """
    Returns the actual MP4 file content for playback/download.
    """
    file_path = REC_DIR / camera / date / hour / filename
    if not file_path.exists():
        raise HTTPException(404, "Recording not found")
    return FileResponse(file_path)

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
