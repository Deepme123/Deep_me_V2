import importlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ws.db")
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

emotion_ws = importlib.import_module("app.backend.routers.emotion_ws")


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class MemoryStore:
    user_id: object = field(default_factory=uuid4)
    session: object | None = None
    steps: list[object] = field(default_factory=list)
    llm_outputs: list[str] = field(default_factory=list)
    current_steps: list[int] = field(default_factory=list)

    def next_llm_output(self) -> str:
        if not self.llm_outputs:
            raise AssertionError("No stubbed LLM output left")
        return self.llm_outputs.pop(0)

    def next_current_step(self) -> int:
        if not self.current_steps:
            raise AssertionError("No stubbed current_step left")
        return self.current_steps.pop(0)


class FakeDB:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def get(self, model, pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "User":
            return SimpleNamespace(user_id=pk)
        if model_name == "EmotionSession":
            session = self.store.session
            if session and session.session_id == pk:
                return session
        return None


def _conversation_from_steps(steps: list[object]) -> list[tuple[str, str]]:
    convo: list[tuple[str, str]] = []
    for step in steps:
        if step.step_type == "user" and step.user_input:
            convo.append(("user", step.user_input))
        elif step.step_type == "assistant" and step.gpt_response:
            convo.append(("assistant", step.gpt_response))
    return convo


@pytest.fixture
def ws_harness(monkeypatch):
    store = MemoryStore()
    fake_db = FakeDB(store)

    @contextmanager
    def fake_session_scope():
        yield fake_db

    async def fake_with_db(fn, *args, **kwargs):
        return fn(fake_db, *args, **kwargs)

    def fake_create_emotion_session(_db, uid_val):
        store.session = SimpleNamespace(
            session_id=uuid4(),
            user_id=uid_val,
            started_at=_utcnow(),
            ended_at=None,
            emotion_label=None,
            topic=None,
            trigger_summary=None,
            insight_summary=None,
        )
        return store.session

    def fake_prepare_message_context(_db, session_id, user_text):
        assert store.session is not None
        assert store.session.session_id == session_id

        steps = list(store.steps)
        last_order = steps[-1].step_order if steps else 0
        return {
            "steps": steps,
            "want_activity": False,
            "user_order": last_order + 1,
            "assistant_order": last_order + 2,
            "conversation": _conversation_from_steps(steps) + [("user", user_text)],
            "current_step": store.next_current_step(),
            "step_context": "",
            "end_session_context": "",
            "soft_timeout_hint": "",
        }

    def fake_commit_full_turn(
        _db,
        session_id,
        user_text,
        assistant_text,
        user_order,
        assistant_order,
        *,
        add_activity_marker,
    ):
        assert store.session is not None
        assert store.session.session_id == session_id
        assert add_activity_marker is False
        store.steps.append(
            SimpleNamespace(
                session_id=session_id,
                step_order=user_order,
                step_type="user",
                user_input=user_text,
                gpt_response="",
                created_at=_utcnow(),
                insight_tag=None,
            )
        )
        store.steps.append(
            SimpleNamespace(
                session_id=session_id,
                step_order=assistant_order,
                step_type="assistant",
                user_input="",
                gpt_response=assistant_text,
                created_at=_utcnow(),
                insight_tag=None,
            )
        )

    def fake_close_session_record(_db, session_id, payload):
        assert store.session is not None
        assert store.session.session_id == session_id
        store.session.ended_at = _utcnow()
        store.session.emotion_label = payload.emotion_label
        store.session.topic = payload.topic
        store.session.trigger_summary = payload.trigger_summary
        store.session.insight_summary = payload.insight_summary

    def fake_append_step_marker(_db, session_id, step_type):
        assert store.session is not None
        assert store.session.session_id == session_id
        last_order = store.steps[-1].step_order if store.steps else 0
        store.steps.append(
            SimpleNamespace(
                session_id=session_id,
                step_order=last_order + 1,
                step_type=step_type,
                user_input="",
                gpt_response="",
                created_at=_utcnow(),
                insight_tag=None,
            )
        )

    def fake_stream_noa_response(**_kwargs):
        yield store.next_llm_output()

    async def fake_generate_analysis_card_async(session_id):
        return {
            "card_id": str(uuid4()),
            "session_id": str(session_id),
            "summary": "analysis summary",
        }

    monkeypatch.setattr(emotion_ws, "session_scope", fake_session_scope)
    monkeypatch.setattr(emotion_ws, "_with_db", fake_with_db)
    monkeypatch.setattr(emotion_ws, "_create_emotion_session", fake_create_emotion_session)
    monkeypatch.setattr(emotion_ws, "_prepare_message_context", fake_prepare_message_context)
    monkeypatch.setattr(emotion_ws, "_commit_full_turn", fake_commit_full_turn)
    monkeypatch.setattr(emotion_ws, "_close_session_record", fake_close_session_record)
    monkeypatch.setattr(emotion_ws, "_append_step_marker", fake_append_step_marker)
    monkeypatch.setattr(emotion_ws, "_generate_analysis_card_async", fake_generate_analysis_card_async)
    monkeypatch.setattr(emotion_ws, "resolve_emotion_user_id", lambda _db, _user: store.user_id)
    monkeypatch.setattr(emotion_ws, "get_system_prompt", lambda: "system")
    monkeypatch.setattr(emotion_ws, "get_task_prompt", lambda: "task")
    monkeypatch.setattr(emotion_ws, "is_activity_turn", lambda **_kwargs: False)
    monkeypatch.setattr(emotion_ws, "stream_noa_response", fake_stream_noa_response)

    app = FastAPI()
    app.include_router(emotion_ws.router)
    client = TestClient(app)
    return store, client


@contextmanager
def _open_ws(client: TestClient):
    with client.websocket_connect("/ws/emotion") as ws:
        open_event = ws.receive_json()
        assert open_event["type"] == "open_ok"
        yield ws


def _send_message_and_collect(ws, text: str, expected_types: list[str]) -> list[dict]:
    ws.send_json({"type": "message", "text": text})
    events = []
    while len(events) < len(expected_types):
        event = ws.receive_json()
        if event["type"] == "step":
            continue
        events.append(event)
    assert [event["type"] for event in events] == expected_types
    return events


def _receive_non_step_event(ws) -> dict:
    while True:
        event = ws.receive_json()
        if event["type"] == "step":
            continue
        return event


def test_step_11_message_does_not_auto_close_session(ws_harness):
    store, client = ws_harness
    store.current_steps = [11]
    store.llm_outputs = ["LLM freeform close response"]

    with _open_ws(client) as ws:
        events = _send_message_and_collect(
            ws,
            "I think this is enough for now.",
            ["message_start", "message_delta", "message_end", "message"],
        )
        ws.send_json({"type": "close"})
        close_event = _receive_non_step_event(ws)

    assert events[1]["delta"] == "LLM freeform close response"
    assert events[3]["message"] == "LLM freeform close response"
    assert close_event["type"] == "close_ok"
    assert store.session is not None
    assert store.session.ended_at is not None


def test_close_still_returns_close_ok_without_soft_trigger(ws_harness):
    store, client = ws_harness
    store.current_steps = [3]
    store.llm_outputs = ["continue"]

    with _open_ws(client) as ws:
        events = _send_message_and_collect(
            ws,
            "Let's keep talking.",
            ["message_start", "message_delta", "message_end", "message"],
        )
        assert events[3]["message"] == "continue"
        ws.send_json({"type": "close"})
        close_event = _receive_non_step_event(ws)

    assert close_event["type"] == "close_ok"
    assert store.session is not None
    assert store.session.ended_at is not None


def test_manual_close_keeps_transcript_turns_committed(ws_harness):
    store, client = ws_harness
    store.current_steps = [3]
    store.llm_outputs = ["Thanks for sharing that."]

    with _open_ws(client) as ws:
        events = _send_message_and_collect(
            ws,
            "I have been under pressure all week.",
            ["message_start", "message_delta", "message_end", "message"],
        )
        assert events[3]["message"] == "Thanks for sharing that."

        ws.send_json({"type": "close"})
        close_event = _receive_non_step_event(ws)

    assert close_event["type"] == "close_ok"
    assert [(step.step_type, step.user_input, step.gpt_response) for step in store.steps] == [
        ("user", "I have been under pressure all week.", ""),
        ("assistant", "", "Thanks for sharing that."),
    ]
    assert store.session is not None
    assert store.session.ended_at is not None


def test_cancel_close_ack_keeps_session_open_for_followup_messages(ws_harness):
    store, client = ws_harness
    store.current_steps = [11, 11]
    store.llm_outputs = [
        "keep going a bit more",
        "still open",
    ]

    with _open_ws(client) as ws:
        ws.send_json({"type": "cancel_close"})
        cancel_event = ws.receive_json()
        assert cancel_event["type"] == "cancel_close_ok"

        continue_turn_1 = _send_message_and_collect(
            ws,
            "Not yet.",
            ["message_start", "message_delta", "message_end", "message"],
        )
        assert continue_turn_1[3]["message"] == "keep going a bit more"

        continue_turn_2 = _send_message_and_collect(
            ws,
            "One more thing.",
            ["message_start", "message_delta", "message_end", "message"],
        )
        assert continue_turn_2[3]["message"] == "still open"
        ws.send_json({"type": "close"})
        close_event = _receive_non_step_event(ws)
        assert close_event["type"] == "close_ok"

    assert any(
        step.step_type == emotion_ws.CANCEL_CLOSE_STEP_TYPE
        for step in store.steps
    )
