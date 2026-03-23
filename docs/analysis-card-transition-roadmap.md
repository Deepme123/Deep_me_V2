# Analysis Card Transition Roadmap

## Purpose

This document fixes the scope for removing step-tracking behavior from the
emotion session flow while keeping transcript-based analysis card generation
working end to end.

The immediate goal is not to redesign the whole conversation model. The goal is
to make the system behave correctly after step tracking is removed.

## In Scope

- Remove the websocket `step` event from the external contract.
- Remove step-specific rendering from the demo UI.
- Remove step-based prompt augmentation in websocket and REST routes.
- Remove step-based automatic close behavior.
- Rename local helper variables from `step` semantics to transcript or turn
  semantics where that reflects the real role.
- Isolate close-related constants that must survive the step-manager removal.
- Delete `step_manager.py` after its remaining responsibilities have been moved
  or removed.
- Keep analysis card generation grounded in the stored transcript.

## Keep As Is For This Work

- `EmotionStep` database model and related persisted rows.
- `step_order` and `step_type` columns.
- Existing transcript persistence for user and assistant turns.
- Manual close paths such as `close` and `confirm_close`.
- Transcript-based analysis card creation after the session ends.
- Existing task recommendation flow unless it is directly coupled to removed
  step logic.

## Explicit Non-Goals

- Do not delete `EmotionStep`.
- Do not remove `step_order` or `step_type` columns.
- Do not introduce a brand new automatic close policy.
- Do not redesign the analysis card schema.
- Do not change unrelated LLM provider or health-check behavior.
- Do not rewrite unrelated UI or database flows.

## Expected End State

- The client no longer depends on a current step or step event.
- Prompts are based on the shared system prompt and transcript, not on
  step-manager context injection.
- Session close behavior is driven by explicit close actions, not by
  inferred step progress.
- Analysis cards still generate from the stored transcript after close.
- There are no live references to `step_manager` in the application code.

## Recommended Delivery Split

### PR 1

- Baseline tests
- Scope documentation
- Remove step expectations from websocket contract tests
- Remove step rendering from the demo UI
- Stop sending websocket `step` events

### PR 2

- Remove step fields from websocket message preparation
- Remove step prompt augmentation in websocket flow
- Remove step prompt augmentation in REST flow
- Disable step-based auto close in websocket flow
- Align REST generate behavior with manual-close-only policy

### PR 3

- Rename local helpers away from step semantics where possible
- Move surviving close constants out of `step_manager`
- Delete `step_manager.py`
- Rewrite docs around transcript-based analysis
- Add transcript-first regression coverage
