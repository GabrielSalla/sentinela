from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.time import now

from .base import Base


class Variable(Base):
    __tablename__ = "Variables"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("Monitors.id"))
    name: Mapped[str] = mapped_column(String())
    value: Mapped[str | None] = mapped_column(String(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), insert_default=now)

    async def set(self, value: str | None) -> None:
        """Set the variable value"""
        self.value = value
        self.updated_at = now()
        await self.save()
