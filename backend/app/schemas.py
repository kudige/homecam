from pydantic import BaseModel
from typing import Optional

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

# Admin view (includes RTSP)
class CameraAdminOut(BaseModel):
    id: int
    name: str
    rtsp_url: str
    enabled: bool
    retention_days: int
    low_width: int
    low_height: int
    high_crf: int
    low_crf: int
    model_config = {"from_attributes": True}

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
