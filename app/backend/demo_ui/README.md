# Backend Demo UI

This directory holds QA-only web assets that are still served directly by FastAPI.

Why it exists:

- keeps the websocket regression demo available at `/demo/emotion-analysis`
- separates QA UI assets from prompt and backend resource files
- leaves room for the product-facing React apps to grow under `frontend/`
