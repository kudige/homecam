# backend/app/main.py
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from sqlalchemy.orm import Session
import threading
from typing import List

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
    ffmpeg_manager.start_camera(
        cam.id,
        cam.name,
        cam.rtsp_url,
        cam.low_width,
        cam.low_height,
        cam.low_crf,
        cam.high_crf,
    )
    return {"ok": True}


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
