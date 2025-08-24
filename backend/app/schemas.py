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

class CameraOut(BaseModel):
    id: int
    name: str
    rtsp_url: str
    enabled: bool
    retention_days: int
    low_width: int
    low_height: int
    high_crf: int
    low_crf: int

    # Pydantic v2
    model_config = {"from_attributes": True}

class RecordingFile(BaseModel):
    path: str
    start_ts: float  # epoch seconds inferred from filename
    size_bytes: int
