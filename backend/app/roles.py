# backend/app/roles.py
from typing import Optional, Tuple
from .models import Camera, CameraStream, RoleMode

def _best_stream_for(cam: Camera, target_w: int, target_h: int) -> Optional[CameraStream]:
    cands = [s for s in cam.streams if s.enabled and s.width and s.height]
    if not cands:
        return None
    def score(s: CameraStream):
        over = max(0, s.width - target_w) + max(0, s.height - target_h)
        under = max(0, target_w - s.width) + max(0, target_h - s.height)
        return (0 if over > 0 else 1, over if over > 0 else under, -(s.width * s.height))
    return sorted(cands, key=score)[0]

def resolve_role(cam: Camera, role: str) -> Tuple[Optional[str], Optional[int], Optional[int], bool]:
    """
    Returns (rtsp_url, scale_w, scale_h, should_run) for role in {"grid","medium","high","recording"}.
    Scaling is only applied for grid/auto when needed to match grid_target_*; otherwise None.
    """
    if role == "grid":
        if cam.grid_mode == RoleMode.manual and cam.grid_stream:
            return (cam.grid_stream.rtsp_url, None, None, True)
        pick = _best_stream_for(cam, cam.grid_target_w, cam.grid_target_h) or (cam.streams[0] if cam.streams else None)
        if not pick:
            return (cam.rtsp_url, cam.grid_target_w, cam.grid_target_h, True)
        if pick.width == cam.grid_target_w and pick.height == cam.grid_target_h:
            return (pick.rtsp_url, None, None, True)
        return (pick.rtsp_url, cam.grid_target_w, cam.grid_target_h, True)

    if role == "medium":
        if cam.medium_mode == RoleMode.disabled: return (None,None,None,False)
        if cam.medium_mode == RoleMode.manual and cam.medium_stream: return (cam.medium_stream.rtsp_url, None, None, True)
        pick = _best_stream_for(cam, cam.grid_target_w*2, cam.grid_target_h*2) or (cam.streams[0] if cam.streams else None)
        return ((pick.rtsp_url if pick else cam.rtsp_url), None, None, True)

    if role == "high":
        if cam.high_mode == RoleMode.disabled: return (None,None,None,False)
        if cam.high_mode == RoleMode.manual and cam.high_stream: return (cam.high_stream.rtsp_url, None, None, True)
        pick = max([s for s in cam.streams if s.enabled and s.width and s.height], key=lambda s: s.width*s.height, default=None)
        return ((pick.rtsp_url if pick else cam.rtsp_url), None, None, True)

    if role == "recording":
        if (cam.retention_days or 0) <= 0 or cam.recording_mode == RoleMode.disabled:
            return (None,None,None,False)
        if cam.recording_mode == RoleMode.manual and cam.recording_stream:
            return (cam.recording_stream.rtsp_url, None, None, True)
        pick = max([s for s in cam.streams if s.enabled and s.width and s.height], key=lambda s: s.width*s.height, default=None)
        return ((pick.rtsp_url if pick else cam.rtsp_url), None, None, True)

    return (None,None,None,False)
