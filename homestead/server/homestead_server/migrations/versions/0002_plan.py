"""Garden plan: background, spaces drawn, other objects, plant layouts.

Revision ID: 0002
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    """Add the plan."""
    with op.batch_alter_table("garden") as table:
        table.add_column(sa.Column("plan_width", sa.Float))
        table.add_column(sa.Column("plan_height", sa.Float))
        table.add_column(sa.Column("background", sa.String(40)))
        table.add_column(sa.Column("background_width", sa.Integer))
        table.add_column(sa.Column("background_height", sa.Integer))
        table.add_column(sa.Column("background_scale", sa.Float))
        table.add_column(
            sa.Column(
                "background_opacity", sa.Float, nullable=False, server_default="0.6"
            )
        )
    with op.batch_alter_table("space") as table:
        table.add_column(sa.Column("x", sa.Float))
        table.add_column(sa.Column("y", sa.Float))
        table.add_column(sa.Column("width", sa.Float))
        table.add_column(sa.Column("height", sa.Float))
        table.add_column(
            sa.Column("rotation", sa.Float, nullable=False, server_default="0")
        )
        table.add_column(
            sa.Column("shape", sa.String(10), nullable=False, server_default="rect")
        )
    with op.batch_alter_table("planting") as table:
        table.add_column(sa.Column("layout", sa.String(12)))
        table.add_column(sa.Column("region_x", sa.Float))
        table.add_column(sa.Column("region_y", sa.Float))
        table.add_column(sa.Column("region_width", sa.Float))
        table.add_column(sa.Column("region_height", sa.Float))
        table.add_column(sa.Column("spacing", sa.Float))
        table.add_column(sa.Column("row_spacing", sa.Float))
        table.add_column(
            sa.Column("direction", sa.String(1), nullable=False, server_default="h")
        )
        table.add_column(sa.Column("points", sa.Text))
    op.create_table(
        "plan_item",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("x", sa.Float, nullable=False),
        sa.Column("y", sa.Float, nullable=False),
        sa.Column("width", sa.Float, nullable=False),
        sa.Column("height", sa.Float, nullable=False),
        sa.Column("rotation", sa.Float, nullable=False),
        sa.Column("sort", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    """Not supported: restore a backup instead."""
    raise NotImplementedError
