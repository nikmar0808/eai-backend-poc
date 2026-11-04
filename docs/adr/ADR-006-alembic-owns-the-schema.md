# ADR-006: Alembic owns the schema; the service no longer creates tables at start-up

- Status: Accepted
- Date: 3 November 2026

## Context

`python-validator` called `Base.metadata.create_all` when it was imported. That can create a missing table, but it can
never change one that exists. So the table could not move to `timestamptz`, gain a unique rule or lose a duplicate
index, and there was no record of what any database had been through. It also meant that importing the module needed
a database, and that every copy of the service tried to create tables as it started.

## Decision

1. Alembic owns the tables. Every change is a numbered file in `02-python-transformation-api/migrations/versions/`.
2. `create_all` is removed. The tests build their database with the same migrations, and `alembic check` fails if a
   model class and the migrations disagree.
3. Migrations run as a separate step before the service starts: in Compose, the one-shot service `db-migrate`, on which
   `python-validator` depends. A pipeline would run the same command before it deploys.
4. Revision `0001_baseline` adopts a database built by the old code, by checking whether the table exists, so that no
   database needs a manual `alembic stamp`.

## Alternatives considered

- **Run migrations when the service starts.** Simple, and common; but several copies starting together race each other,
  and the service's account would need rights to change tables.
- **Flyway, as `db-lab` uses.** Works, but this table belongs to the Python service, whose models Alembic can compare
  with the database. One set of tables has one migration tool.
- **Keep `create_all`, and alter by hand.** The drift this decision exists to end.

## Consequences

- A service started against a database that has not been migrated answers `/health` normally, and fails on its first
  write. Compose's dependency prevents this locally; a pipeline must run the migration first.
- The upgrade locks the table while the column type changes, so this release takes a short outage. A table too large
  for that would use expand and contract instead: add a new column, write both, copy in batches, switch, drop the old.
- In this project the migration and the service use one database account. Production gives the migration an owner
  account, and the service one that may only read and write data, as the `db-lab` accounts do.
- `downgrade()` restores the structure, but not the duplicate rows the upgrade removed.