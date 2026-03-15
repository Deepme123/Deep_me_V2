# Run Rules

## Basics
- Always run from the project root.
- Use the `app` package entrypoint.
- Configure LLM env values from the root `.env`. See `docs/env-provider-migration.md` for provider switch and rollback steps.

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
