from pydantic import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    MEDIA_ROOT: str = "/media"
    LIVE_SUBDIR: str = "live"
    REC_SUBDIR: str = "recordings"
    DB_PATH: str = "/data/homecam.db"
    LOG_LEVEL: str = "INFO"
    # Recording chunk length in seconds
    RECORDING_SEGMENT_SEC: int = 300
    # Default per-camera retention in days
    DEFAULT_RETENTION_DAYS: int = 7

    class Config:
        env_file = ".env"

settings = Settings()

MEDIA_ROOT = Path(settings.MEDIA_ROOT)
LIVE_DIR = MEDIA_ROOT / settings.LIVE_SUBDIR
REC_DIR = MEDIA_ROOT / settings.REC_SUBDIR
DB_PATH = Path(settings.DB_PATH)
