"""create users table

Revision ID: 3c4d5e6f7a8b
Revises: 1a2b3c4d5e6f
Create Date: 2026-09-06 00:00:00.000000

"""
import enum
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3c4d5e6f7a8b"
down_revision: Union[str, None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    class UserRole(enum.Enum):
        admin = "admin"
        user = "user"

    op.create_table(
        "Users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=True),
        sa.Column("password_salt", sa.String(64), nullable=True),
        sa.Column("role", sa.Enum(UserRole, native_enum=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("require_change_password", sa.Boolean(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_Users_username",
        "Users",
        ["username"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_Users_username")
    op.drop_table("Users")
