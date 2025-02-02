"""create code modules table

Revision ID: 247390255aee
Revises: c628330bb96e
Create Date: 2024-11-18 12:08:24.441692

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "247390255aee"
down_revision: Union[str, None] = "c628330bb96e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "CodeModules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("monitor_id", sa.Integer(), unique=True),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("additional_files", sa.JSON, nullable=True),

        sa.ForeignKeyConstraint(("monitor_id",), ["Monitors.id"]),
    )


def downgrade() -> None:
    op.drop_table("CodeModules")
