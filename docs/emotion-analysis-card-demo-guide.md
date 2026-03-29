# Emotion Analysis Card Demo Guide

This guide explains how to present the current transcript-based analysis flow.

## Goal

Show three things clearly:

1. user and assistant turns are stored as a transcript
2. session close is explicit
3. analysis cards are derived from that stored transcript

## Core Story

The product is no longer organized around conversation steps.

The simpler explanation is:

- the user talks
- the service stores the transcript
- when the model finishes with the reserved close token, the backend
  auto-closes the session and turns the stored transcript into the input for
  analysis card generation

## What To Demonstrate

### A. Transcript Accumulation

Use the websocket flow to show:

- `open_ok`
- `message_start`
- `message_delta`
- `message_end`
- `message`

The important point is not a hidden internal stage. The important point is that
the transcript keeps growing in a stable format.

### B. Token-Driven Session Close

The current backend can still close explicitly, but the main demo flow is now
token-driven.

- `close` still finalizes the session manually
- `[[CONFIRM_CLOSE]]` at the end of the model response is stripped from the
  visible text and automatically triggers the same close-and-analyze path

This lets the demo stay transcript-first: the model decides it is time to wrap
up, but the reserved token never appears in the UI transcript.

### C. Transcript-Based Card Generation

The card service reads the stored transcript rows and extracts:

- situation
- emotion
- thoughts
- physical reactions
- behaviors
- summary and insight

The card is not built from a step label. It is built from the conversation
content.

## Suggested Presenter Script

### Opening

"This demo shows how a session transcript turns into an analysis card after the
session is automatically closed by the reserved wrap-up token."

### During Conversation

"The right side shows the raw websocket events, and the conversation feed shows
the human-readable transcript."

### At Close

"The close event finalizes the session. When the close path includes
`[[CONFIRM_CLOSE]]`, the backend hides that token from the UI and uses the
stored transcript to generate the card."

### At Card Output

"The result is not a stage summary. It is a transcript-derived analysis card."

## Good Verification Paths

### Path 1: WebSocket Contract

Run:

```bash
pytest tests/backend/test_emotion_ws_close_flow.py tests/backend/test_emotion_ws_analysis_trigger.py
```

This verifies:

- transcript turns are committed
- manual close still returns `close_ok`
- reserved-token close produces `analysis_card_ready` or `analysis_card_failed`

### Path 2: Card Extraction Contract

Run:

```bash
pytest tests/analyze/test_cards_from_session.py tests/analyze/test_llm_card.py
```

This verifies:

- cards can be created directly from stored session transcript rows
- transcript-only content is passed into card extraction
- non-dialogue markers do not define the card structure

## What To Avoid Saying

Avoid describing the system as:

- a step-driven interview
- a stage machine that decides what the card means
- a flow where reaching the last step is what creates the card
- a UI where the reserved close token is shown to the user

Those descriptions are no longer true.
