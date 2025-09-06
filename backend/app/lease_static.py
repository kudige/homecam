import logging
from typing import Optional

from starlette.staticfiles import StaticFiles
from urllib.parse import parse_qs

from .ffmpeg_manager import ffmpeg_manager

logger = logging.getLogger(__name__)

class LeaseRenewStaticFiles(StaticFiles):
    """StaticFiles subclass that renews ffmpeg leases on media requests.

    When a client requests a medium or high quality stream segment or playlist,
    a ``lease`` query parameter may be supplied.  This handler will renew the
    corresponding lease so that the stream stays alive while it is actively
    being consumed.
    """

    async def get_response(self, path: str, scope):  # type: ignore[override]
        # Serve the actual file first
        response = await super().get_response(path, scope)

        try:
            parts = path.split("/")
            if len(parts) >= 3 and parts[0] == "live":
                cam_name = parts[1]
                role = parts[2]
                if role in {"medium", "high"}:
                    qs = parse_qs(scope.get("query_string", b"").decode())
                    lease_id = qs.get("lease", [None])[0]
                    if lease_id:
                        cam_id = _cam_id_by_name(cam_name)
                        if cam_id is not None:
                            ffmpeg_manager.renew_lease(cam_id, role, lease_id)
        except Exception:  # pragma: no cover - best effort logging
            logger.exception("lease renew error")

        return response


def _cam_id_by_name(name: str) -> Optional[int]:
    """Helper to resolve cam_id from name using ffmpeg_manager state."""
    for cid, cname in ffmpeg_manager._cam_names.items():  # type: ignore[attr-defined]
        if cname == name:
            return cid
    return None
