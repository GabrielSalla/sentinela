"""create issues table

Revision ID: 8382681faa0c
Revises: a0e61ac09d4c
Create Date: 2024-11-06 22:48:33.179508

"""
import enum
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8382681faa0c"
down_revision: Union[str, None] = "a0e61ac09d4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    class IssueStatus(enum.Enum):
        active = "active"
        dropped = "dropped"
        solved = "solved"

    op.create_table(
        "Issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("monitor_id", sa.Integer()),
        sa.Column("alert_id", sa.Integer(), nullable=True),
        sa.Column("model_id", sa.String(255)),
        sa.Column("status", sa.Enum(IssueStatus, native_enum=False)),
        sa.Column("data", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("solved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dropped_at", sa.DateTime(timezone=True), nullable=True),

        sa.ForeignKeyConstraint(("monitor_id",), ["Monitors.id"]),
        sa.ForeignKeyConstraint(("alert_id",), ["Alerts.id"]),
    )
    op.create_index(
        "ix_Issues_monitor_id_model_id",
        "Issues",
        ["monitor_id", "model_id"],
    )
    op.create_index(
        "ix_Issues_monitor_id_status_active",
        "Issues",
        ["monitor_id"],
        postgresql_where="status = 'active'",
    )
    op.create_index(
        "ix_Issues_alert_id_status_active",
        "Issues",
        ["alert_id"],
        postgresql_where="status = 'active'",
    )


def downgrade() -> None:
    op.drop_table("Issues")
