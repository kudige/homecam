from pathlib import Path
import os, time, re
from typing import List
from .config import REC_DIR

# Filenames look like: YYYY-MM-DD_HH-MM-SS.mp4
FNAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})\.mp4$")

def list_recordings(camera: str, date_str: str) -> List[dict]:
    base = REC_DIR / camera / date_str
    if not base.exists():
        return []
    items = []
    for hour_dir, _, files in os.walk(base):
        for f in files:
            if not f.endswith(".mp4"):
                continue
            if not FNAME_RE.search(f):
                continue
            full = Path(hour_dir) / f
            try:
                ts = time.mktime(time.strptime(FNAME_RE.search(f).group(0).replace('.mp4',''), "%Y-%m-%d_%H-%M-%S"))
            except Exception:
                ts = full.stat().st_mtime
            items.append({
                "path": str(full).replace(str(REC_DIR.parent), ""),  # make it relative from /media
                "start_ts": ts,
                "size_bytes": full.stat().st_size,
            })
    items.sort(key=lambda x: x["start_ts"])
    return items
