import time, shutil
from pathlib import Path
from sqlalchemy.orm import Session
from .models import Camera
from .config import REC_DIR, settings

# Run daily to delete old recordings per-camera

def run_retention_loop(get_session_func):
    while True:
        try:
            with get_session_func() as db:
                _apply_retention(db)
        except Exception:
            pass
        time.sleep(24 * 3600)


def _apply_retention(db: Session):
    cams = db.query(Camera).all()
    now = time.time()
    for cam in cams:
        days = cam.retention_days or settings.DEFAULT_RETENTION_DAYS
        cut = now - days * 86400
        cam_dir = REC_DIR / cam.name
        if not cam_dir.exists():
            continue
        for date_dir in sorted(cam_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            # Parse date folder YYYY-MM-DD
            try:
                ts = time.mktime(time.strptime(date_dir.name, "%Y-%m-%d"))
            except Exception:
                continue
            if ts < cut:
                shutil.rmtree(date_dir, ignore_errors=True)
