import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ExecutionStatus(enum.Enum):
    success = "success"
    failed = "failed"


class MonitorExecution(Base):
    __tablename__ = "MonitorExecutions"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("Monitors.id"))
    status: Mapped[ExecutionStatus] = mapped_column(Enum(ExecutionStatus, native_enum=False))
    error_type: Mapped[str] = mapped_column(String(), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
