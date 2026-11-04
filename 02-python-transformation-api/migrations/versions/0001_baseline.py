"""The table as Base.metadata.create_all built it, before Alembic took over.

Two kinds of database reach this file: an empty one, which gets the table; and one already in use, built by the old
start-up code, which already has it. The check makes this file safe for both, so that nobody has to run
`alembic stamp` by hand on an existing database.

Revision ID: 0001_baseline
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("smart_meter_intervals"):
        return
    op.create_table(
        "smart_meter_intervals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("meter_id", sa.String(20), nullable=False),
        sa.Column("grid_zone", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("kwh_value", sa.Float(), nullable=False),
        sa.Column("voltage", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_smart_meter_intervals_id", "smart_meter_intervals", ["id"])
    op.create_index("ix_smart_meter_intervals_meter_id", "smart_meter_intervals", ["meter_id"])


def downgrade() -> None:
    op.drop_table("smart_meter_intervals")