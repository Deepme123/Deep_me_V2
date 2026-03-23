# LLM Call Sites

This document lists the active LLM call sites after the step-tracker removal.

The current design is transcript-first:

- live conversation responses are generated from the system prompt, optional
  task prompt, and recent transcript turns
- analysis cards are generated from the stored session transcript
- no route appends step-specific prompt fragments

## 1. WebSocket Conversation

File:
- `app/backend/routers/emotion_ws.py`

Call:
- `stream_noa_response(...)`

Inputs:
- `system_prompt = get_system_prompt()`
- optional `task_prompt = get_task_prompt()` when activity recommendation logic
  is active
- `conversation`, built from recent stored user and assistant transcript rows
  plus the pending user message

Notes:
- websocket message handling no longer emits or depends on a `step` payload
- the websocket route no longer appends step context, end-session context, or
  soft-timeout hint text to the system prompt
- session close now depends on explicit `close` or `confirm_close`, not on step
  progress

## 2. REST Emotion Generate

File:
- `app/backend/routers/emotion.py`

Call:
- `generate_noa_response(...)`

Inputs:
- `system_prompt = get_system_prompt()`
- optional `task_prompt = get_task_prompt()` when activity recommendation logic
  is active
- `conversation`, built from the stored transcript rows and the incoming user
  input

Notes:
- this route no longer augments the prompt with step-derived text
- this route no longer swaps in a step-based farewell or auto-finalizes the
  session
- any end-session marker token is stripped from the raw model output before the
  response is stored

## 3. Analysis Card Extraction

Files:
- `app/analyze/routers/cards.py`
- `app/analyze/services/llm_card.py`

Call:
- `analyze_dialogue_to_card(...)`

Inputs:
- conversation turns loaded from persisted session transcript rows
- optional `title_hint`

Notes:
- marker rows such as activity or cancel-close do not contribute content unless
  they contain actual transcript text
- card generation is grounded in stored transcript content, not in step labels
  or inferred stage metadata

## 4. Task Recommendation

File:
- `app/backend/services/task_recommend.py`

This flow does not call the main conversation LLM directly in this module, but
it still builds its context from recent transcript rows stored in the emotion
session.

## 5. Removed Step-Specific Prompting

The following behavior is intentionally gone:

- websocket prompt augmentation with current-step metadata
- websocket prompt augmentation with end-session instructions
- websocket prompt augmentation with soft-timeout hints
- REST prompt augmentation with step-derived guidance

The remaining source of truth for both generation and analysis is the
transcript.
