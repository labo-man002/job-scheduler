"""make quota period timezone-aware

Revision ID: 3e8ecad270d2
Revises: ded4d84ae440
Create Date: 2026-08-22 00:54:42.203821

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3e8ecad270d2'
down_revision: str | Sequence[str] | None = 'ded4d84ae440'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # postgresql_using pins the reinterpretation to UTC explicitly -- without it,
    # Postgres's default TIMESTAMP->TIMESTAMPTZ cast uses the session's *current*
    # TimeZone setting (not necessarily UTC) to decide what an existing naive value
    # meant, silently shifting every pre-existing quota.period even though the app
    # (Server._check_quota/_month_bounds) always treats these as UTC already.
    op.alter_column('quota', 'period',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False,
               postgresql_using="period AT TIME ZONE 'UTC'")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('quota', 'period',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=False,
               postgresql_using="period AT TIME ZONE 'UTC'")
