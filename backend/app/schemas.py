from pydantic import BaseModel
from typing import Optional, List

class CameraCreate(BaseModel):
    name: str
    rtsp_url: str
    retention_days: Optional[int] = None

class CameraUpdate(BaseModel):
    rtsp_url: Optional[str] = None
    enabled: Optional[bool] = None
    retention_days: Optional[int] = None
    low_width: Optional[int] = None
    low_height: Optional[int] = None
    high_crf: Optional[int] = None
    low_crf: Optional[int] = None

    # These must be present:
    preferred_low_stream_id: Optional[int] = None
    preferred_high_stream_id: Optional[int] = None
    grid_target_w: Optional[int] = None
    grid_target_h: Optional[int] = None
    full_target_w: Optional[int] = None
    full_target_h: Optional[int] = None

# Streams (admin)
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
        from_attributes = True

# Admin camera (with streams and RTSP)
class CameraAdminOut(BaseModel):
    id: int
    name: str
    rtsp_url: str
    enabled: bool
    retention_days: int
    preferred_low_stream_id: Optional[int]
    preferred_high_stream_id: Optional[int]
    grid_target_w: int
    grid_target_h: int
    full_target_w: int
    full_target_h: int
    streams: List[CameraStreamOut]
    class Config:
        from_attributes = True

# Client view (no RTSP; includes ready-to-use HLS URLs and status)
class CameraClientOut(BaseModel):
    id: int
    name: str
    enabled: bool
    hls_low: str
    hls_high: str
    status: dict

class RecordingFile(BaseModel):
    path: str
    start_ts: float # epoch seconds inferred from filename
    size_bytes: int    

class CameraClientItem(BaseModel):
    id: str
    name: str
    low_url: str
    high_url: str

class CameraClientList(BaseModel):
    cameras: list[CameraClientItem]    
