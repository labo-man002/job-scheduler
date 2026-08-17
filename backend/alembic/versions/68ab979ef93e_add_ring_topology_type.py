"""add ring topology type

Revision ID: 68ab979ef93e
Revises: 11123a617a98
Create Date: 2026-08-11 19:27:48.121039

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68ab979ef93e'
down_revision: Union[str, Sequence[str], None] = '11123a617a98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE topology_type ADD VALUE 'RING'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no `ALTER TYPE ... DROP VALUE` — removing an enum value means
    # recreating the type, which isn't safe to do blindly if any cluster row
    # already uses RING. Not implemented; drop manually if this needs reverting.
    raise NotImplementedError("Removing an enum value requires manually recreating topology_type")
