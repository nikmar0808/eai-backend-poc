"""How Alembic connects (POC 3, Stage 8). Called by every alembic command.

The address comes from DATABASE_URL, the variable the service itself reads. A test can pass another database in
config.attributes["url"], which is how test_migrations.py works on a scratch database.
target_metadata is the model classes: `alembic check` compares them with the real tables and reports any difference.
"""

import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.database.models import Base

if context.is_offline_mode():
    raise RuntimeError("Offline mode (writing SQL to a file) is not used in this project.")

url = context.config.attributes.get("url") or os.environ["DATABASE_URL"]
# NullPool: open one connection, use it, close it. A migration is a short job, and needs no pool.
engine = create_engine(url, poolclass=pool.NullPool)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():      # one transaction per run: a failed migration leaves nothing half-done
        context.run_migrations()
engine.dispose()