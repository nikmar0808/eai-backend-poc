"""The transactional outbox: one row per ReadingsStored event, written in the readings' own transaction.

Revision ID: 0004_outbox
Revises: 0003_idempotency_key

The column names are the ones Debezium's outbox event router reads by default (POC 4, Stage 3): id, aggregatetype,
aggregateid, type, payload. Keeping the defaults means the connector needs no column mapping.
"""

import sqlalchemy as sa                        # SQLAlchemy's column types (sa.Uuid, sa.String, ...) and functions (sa.func)
from alembic import op                         # Alembic's DDL operations: op.create_table, op.create_index, op.drop_table
from sqlalchemy.dialects import postgresql     # types that only PostgreSQL has, here JSONB

# The four names Alembic reads to place this file in the chain of migrations (like numbered release SQL scripts,
# but Alembic records in the table alembic_version which ones a database has already run).
revision = "0004_outbox"                       # this migration's own name
down_revision = "0003_idempotency_key"         # the one that must have run before it: the chain is 0001 -> ... -> 0004
branch_labels = None                           # not used in this project: one straight line of migrations
depends_on = None                              # not used: no dependency outside that line


def upgrade() -> None:
    """Run by `alembic upgrade head` (the db-migrate job, and the tests' conftest.py)."""
    op.create_table(                           # CREATE TABLE outbox (...)
        "outbox",
        # uuid type, primary key. The value is made by the service (uuid4) and is also the payload's event_id.
        sa.Column("id", sa.Uuid(), primary_key=True),
        # Always 'meter-readings'. Debezium uses it to choose the Kafka topic (Stage 3).
        sa.Column("aggregatetype", sa.String(255), nullable=False),
        # The meter ID. Debezium makes it the Kafka key, so one meter's events stay in order.
        sa.Column("aggregateid", sa.String(255), nullable=False),
        # Always 'ReadingsStored'. Debezium puts it in a Kafka header called "type".
        sa.Column("type", sa.String(255), nullable=False),
        # The event itself, as parsed JSON (jsonb). Becomes the Kafka message's value.
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        # When the row was written. server_default: the database fills it with now() when the insert gives no value.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Rows are kept for a day, then deleted by scripts/outbox-clean-up.sql, which finds old rows by this column.
    op.create_index("outbox_created_ix", "outbox", ["created_at"])     # CREATE INDEX outbox_created_ix ON outbox (created_at)


def downgrade() -> None:
    """Run by `alembic downgrade 0003_idempotency_key`: undoes upgrade(). test_migrations.py runs it on a scratch database."""
    op.drop_table("outbox")                    # DROP TABLE removes the table's index with it
