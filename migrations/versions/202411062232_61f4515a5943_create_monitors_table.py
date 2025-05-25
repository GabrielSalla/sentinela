"""create monitors table

Revision ID: 61f4515a5943
Revises: none
Create Date: 2024-11-06 22:32:09.701601

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "61f4515a5943"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "Monitors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), unique=True),
        sa.Column("enabled", sa.Boolean(), insert_default=True),
        sa.Column("queued", sa.Boolean(), insert_default=False),
        sa.Column("running", sa.Boolean(), insert_default=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("running_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("search_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("update_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("Monitors")
