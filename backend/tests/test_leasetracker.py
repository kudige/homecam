import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from backend.app.ffmpeg_manager import LeaseTracker

def test_mark_activity_resets_idle():
    lt = LeaseTracker()
    cam_id, role = 1, "medium"
    lease_id = lt.acquire(cam_id, role)
    lt.release(cam_id, role, lease_id)
    # ensure some measurable idle time
    assert lt.idle_for(cam_id, role) >= 0
    lt.mark_activity(cam_id, role)
    assert lt.idle_for(cam_id, role) == 0
