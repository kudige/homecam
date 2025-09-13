# backend/app/schemas.py
from typing import Optional, List, Dict
from pydantic import BaseModel
from .models import RoleMode  # Enum: "auto" | "manual" | "disabled"

# -------- Camera CRUD (admin) --------

class CameraCreate(BaseModel):
    name: str
    rtsp_url: str
    retention_days: Optional[int] = None  # 0 means no recordings

class CameraUpdate(BaseModel):
    rtsp_url: Optional[str] = None
    enabled: Optional[bool] = None
    retention_days: Optional[int] = None
    # legacy encoder knobs (keep for CRF)
    low_crf: Optional[int] = None
    high_crf: Optional[int] = None
    # older fields retained for compatibility; harmless if unused
    low_width: Optional[int] = None
    low_height: Optional[int] = None
    high_crf_: Optional[int] = None  # ignore if present in older code
    low_crf_: Optional[int] = None

# -------- Streams (admin) --------

class CameraStreamCreate(BaseModel):
    name: str
    rtsp_url: str

class CameraStreamOut(BaseModel):
    id: int
    name: str
    rtsp_url: str
    enabled: bool
    width: Optional[int]
    height: Optional[int]
    fps: Optional[int]
    bitrate_kbps: Optional[int]
    class Config:
        from_attributes = True  # Pydantic v2

# -------- Role config (admin) --------

class CameraRoleUpdate(BaseModel):
    # grid (always on) – no disabled
    grid_mode: Optional[RoleMode] = None
    grid_stream_id: Optional[int] = None
    grid_target_w: Optional[int] = None
    grid_target_h: Optional[int] = None
    # medium / high / recording – allow disabled
    medium_mode: Optional[RoleMode] = None
    medium_stream_id: Optional[int] = None
    high_mode: Optional[RoleMode] = None
    high_stream_id: Optional[int] = None
    recording_mode: Optional[RoleMode] = None
    recording_stream_id: Optional[int] = None
    retention_days: Optional[int] = None
    
class CameraAdminOut(BaseModel):
    id: int
    name: str
    rtsp_url: str
    retention_days: int

    grid_mode: RoleMode
    grid_stream_id: Optional[int]
    grid_target_w: int
    grid_target_h: int

    medium_mode: RoleMode
    medium_stream_id: Optional[int]

    high_mode: RoleMode
    high_stream_id: Optional[int]

    recording_mode: RoleMode
    recording_stream_id: Optional[int]

    streams: List[CameraStreamOut]
    class Config:
        from_attributes = True

# -------- Client list (no RTSP) --------

class CameraClientItem(BaseModel):
    id: str
    name: str
    urls: Dict[str, str]  # role -> url

class CameraClientList(BaseModel):
    cameras: List[CameraClientItem]

# -------- Recordings listing --------

class RecordingFile(BaseModel):
    path: str          # API path like /api/recordings/<cam>/<date>/<hour>/<file>.mp4
    start_ts: float    # epoch seconds
    size_bytes: int

# -------- Clip export --------

class ClipExportRequest(BaseModel):
    start: float
    end: float
    name: Optional[str] = None
    save: bool = False

class SavedVideo(BaseModel):
    name: str
    path: str
    size_bytes: int
