import enum
from datetime import datetime

from sqlalchemy import UUID, DateTime, Enum, Integer, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from utils.time import now

from .base import Base


class EventType(enum.Enum):
    monitor_execution_error = "monitor_execution_error"
    monitor_execution_success = "monitor_execution_success"


class Event(Base):
    __tablename__ = "Events"

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, native_enum=False))
    model: Mapped[str] = mapped_column(String())
    model_id: Mapped[str] = mapped_column(Integer())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), insert_default=now)
    payload: Mapped[dict[str, str]] = mapped_column(
        MutableDict.as_mutable(postgresql.JSON)  # type: ignore[arg-type]
    )

    # Events won't trigger events when they are created
    _enable_creation_event: bool = False
