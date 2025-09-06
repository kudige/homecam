import logging
from typing import Optional, Dict, Tuple

from starlette.staticfiles import StaticFiles

from .ffmpeg_manager import ffmpeg_manager

logger = logging.getLogger(__name__)

class LeaseRenewStaticFiles(StaticFiles):
    """StaticFiles subclass that manages ffmpeg leases on media requests.

    For medium and high quality streams, the first request will automatically
    acquire a lease for the stream.  Subsequent requests will renew that lease
    so the underlying ffmpeg process remains active while content is served.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._leases: Dict[Tuple[int, str], str] = {}

    async def get_response(self, path: str, scope):  # type: ignore[override]
        # Serve the actual file first
        response = await super().get_response(path, scope)

        try:
            parts = path.split("/")
            if len(parts) >= 3 and parts[0] == "live":
                cam_name = parts[1]
                role = parts[2]
                if role in {"medium", "high"}:
                    cam_id = _cam_id_by_name(cam_name)
                    if cam_id is not None:
                        key = (cam_id, role)
                        lease_id = self._leases.get(key)
                        if lease_id is None or not ffmpeg_manager.renew_lease(cam_id, role, lease_id):
                            lease_id = ffmpeg_manager.acquire_lease(cam_id, role)
                            self._leases[key] = lease_id
        except Exception:  # pragma: no cover - best effort logging
            logger.exception("lease renew error")

        return response


def _cam_id_by_name(name: str) -> Optional[int]:
    """Helper to resolve cam_id from name using ffmpeg_manager state."""
    for cid, cname in ffmpeg_manager._cam_names.items():  # type: ignore[attr-defined]
        if cname == name:
            return cid
    return None
