"""Persist paired replay experiment runs."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "f5a6b7c8d9e0"
down_revision: str | Sequence[str] | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "replay_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("display_name", sa.String(120), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("workload_label", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("gpus_per_node", JSONB(), nullable=False),
        sa.Column("inputs", JSONB(), nullable=False),
        sa.Column("outputs", JSONB(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_replay_runs_newest", "replay_runs", [sa.text("created_at DESC"), sa.text("id DESC")])


def downgrade() -> None:
    op.drop_index("ix_replay_runs_newest", table_name="replay_runs")
    op.drop_table("replay_runs")
