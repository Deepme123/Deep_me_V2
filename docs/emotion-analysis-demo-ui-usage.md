# Emotion Analysis Demo UI Usage

This page documents the internal demo screen at:

`/demo/emotion-analysis`

The page is meant to inspect transcript-oriented websocket behavior, not step
progress.

## What The Demo Shows

- connection state and `session_id`
- the conversation transcript in a readable feed
- raw websocket events
- analysis card payloads when the backend sends `analysis_card_ready`
- stored cards loaded back from the analyze API

The page no longer shows a "last step" indicator and does not render `step`
events.

## Basic Flow

1. Open the page.
2. Connect to `/ws/emotion`.
3. Send one or more messages.
4. Watch the transcript and raw event log update.
5. Close the session or load stored cards for the current session.

## Important Event Meanings

- `open_ok`: the websocket session is ready
- `message_start`: assistant streaming started
- `message_delta`: streamed assistant fragment
- `message_end`: assistant streaming finished
- `message`: final assistant message for the turn
- `close_ok`: the session close was persisted
- `analysis_card_ready`: transcript-based card generation succeeded
- `analysis_card_failed`: the session closed, but card generation failed

## Current Close Behavior

The backend is manual-close-first.

- sending `close` closes the session
- sending `confirm_close` closes the session and triggers card generation

The current demo page includes a `close` action. If you need to exercise live
`analysis_card_ready` over websocket, use a websocket client that can send
`confirm_close`, or verify saved cards through the analyze API after the
appropriate close flow.

## Recommended Checks

### Transcript Check

After each message, confirm:

- the user text appears in the conversation feed
- the assistant response appears in the conversation feed
- the raw event log shows message lifecycle events

### Close Check

After sending a close action, confirm:

- `close_ok` appears in the event log
- the connection state changes to closed

### Card Check

When card generation is part of the close flow, confirm:

- `analysis_card_ready` appears in the event log
- the card panel renders the returned card
- the stored card list can be loaded again by `session_id`

## Useful Commands

```bash
uvicorn app.main:app --reload
```

```bash
pytest tests/backend/test_demo_router.py tests/backend/test_emotion_ws_close_flow.py tests/backend/test_emotion_ws_analysis_trigger.py
```
