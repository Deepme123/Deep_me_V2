# Repository Structure

This repository now separates backend-owned QA surfaces from product-facing web UI.

## Top-level layout

- `app/backend`: FastAPI application, routers, models, services, and QA demo serving
- `app/backend/demo_ui`: HTML/CSS/JS assets for the internal websocket regression demo
- `app/backend/resources`: backend-only text resources such as prompts
- `app/analyze`: analysis service package
- `app/desire`: desire and need-analysis service package
- `frontend`: product-facing web UI workspace
- `tests`: automated test suite
- `docs`: product, API, and implementation notes

## Frontend boundary

`frontend/` is where new web UI should land.

- `frontend/apps/beta`: public beta experience
- `frontend/apps/admin`: operator and master monitoring pages
- `frontend/shared`: code shared across frontend apps

## QA demo boundary

The existing HTML websocket demo is intentionally preserved and served from FastAPI:

- route: `/demo/emotion-analysis`
- files: `app/backend/demo_ui/pages/` and `app/backend/demo_ui/assets/`

That keeps conversation and analysis-card testing stable while the beta and admin
surfaces are built separately.
