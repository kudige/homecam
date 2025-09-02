from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .db import Base
import datetime as dt

class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    rtsp_url = Column(String, nullable=False)  # legacy (keep for migration/back-compat)
    enabled = Column(Boolean, default=True)
    retention_days = Column(Integer, default=7)

    # Legacy encoder knobs (kept)
    low_width = Column(Integer, default=640)
    low_height = Column(Integer, default=-1)
    high_crf = Column(Integer, default=20)
    low_crf = Column(Integer, default=26)

    # NEW: preferred streams + UI targets (admin can set)
    preferred_low_stream_id = Column(Integer, ForeignKey("camera_streams.id"), nullable=True)
    preferred_high_stream_id = Column(Integer, ForeignKey("camera_streams.id"), nullable=True)
    grid_target_w = Column(Integer, default=640)    # desired grid width
    grid_target_h = Column(Integer, default=360)    # desired grid height
    full_target_w = Column(Integer, default=1920)   # desired full width
    full_target_h = Column(Integer, default=1080)   # desired full height

    streams = relationship("CameraStream", back_populates="camera", cascade="all, delete-orphan", lazy="joined")

class CameraStream(Base):
    __tablename__ = "camera_streams"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    name = Column(String, nullable=False)       # e.g. "main", "sub", "720p", "4k"
    rtsp_url = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)

    # Probed metadata
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Integer, nullable=True)
    bitrate_kbps = Column(Integer, nullable=True)
    probed_at = Column(DateTime, nullable=True)

    camera = relationship("Camera", back_populates="streams")
