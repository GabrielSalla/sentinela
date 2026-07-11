from datetime import datetime
from typing import Any, Type, TypeVar

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from internal_database import get_session
from utils.time import now

ClassType = TypeVar("ClassType")


class Base(AsyncAttrs, DeclarativeBase):
    __allow_unmapped__ = True


class Event(Base):
    __tablename__ = "Events"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    # Not using foreign key because the base class is not the same for the 'Monitors' table
    monitor_id: Mapped[int] = mapped_column(Integer())
    source: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[int] = mapped_column(Integer())
    data: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(postgresql.JSONB)  # type: ignore[arg-type]
    )
    extra_payload: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(postgresql.JSONB)  # type: ignore[arg-type]
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), insert_default=now)

    @classmethod
    async def create(cls: Type[ClassType], **attributes: Any) -> ClassType:
        """Create an event in the database with the provided attributes"""
        async with get_session() as session:
            instance = cls(**attributes)
            session.add(instance)
            await session.commit()

        return instance
