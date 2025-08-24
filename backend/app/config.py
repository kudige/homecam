from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    MEDIA_ROOT: str = "/media"
    LIVE_SUBDIR: str = "live"
    REC_SUBDIR: str = "recordings"
    RECORDINGS_ROOT: str | None = None
    DB_PATH: str = "/data/homecam.db"
    LOG_LEVEL: str = "INFO"
    RECORDING_SEGMENT_SEC: int = 300
    DEFAULT_RETENTION_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()

MEDIA_ROOT = Path(settings.MEDIA_ROOT)
LIVE_DIR = MEDIA_ROOT / settings.LIVE_SUBDIR
if settings.RECORDINGS_ROOT:
    REC_DIR = Path(settings.RECORDINGS_ROOT)
else:
    REC_DIR = MEDIA_ROOT / settings.REC_SUBDIR

DB_PATH = Path(settings.DB_PATH)
