"""create alerts table

Revision ID: a0e61ac09d4c
Revises: 61f4515a5943
Create Date: 2024-11-06 22:36:12.797822

"""
import enum
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a0e61ac09d4c"
down_revision: Union[str, None] = "61f4515a5943"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    class AlertStatus(enum.Enum):
        active = "active"
        solved = "solved"

    op.create_table(
        "Alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("monitor_id", sa.Integer()),
        sa.Column("status", sa.Enum(AlertStatus, native_enum=False)),
        sa.Column("acknowledged", sa.Boolean()),
        sa.Column("locked", sa.Boolean()),
        sa.Column("priority", sa.Integer()),
        sa.Column("acknowledge_priority", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("solved_at", sa.DateTime(timezone=True), nullable=True),

        sa.ForeignKeyConstraint(("monitor_id",), ["Monitors.id"]),
    )
    op.create_index(
        "ix_Alerts_monitor_id_status_active",
        "Alerts",
        ["monitor_id"],
        postgresql_where="status = 'active'",
    )


def downgrade() -> None:
    op.drop_table("Alerts")
