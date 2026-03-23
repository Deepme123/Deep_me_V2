# Env Provider Migration Guide

## Purpose
- Prevent operator mistakes while switching the LLM provider.
- Make rollback to OpenAI immediate and explicit.
- Keep `.env` changes aligned with the current code path.

## How Env Loading Works
- The app loads the root `.env` at startup.
- LLM settings also try to load both root `.env` and `app/.env`.
- Recommended rule: use the root `.env` as the single source of truth.
- After editing `.env`, restart the application process so the new values are applied.

## Required Keys
```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=800
LLM_TIMEOUT_SEC=60
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=
```

## Recommended Baseline
Start from [`.env.example`](C:\Users\user\Desktop\Deep_me_V2\.env.example).

Recommended safe baseline:
```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=800
LLM_TIMEOUT_SEC=60
LLM_BACKUP_MODELS=gpt-4o-mini,gpt-4o
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=
```

## Switch To Anthropic
Claude is opt-in. Do not switch by changing only the model name.

1. Add a valid Anthropic key.
2. Change `LLM_PROVIDER` from `openai` to `anthropic`.
3. Set `LLM_MODEL` to a Claude model name.
4. Restart the application.
5. Run the normal health and smoke checks before sending production traffic.

Example:
```dotenv
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=800
LLM_TIMEOUT_SEC=60
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

## Immediate Rollback To OpenAI
If any issue appears in production, revert to OpenAI by changing the provider first.

Emergency rollback:
```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your-openai-api-key
```

Recommended full rollback state:
```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=800
LLM_TIMEOUT_SEC=60
LLM_BACKUP_MODELS=gpt-4o-mini,gpt-4o
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

Notes:
- The key rollback control is `LLM_PROVIDER=openai`.
- Keep `OPENAI_API_KEY` present even during Anthropic rollout so rollback is immediate.
- Leaving `ANTHROPIC_API_KEY` in place is acceptable; it is ignored when `LLM_PROVIDER=openai`.
- Restart the app after rollback so the reverted env is reloaded.

## OpenAI Return Checklist
- `LLM_PROVIDER=openai`
- `LLM_MODEL` is set to the intended OpenAI model
- `OPENAI_API_KEY` is present and valid
- Process was restarted after the `.env` edit
- Health check and one real text/stream/json smoke path succeed

## Desire Service Note
- `NEED_CARD_MODEL` is optional and affects only the desire service model selection.
- If `NEED_CARD_MODEL` is not set, the desire service uses `LLM_MODEL`.
- Provider selection still follows `LLM_PROVIDER`.

## Operator Rules
- Do not split provider settings between root `.env` and `app/.env`.
- Do not switch providers by changing only `LLM_MODEL`.
- Do not remove `OPENAI_API_KEY` during Anthropic opt-in if fast rollback matters.
- For incidents, prioritize `LLM_PROVIDER=openai` before tuning any other variable.
