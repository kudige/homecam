# backend/app/models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from .db import Base
import enum, datetime as dt

class RoleMode(str, enum.Enum):
    auto = "auto"        # pick best stream; grid may scale to grid_target_* if needed
    manual = "manual"    # use selected stream; NO scaling
    disabled = "disabled"  # allowed for medium/high/recording (NOT grid)

class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    # legacy default/master URL (seed master stream on create)
    rtsp_url = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    retention_days = Column(Integer, default=7)

    # ---- ROLE CONFIG ----
    # Grid (always running) – modes: auto | manual   (no disabled)
    grid_mode  = Column(Enum(RoleMode), default=RoleMode.auto, nullable=False)
    grid_stream_id = Column(Integer, ForeignKey("camera_streams.id"), nullable=True)
    grid_target_w  = Column(Integer, default=640)    # used only in auto mode
    grid_target_h  = Column(Integer, default=360)

    # Medium (default when expanded) – modes: auto | manual | disabled
    medium_mode  = Column(Enum(RoleMode), default=RoleMode.auto, nullable=False)
    medium_stream_id = Column(Integer, ForeignKey("camera_streams.id"), nullable=True)

    # High (user toggles high) – modes: auto | manual | disabled
    high_mode  = Column(Enum(RoleMode), default=RoleMode.auto, nullable=False)
    high_stream_id = Column(Integer, ForeignKey("camera_streams.id"), nullable=True)

    # Recording (if retention>0) – modes: auto | manual | disabled
    recording_mode  = Column(Enum(RoleMode), default=RoleMode.auto, nullable=False)
    recording_stream_id = Column(Integer, ForeignKey("camera_streams.id"), nullable=True)

    # old encoder knobs (kept for CRF only)
    low_crf  = Column(Integer, default=26)
    high_crf = Column(Integer, default=20)

    # relations
    streams = relationship(
        "CameraStream",
        back_populates="camera",
        cascade="all, delete-orphan",
        foreign_keys="CameraStream.camera_id",
        lazy="joined",
    )
    grid_stream     = relationship("CameraStream", foreign_keys=[grid_stream_id],     uselist=False, post_update=True)
    medium_stream   = relationship("CameraStream", foreign_keys=[medium_stream_id],   uselist=False, post_update=True)
    high_stream     = relationship("CameraStream", foreign_keys=[high_stream_id],     uselist=False, post_update=True)
    recording_stream= relationship("CameraStream", foreign_keys=[recording_stream_id],uselist=False, post_update=True)

class CameraStream(Base):
    __tablename__ = "camera_streams"
    id = Column(Integer, primary_key=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    name = Column(String, nullable=False)     # e.g. master/main/sub/720p
    rtsp_url = Column(String, nullable=False)
    enabled  = Column(Boolean, default=True)
    is_master = Column(Boolean, default=False)  # ← set True for the seed stream

    width  = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps    = Column(Integer, nullable=True)
    bitrate_kbps = Column(Integer, nullable=True)
    probed_at = Column(DateTime, nullable=True)

    camera = relationship("Camera", back_populates="streams", foreign_keys=[camera_id])
