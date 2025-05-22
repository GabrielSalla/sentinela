"""create variables table

Revision ID: ce56a57ff560
Revises: 247390255aee
Create Date: 2025-05-23 21:08:54.608578

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ce56a57ff560"
down_revision: Union[str, None] = "247390255aee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "Variables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("monitor_id", sa.Integer()),
        sa.Column("name", sa.String()),
        sa.Column("value", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True)),

        sa.ForeignKeyConstraint(("monitor_id",), ["Monitors.id"]),
    )
    op.create_index(
        "ix_Variables_monitor_id_name",
        "Variables",
        ["monitor_id", "name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_Variables_monitor_id_name")
    op.drop_table("Variables")
