"""Weather entity whose forecast warns of frost.

Revision ID: 0003
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    """Add the weather entity."""
    with op.batch_alter_table("garden") as table:
        table.add_column(sa.Column("weather_entity", sa.String(255)))


def downgrade() -> None:
    """Not supported: restore a backup instead."""
    raise NotImplementedError
