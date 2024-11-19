import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.utils.time import now


class NotificationStatus(enum.Enum):
    active = "active"
    closed = "closed"


class Notification(Base):
    __tablename__ = "Notifications"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("Monitors.id"))
    alert_id: Mapped[int] = mapped_column(ForeignKey("Alerts.id"))
    target: Mapped[str] = mapped_column(String(255))
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, native_enum=False), insert_default=NotificationStatus.active
    )
    data: Mapped[dict[Any, Any]] = mapped_column(
        MutableDict.as_mutable(postgresql.JSON), nullable=True  # type: ignore[arg-type]
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), insert_default=now)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    async def close(self):
        self.status = NotificationStatus.closed
        self.closed_at = now()

        await self.save()

        await self._create_event("notification_closed")
        self._logger.debug("Closed")
