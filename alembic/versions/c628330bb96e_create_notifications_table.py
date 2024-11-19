"""create notifications table

Revision ID: c628330bb96e
Revises: 8382681faa0c
Create Date: 2024-11-06 22:57:02.478632

"""
import enum
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c628330bb96e'
down_revision: Union[str, None] = '8382681faa0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    class NotificationStatus(enum.Enum):
        active = "active"
        closed = "closed"

    op.create_table(
        "Notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("monitor_id", sa.Integer()),
        sa.Column("alert_id", sa.Integer(), nullable=True),
        sa.Column("target", sa.String(255)),
        sa.Column("status", sa.Enum(NotificationStatus, native_enum=False)),
        sa.Column("data", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),

        sa.UniqueConstraint("alert_id", "target", name="Notifications_alert_id_target_key")
    )
    op.create_index(
        "ix_Notifications_monitor_id_alert_id_target_status_active",
        "Notifications",
        ["monitor_id", "alert_id", "target"],
        postgresql_where="status = 'active'",
    )


def downgrade() -> None:
    op.drop_table("Notifications")
