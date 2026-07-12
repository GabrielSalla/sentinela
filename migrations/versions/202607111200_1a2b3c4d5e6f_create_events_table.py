"""create events table

Revision ID: 1a2b3c4d5e6f
Revises: 845d74ade448
Create Date: 2026-07-11 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as postgresql
from alembic import op

revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "845d74ade448"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "Events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(128)),
        sa.Column("monitor_id", sa.Integer()),
        sa.Column("source", sa.String(32)),
        sa.Column("source_id", sa.Integer()),
        sa.Column("data", postgresql.JSONB),
        sa.Column("extra_payload", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True)),

        sa.ForeignKeyConstraint(("monitor_id",), ["Monitors.id"]),
    )
    op.create_index(
        "ix_Events_monitor_id",
        "Events",
        ["monitor_id"],
    )
    op.create_index(
        "ix_Events_source_source_id",
        "Events",
        ["source", "source_id"],
    )
    op.create_index(
        "ix_Events_created_at",
        "Events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_Events_monitor_id")
    op.drop_index("ix_Events_source_source_id")
    op.drop_index("ix_Events_created_at")
    op.drop_table("Events")
