"""Device database model (push tokens)."""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.infra.db.base import Base


class DeviceModel(Base):
    """User device for push notifications."""

    __tablename__ = "devices"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    push_token = Column(String, nullable=False, unique=True)
    platform = Column(String, nullable=False)  # 'ios' or 'android'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("UserModel", backref="devices")
