# Deep_me_V2

FastAPI-based backend for the DeepMe conversation, desire, and analysis flows.

This repository currently contains:

- a unified FastAPI entrypoint at `app.main`
- the emotion conversation backend and websocket flow
- analysis-card and desire-related backend packages
- an internal QA demo UI served by FastAPI
- a reserved `frontend/` workspace for the upcoming beta and admin web apps

## Current scope

The backend serves three main areas:

- `app/backend`: core API, auth, websocket, tasks, and QA demo routing
- `app/analyze`: analysis-card and summary-related services
- `app/desire`: need and desire analysis services

The existing HTML websocket demo remains available at `/demo/emotion-analysis`.
It is kept for conversation and analysis-card regression testing while the
product-facing web UI grows separately under `frontend/`.

## Project layout

```text
Deep_me_V2/
  app/
    backend/
      demo_ui/
      resources/
    analyze/
    desire/
  frontend/
    apps/
      beta/
      admin/
    shared/
  tests/
  docs/
```

More detail is documented in [docs/repo-structure.md](docs/repo-structure.md).

## Requirements

- Python 3.11+
- pip
- environment variables in the project root `.env`

Main Python dependencies are listed in `requirements.txt`.

## Setup

```bash
pip install -r requirements.txt
```

Create a root `.env` file based on `.env.example` and configure the required
database and LLM provider values before running the app.

## Run

Always run from the project root.

```bash
uvicorn app.main:app --reload
```

Or:

```bash
python -m app.main
```

Useful routes:

- `GET /health`
- `GET /health/db`
- `GET /demo/emotion-analysis`
- `WS /ws/emotion`

## Database migrations

This project uses Alembic.

For a fresh database:

```bash
alembic upgrade head
```

For the existing production database noted in `RUN.md`, stamp the base revision
before upgrading:

```bash
alembic stamp 0001_base_schema
alembic upgrade head
```

## Tests

Run the full suite:

```bash
pytest
```

Run the QA demo router tests only:

```bash
pytest tests/backend/test_demo_router.py -q
```

## Frontend note

`frontend/` is intentionally a separate workspace boundary for the future
product-facing UI:

- `frontend/apps/beta`: public beta tester experience
- `frontend/apps/admin`: operator and master monitoring pages
- `frontend/shared`: shared frontend code

The current internal QA demo is still served directly from FastAPI and is not a
React app.

## Deployment note

The current Render backend start command should remain:

```bash
uvicorn app.main:app
```

Run migrations before the web process starts:

```bash
alembic upgrade head
```
