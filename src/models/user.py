import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.time import now

from .base import Base


class UserRole(enum.Enum):
    admin = "admin"
    user = "user"


class User(Base):
    __tablename__ = "Users"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    password_salt: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False), insert_default=UserRole.user
    )
    require_change_password: Mapped[bool] = mapped_column(
        Boolean(), insert_default=True, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean(), insert_default=True, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer(), insert_default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), insert_default=now)

    # Users won't trigger events, they have no 'monitor_id'
    _enable_creation_event: bool = False

    @property
    def is_admin(self) -> bool:
        """Return whether the user has the admin role"""
        return self.role == UserRole.admin
