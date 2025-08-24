from sqlalchemy import Column, Integer, String, Boolean
from .db import Base

class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    rtsp_url = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    retention_days = Column(Integer, default=7)
    # Encoding parameters
    low_width = Column(Integer, default=640)
    low_height = Column(Integer, default=-1)  # keep aspect
    high_crf = Column(Integer, default=20)
    low_crf = Column(Integer, default=26)
