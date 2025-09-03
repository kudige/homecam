# backend/app/schemas.py
from pydantic import BaseModel
from typing import Optional, List
from .models import RoleMode

class CameraStreamCreate(BaseModel):
    name: str
    rtsp_url: str

class CameraStreamOut(BaseModel):
    id: int; name: str; rtsp_url: str; enabled: bool
    width: Optional[int]; height: Optional[int]; fps: Optional[int]; bitrate_kbps: Optional[int]
    class Config: from_attributes = True

class CameraRoleUpdate(BaseModel):
    # each may be: mode = auto/manual/disabled (grid: no 'disabled'), stream_id when manual, and (for grid) target dims
    grid_mode: Optional[RoleMode] = None
    grid_stream_id: Optional[int] = None
    grid_target_w: Optional[int] = None
    grid_target_h: Optional[int] = None

    medium_mode: Optional[RoleMode] = None
    medium_stream_id: Optional[int] = None

    high_mode: Optional[RoleMode] = None
    high_stream_id: Optional[int] = None

    recording_mode: Optional[RoleMode] = None
    recording_stream_id: Optional[int] = None

class CameraAdminOut(BaseModel):
    id: int; name: str; rtsp_url: str; retention_days: int
    grid_mode: RoleMode; grid_stream_id: Optional[int]; grid_target_w: int; grid_target_h: int
    medium_mode: RoleMode; medium_stream_id: Optional[int]
    high_mode: RoleMode; high_stream_id: Optional[int]
    recording_mode: RoleMode; recording_stream_id: Optional[int]
    streams: List[CameraStreamOut]
    class Config: from_attributes = True
