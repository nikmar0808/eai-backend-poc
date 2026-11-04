"""Exact moments, one reading per meter per moment, and the index the readings query needs.

The whole file runs in one transaction, so a failure leaves the table as it was. The order matters: duplicates must
go before the unique rule can be added.

Revision ID: 0002_reading_rules
Revises: 0001_baseline
"""

from alembic import op

revision = "0002_reading_rules"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Of each group with the same meter and moment, keep the row that arrived first (the lowest id).
    op.execute("""
        DELETE FROM smart_meter_intervals later
        USING smart_meter_intervals earlier
        WHERE later.meter_id = earlier.meter_id
          AND later."timestamp" = earlier."timestamp"
          AND later.id > earlier.id
    """)
    # The old column held India wall-clock time, because the database session's time zone was Asia/Kolkata. Saying so
    # here turns each value into the exact moment it was. created_at was written by the old code in UTC.
    op.execute("""
        ALTER TABLE smart_meter_intervals
            ALTER COLUMN "timestamp" TYPE timestamptz USING "timestamp" AT TIME ZONE 'Asia/Kolkata',
            ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC',
            ALTER COLUMN created_at SET DEFAULT now()
    """)
    op.execute("UPDATE smart_meter_intervals SET created_at = now() WHERE created_at IS NULL")
    op.alter_column("smart_meter_intervals", "created_at", nullable=False)
    # The rule, and also the index: PostgreSQL builds a unique rule on an index of (meter_id, timestamp), which the
    # readings query walks backwards. That makes both old indexes unnecessary.
    op.create_unique_constraint(
        "smart_meter_intervals_meter_time_uk", "smart_meter_intervals", ["meter_id", "timestamp"]
    )
    op.drop_index("ix_smart_meter_intervals_meter_id", table_name="smart_meter_intervals")
    op.drop_index("ix_smart_meter_intervals_id", table_name="smart_meter_intervals")     # a copy of the primary key's


def downgrade() -> None:
    # Puts the structure back. The duplicates that upgrade() deleted cannot come back.
    op.create_index("ix_smart_meter_intervals_id", "smart_meter_intervals", ["id"])
    op.create_index("ix_smart_meter_intervals_meter_id", "smart_meter_intervals", ["meter_id"])
    op.drop_constraint("smart_meter_intervals_meter_time_uk", "smart_meter_intervals", type_="unique")
    op.execute("""
        ALTER TABLE smart_meter_intervals
            ALTER COLUMN created_at DROP NOT NULL,
            ALTER COLUMN created_at DROP DEFAULT,
            ALTER COLUMN created_at TYPE timestamp USING created_at AT TIME ZONE 'UTC',
            ALTER COLUMN "timestamp" TYPE timestamp USING "timestamp" AT TIME ZONE 'Asia/Kolkata'
    """)