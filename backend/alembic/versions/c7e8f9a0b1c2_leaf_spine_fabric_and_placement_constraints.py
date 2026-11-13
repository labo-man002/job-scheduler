"""persist leaf-spine fabric and job placement constraints

Revision ID: c7e8f9a0b1c2
Revises: a1b2c3d4e5f6
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE topology_type ADD VALUE IF NOT EXISTS 'LEAF_SPINE'")
    op.add_column("cluster", sa.Column("fabric_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("job", sa.Column("min_nodes", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("job", sa.Column("max_nodes", sa.Integer(), nullable=True))
    op.add_column("job", sa.Column("require_full_connectivity", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("job", sa.Column("min_bandwidth_gbps", sa.Float(), nullable=True))
    op.add_column("job", sa.Column("max_latency_us", sa.Float(), nullable=True))
    op.alter_column("job", "min_nodes", server_default=None)
    op.alter_column("job", "require_full_connectivity", server_default=None)


def downgrade() -> None:
    op.drop_column("job", "max_latency_us")
    op.drop_column("job", "min_bandwidth_gbps")
    op.drop_column("job", "require_full_connectivity")
    op.drop_column("job", "max_nodes")
    op.drop_column("job", "min_nodes")
    op.drop_column("cluster", "fabric_config")
    # PostgreSQL enum values cannot be removed safely in-place. LEAF_SPINE
    # remains an unused enum label after downgrade.
