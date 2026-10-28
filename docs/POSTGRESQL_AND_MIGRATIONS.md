# PostgreSQL and migrations

The application reads `DATABASE_URL` first and accepts
`YOTTAFLEX_DATABASE_URL` for backwards compatibility. Use the SQLAlchemy URL
format for the installed driver:

```text
postgresql+psycopg2://cold_chain_app:<password>@localhost:5432/cold_chain_dev
```

Set the value in the process environment or in a local `.env` file based on
[`.env.example`](../.env.example). Never commit the local `.env` file.

## Alembic commands

From the repository root:

```powershell
$env:DATABASE_URL = "postgresql+psycopg2://cold_chain_app:<password>@localhost:5432/cold_chain_dev"
python -m alembic current
python -m alembic upgrade head
```

The initial revision is
`91f9897bb752_initial_complete_schema.py`. It includes all current entities,
constraints, indexes, and the `excursion_evidence` table.

Do not use `create_schema()` for production migration management. It remains
available for SQLite tests and local isolated fixtures.

## Bounded persistence benchmark

The benchmark compares the legacy ORM `add_all` path with ordered SQLAlchemy
bulk inserts without disabling foreign keys or constraints:

```powershell
python -m backend.scripts.benchmark_persistence --shipments 25
```

The benchmark uses temporary SQLite databases and never touches the retained
full-scale verification artifacts.
