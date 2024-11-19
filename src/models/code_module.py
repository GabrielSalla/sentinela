from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class CodeModule(Base):
    __tablename__ = "CodeModules"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("Monitors.id"))
    code: Mapped[str] = mapped_column(String(), nullable=True)
    additional_files: Mapped[dict[str, str]] = mapped_column(
        MutableDict.as_mutable(postgresql.JSON), nullable=True  # type: ignore[arg-type]
    )

    # Code modules won't trigger events when they are created
    _enable_creation_event: bool = False
