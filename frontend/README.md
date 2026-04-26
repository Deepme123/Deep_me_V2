# Frontend Workspace

This directory is reserved for product-facing web UI work that should live outside
the FastAPI package.

Current layout:

- `apps/beta`: public beta tester experience
- `apps/admin`: operator and master monitoring pages
- `shared`: shared UI utilities, types, and design primitives

The existing QA demo remains server-rendered at `/demo/emotion-analysis` and is
kept under `app/backend/demo_ui/` so websocket and analysis-card regression checks
can continue without waiting for the product UI migration.
