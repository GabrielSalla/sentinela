from datetime import datetime
from typing import Sequence

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CodeModule(Base):
    __tablename__ = "CodeModules"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("Monitors.id"))
    code: Mapped[str] = mapped_column(String(), nullable=True)
    additional_files: Mapped[dict[str, str]] = mapped_column(
        MutableDict.as_mutable(postgresql.JSON),  # type: ignore[arg-type]
        nullable=True,
    )
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Code modules won't trigger events when they are created
    _enable_creation_event: bool = False

    @classmethod
    async def get_updated_code_modules(
        cls: type["CodeModule"],
        monitors_ids: list[int],
        reference_timestamp: datetime | None,
    ) -> Sequence["CodeModule"]:
        """Get all code modules that were updated after a reference timestamp"""
        if not monitors_ids:
            return []

        if reference_timestamp is None:
            return await cls.get_all(cls.monitor_id.in_(monitors_ids))

        return await cls.get_all(
            cls.monitor_id.in_(monitors_ids),
            cls.registered_at > reference_timestamp,
        )

    @Base.lock_change
    async def register(self, code: str, additional_files: dict[str, str] | None = None) -> None:
        """Register a code module with the given code and additional files"""
        self.code = code
        self.additional_files = additional_files or {}
        self.registered_at = datetime.now()
        await self.save()
