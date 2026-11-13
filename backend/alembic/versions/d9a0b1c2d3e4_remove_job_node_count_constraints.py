"""remove user-facing job Node-count constraints

Revision ID: d9a0b1c2d3e4
Revises: c7e8f9a0b1c2
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9a0b1c2d3e4"
down_revision: str | Sequence[str] | None = "c7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("job", "max_nodes")
    op.drop_column("job", "min_nodes")


def downgrade() -> None:
    op.add_column("job", sa.Column("min_nodes", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("job", sa.Column("max_nodes", sa.Integer(), nullable=True))
    op.alter_column("job", "min_nodes", server_default=None)
