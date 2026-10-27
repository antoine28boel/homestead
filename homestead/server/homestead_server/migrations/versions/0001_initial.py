"""Garden, spaces, plantings, journal, harvests and to-do list.

Revision ID: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None


def upgrade() -> None:
    """Create the first tables."""
    op.create_table(
        "garden",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("last_frost", sa.String(5), nullable=False),
        sa.Column("first_frost", sa.String(5), nullable=False),
    )
    op.create_table(
        "space",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("frost_shift", sa.Integer),
        sa.Column("area", sa.Float),
        sa.Column("sort", sa.Integer, nullable=False),
        sa.Column("archived", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "planting",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("season", sa.Integer, nullable=False, index=True),
        sa.Column(
            "space_id", sa.String(32), sa.ForeignKey("space.id", ondelete="SET NULL")
        ),
        sa.Column("species", sa.String(50), nullable=False, index=True),
        sa.Column("variety", sa.String(100), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("window", sa.Integer, nullable=False),
        sa.Column("quantity", sa.Integer),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("sown_on", sa.Date),
        sa.Column("transplanted_on", sa.Date),
        sa.Column("growing_on", sa.Date),
        sa.Column("harvesting_on", sa.Date),
        sa.Column("finished_on", sa.Date),
        sa.Column("notes", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "journal",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "planting_id",
            sa.String(32),
            sa.ForeignKey("planting.id", ondelete="CASCADE"),
            index=True,
        ),
        sa.Column(
            "space_id",
            sa.String(32),
            sa.ForeignKey("space.id", ondelete="SET NULL"),
            index=True,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("day", sa.Date, nullable=False, index=True),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("amount", sa.Float),
        sa.Column("unit", sa.String(20)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "harvest",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "planting_id",
            sa.String(32),
            sa.ForeignKey("planting.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("day", sa.Date, nullable=False, index=True),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "task_state",
        sa.Column("uid", sa.String(100), primary_key=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "todo_item",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("due", sa.Date),
        sa.Column("description", sa.Text),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    """Not supported: restore a backup instead."""
    raise NotImplementedError
