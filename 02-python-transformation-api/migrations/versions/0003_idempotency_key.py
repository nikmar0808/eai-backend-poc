"""What a client's Idempotency-Key produced: the key, a fingerprint of its request, and the answer given.

Revision ID: 0003_idempotency_key
Revises: 0002_reading_rules
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_idempotency_key"
down_revision = "0002_reading_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_key",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Keys are kept for a limited time. A clean-up job deletes old ones by this column (docs/api/README.md).
    op.create_index("idempotency_key_created_ix", "idempotency_key", ["created_at"])


def downgrade() -> None:
    op.drop_table("idempotency_key")