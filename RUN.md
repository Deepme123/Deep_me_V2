# Run Rules

## Basics
- Always run from the project root.
- Use the `app` package entrypoint.

## Official Commands
```bash
uvicorn app.main:app --reload
```

```bash
python -m app.main
```

## Windows Git Bash
```bash
uvicorn app.main:app --reload --port 8000
```

## Render Rollout
- Keep the web service start command on `uvicorn app.main:app`.
- Run Alembic before the web process starts. Use a Render release/pre-deploy command equivalent to:

```bash
alembic upgrade head
```

### Existing Production Database
- The current production database already contains the base tables and is missing only `emotioncard`.
- To onboard that database into Alembic safely, take a DB backup first.
- Stamp the database to the base revision, then upgrade to head:

```bash
alembic stamp 0001_base_schema
alembic upgrade head
```

### New Databases
- For a fresh database, do not stamp anything manually.
- Run only:

```bash
alembic upgrade head
```

### Render Shell Notes
- `psql` does not accept SQLAlchemy URLs with the `postgresql+psycopg2://` prefix.
- Convert the scheme before connecting in Render Shell:

```bash
psql "${DATABASE_URL/postgresql+psycopg2/postgresql}"
```
