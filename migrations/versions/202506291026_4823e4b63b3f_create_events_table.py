"""create events table

Revision ID: 4823e4b63b3f
Revises: ce56a57ff560
Create Date: 2025-06-29 10:26:26.959173-03:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4823e4b63b3f'
down_revision: Union[str, None] = 'ce56a57ff560'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "Events",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("event_type", sa.String()),
        sa.Column("model", sa.String()),
        sa.Column("model_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("payload", sa.JSON),
    )
    op.create_index(
        "ix_Events_event_type_model_model_id",
        "Events",
        ["event_type", "model", "model_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_Events_event_type_model_model_id")
    op.drop_table("Events")
