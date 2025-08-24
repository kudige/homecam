from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pathlib import Path
import threading

from .db import Base, engine, get_session
from .models import Camera
from .schemas import CameraCreate, CameraUpdate, CameraOut, RecordingFile
from .ffmpeg_manager import ffmpeg_manager
from .recordings import list_recordings
from .config import settings, MEDIA_ROOT, LIVE_DIR, REC_DIR
from .retention import run_retention_loop

app = FastAPI(title="HomeCam API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure dirs
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
LIVE_DIR.mkdir(parents=True, exist_ok=True)
REC_DIR.mkdir(parents=True, exist_ok=True)

# Create DB schema
Base.metadata.create_all(bind=engine)

# Serve media under /media (Nginx will also serve in production)
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")

# Background retention thread
threading.Thread(target=run_retention_loop, args=(get_session,), daemon=True).start()

# ----- Camera CRUD -----

@app.get("/api/cameras", response_model=list[CameraOut])
def list_cameras(session: Session = Depends(get_session)):
    cams = session.query(Camera).order_by(Camera.id.asc()).all()
    return cams

@app.post("/api/cameras", response_model=CameraOut)
def create_camera(body: CameraCreate, session: Session = Depends(get_session)):
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

@app.put("/api/cameras/{cam_id}", response_model=CameraOut)
def update_camera(cam_id: int, body: CameraUpdate, session: Session = Depends(get_session)):
    cam = session.get(Camera,cam_id)
    if not cam:
        raise HTTPException(404, "Not found")
    for f, v in body.dict(exclude_unset=True).items():
        setattr(cam, f, v)
    session.commit()
    session.refresh(cam)
    return cam

@app.delete("/api/cameras/{cam_id}")
def delete_camera(cam_id: int, session: Session = Depends(get_session)):
    cam = session.get(Camera,cam_id)
    if not cam:
        return {"ok": True}
    # stop if running
    ffmpeg_manager.stop_camera(cam_id)
    session.delete(cam)
    session.commit()
    return {"ok": True}

# ----- Live control & URLs -----

@app.post("/api/cameras/{cam_id}/start")
def start_camera(cam_id: int, session: Session = Depends(get_session)):
    cam = session.get(Camera,cam_id)
    if not cam:
        raise HTTPException(404, "Not found")
    ffmpeg_manager.start_camera(
        cam_id, cam.name, cam.rtsp_url, cam.low_width, cam.low_height, cam.low_crf, cam.high_crf
    )
    return {"ok": True}

@app.post("/api/cameras/{cam_id}/stop")
def stop_camera(cam_id: int):
    ffmpeg_manager.stop_camera(cam_id)
    return {"ok": True}

@app.get("/api/cameras/{cam_id}/live")
def live_urls(cam_id: int, session: Session = Depends(get_session)):
    cam = session.get(Camera,cam_id)
    if not cam:
        raise HTTPException(404, "Not found")
    base = f"/media/live/{cam.name}"
    return {
        "low": f"{base}/low/index.m3u8",
        "high": f"{base}/high/index.m3u8",
        "status": ffmpeg_manager.status(cam_id),
    }

# ----- Recordings -----

@app.get("/api/cameras/{cam_id}/recordings/{date}", response_model=list[RecordingFile])
def recordings_for_date(cam_id: int, date: str, session: Session = Depends(get_session)):
    cam = session.get(Camera,cam_id)
    if not cam:
        raise HTTPException(404, "Not found")
    return list_recordings(cam.name, date)
