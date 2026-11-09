"""store leaf-spine NIC metadata on physical compute nodes

Revision ID: a1b2c3d4e5f6
Revises: ded4d84ae440
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "ded4d84ae440"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    operational_state = postgresql.ENUM("UP", "DOWN", name="operational_state")
    operational_state.create(op.get_bind(), checkfirst=True)

    op.add_column("node", sa.Column("nic_capacity_gbps", sa.Float(), nullable=True))
    op.add_column(
        "node",
        sa.Column("nic_state", operational_state, nullable=False, server_default="UP"),
    )
    op.alter_column("node", "nic_state", server_default=None)


def downgrade() -> None:
    op.drop_column("node", "nic_state")
    op.drop_column("node", "nic_capacity_gbps")
    postgresql.ENUM("UP", "DOWN", name="operational_state").drop(op.get_bind(), checkfirst=True)
