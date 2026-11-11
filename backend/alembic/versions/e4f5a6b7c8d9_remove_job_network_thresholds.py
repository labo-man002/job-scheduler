"""remove Job-level network thresholds

Revision ID: e4f5a6b7c8d9
Revises: d9a0b1c2d3e4
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: str | Sequence[str] | None = "d9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("job", "max_latency_us")
    op.drop_column("job", "min_bandwidth_gbps")
    op.drop_column("job", "require_full_connectivity")


def downgrade() -> None:
    op.add_column("job", sa.Column("require_full_connectivity", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("job", sa.Column("min_bandwidth_gbps", sa.Float(), nullable=True))
    op.add_column("job", sa.Column("max_latency_us", sa.Float(), nullable=True))
    op.alter_column("job", "require_full_connectivity", server_default=None)
