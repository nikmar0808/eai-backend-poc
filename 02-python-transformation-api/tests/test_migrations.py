"""
What this file protects. Alembic now owns the table, so three things must stay true: the migrations build what the
model classes describe, an existing database with old rows is converted correctly, and a migration can be undone.

New ideas.
- `alembic check` compares the model classes with the real tables, and fails on any difference. It is the guard against
  a class changed without a migration.
- A scratch database. These tests run real DDL, which must not touch the rolling-back test database, so they create a
  database of their own, and drop it at the end. `isolation_level="AUTOCOMMIT"`: PostgreSQL refuses CREATE DATABASE
  inside a transaction.
- `Config.attributes` passes a Python object to migrations/env.py, here the scratch database's address.
"""
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, exc, inspect, text

pytestmark = pytest.mark.db

ALEMBIC_INI = str(Path(__file__).resolve().parents[1] / "alembic.ini")
OLD_ROW = """
    INSERT INTO smart_meter_intervals (meter_id, grid_zone, "timestamp", kwh_value, voltage, created_at)
    VALUES (:meter, 'ZONE-A', :at, :kwh, NULL, '2026-10-09 00:00:00')
"""


def alembic_config(url) -> Config:
    config = Config(ALEMBIC_INI)
    config.attributes["url"] = url
    return config


@pytest.fixture()
def scratch(engine: Engine) -> Iterator[tuple[Config, Engine]]:
    """An empty database of its own, removed at the end, with an Alembic configuration aimed at it."""
    name = f"{engine.url.database}_migrations"
    admin = create_engine(engine.url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    url = engine.url.set(database=name)
    database = create_engine(url)
    try:
        yield alembic_config(url), database
    finally:
        database.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def test_the_models_match_the_migrations(engine):
    command.check(alembic_config(engine.url))       # raises an error if a class and a table differ


def test_old_rows_become_exact_moments_and_duplicates_go(scratch):
    config, database = scratch
    command.upgrade(config, "0001_baseline")
    with database.begin() as connection:
        connection.execute(text(OLD_ROW), {"meter": "MTR-OLD-1", "at": "2026-10-09 05:30:00", "kwh": 1.0})
        connection.execute(text(OLD_ROW), {"meter": "MTR-OLD-1", "at": "2026-10-09 05:30:00", "kwh": 2.0})   # a duplicate
        connection.execute(text(OLD_ROW), {"meter": "MTR-OLD-2", "at": "2026-10-09 05:30:00", "kwh": 3.0})   # another meter

    command.upgrade(config, "head")

    with database.connect() as connection:
        rows = connection.execute(text(
            'SELECT meter_id, "timestamp", kwh_value, created_at FROM smart_meter_intervals ORDER BY meter_id'
        )).all()
    midnight_utc = datetime(2026, 10, 9, 0, 0, tzinfo=timezone.utc)   # 05:30 India time was this moment
    assert [(r.meter_id, r.timestamp, r.kwh_value) for r in rows] == [
        ("MTR-OLD-1", midnight_utc, 1.0),                             # the first of the two stays
        ("MTR-OLD-2", midnight_utc, 3.0),
    ]
    assert rows[0].created_at == midnight_utc                         # created_at was already UTC


def test_the_rule_refuses_a_second_reading_for_the_same_moment(scratch):
    config, database = scratch
    command.upgrade(config, "head")
    insert = text("""INSERT INTO smart_meter_intervals (meter_id, grid_zone, "timestamp", kwh_value)
                     VALUES ('MTR-RULE-1', 'ZONE-A', '2026-10-09T00:00:00Z', 1.0)""")
    with database.begin() as connection:
        connection.execute(insert)
    with pytest.raises(exc.IntegrityError), database.begin() as connection:
        connection.execute(insert)


def test_the_duplicate_indexes_are_gone(scratch):
    config, database = scratch
    command.upgrade(config, "head")
    names = {index["name"] for index in inspect(database).get_indexes("smart_meter_intervals")}
    assert "ix_smart_meter_intervals_id" not in names
    assert "ix_smart_meter_intervals_meter_id" not in names


def test_an_existing_table_is_adopted_not_rebuilt(scratch):
    config, database = scratch
    command.upgrade(config, "0001_baseline")
    with database.begin() as connection:
        connection.execute(text("DELETE FROM alembic_version"))       # as if the old start-up code had built the table
        connection.execute(text(OLD_ROW), {"meter": "MTR-OLD-3", "at": "2026-10-09 05:30:00", "kwh": 1.0})

    command.upgrade(config, "head")                                    # finds the table, and carries on

    with database.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM smart_meter_intervals")).scalar_one() == 1


def test_the_migrations_can_be_undone_and_done_again(scratch):
    config, database = scratch
    command.upgrade(config, "head")
    command.downgrade(config, "0001_baseline")
    columns = {column["name"]: column for column in inspect(database).get_columns("smart_meter_intervals")}
    assert columns["timestamp"]["type"].timezone is False              # back to the old type
    command.upgrade(config, "head")
    command.check(config)