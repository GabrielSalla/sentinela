"""create_monitor_executions_table

Revision ID: 845d74ade448
Revises: ce56a57ff560
Create Date: 2025-10-18 18:36:13.571779-03:00

"""
import enum
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "845d74ade448"
down_revision: Union[str, None] = "ce56a57ff560"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    class ExecutionStatus(enum.Enum):
        success = "success"
        failed = "failed"

    op.create_table(
        "MonitorExecutions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("monitor_id", sa.Integer()),
        sa.Column("status", sa.Enum(ExecutionStatus, native_enum=False)),
        sa.Column("error_type", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),

        sa.ForeignKeyConstraint(("monitor_id",), ["Monitors.id"]),
    )
    op.create_index(
        "ix_MonitorExecutions_monitor_id_started_at",
        "MonitorExecutions",
        ["monitor_id", "started_at"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_MonitorExecutions_monitor_id_started_at")
    op.drop_table("MonitorExecutions")
