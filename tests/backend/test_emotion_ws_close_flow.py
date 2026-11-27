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
os.environ.setdefault("JWT_SECRET_KEY", "test-ws-close-secret")
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
    flow_state: dict | None = None

    def next_llm_output(self) -> str:
        if not self.llm_outputs:
            raise AssertionError("No stubbed LLM output left")
        return self.llm_outputs.pop(0)

    def next_current_step(self) -> int:
        if not self.current_steps:
            raise AssertionError("No stubbed current_step left")
        return self.current_steps.pop(0)

    def with_reserved_close_token(self, text: str) -> str:
        return f"{text.rstrip()} {emotion_ws.RESERVED_CONFIRM_CLOSE_TOKEN}".strip()


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

    def fake_prepare_message_context(_db, session_id, user_text, **kwargs):
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

    async def fakepost_action_generate_analysis_card_async(session_id):
        return {
            "card_id": str(uuid4()),
            "session_id": str(session_id),
            "summary": "analysis summary",
        }

    def fake_pick_greeting_message(_db):
        return 0, "테스트 인사말"

    def fake_commit_opening_message(_db, session_id, assistant_text):
        assert store.session is not None
        assert store.session.session_id == session_id
        store.steps.append(
            SimpleNamespace(
                session_id=session_id,
                step_order=1,
                step_type="assistant",
                user_input="",
                gpt_response=assistant_text,
                created_at=_utcnow(),
                insight_tag=None,
            )
        )

    monkeypatch.setattr(emotion_ws, "session_scope", fake_session_scope)
    monkeypatch.setattr(emotion_ws, "session_with_db", fake_with_db)
    monkeypatch.setattr(emotion_ws, "session_create_emotion_session", fake_create_emotion_session)
    monkeypatch.setattr(emotion_ws, "session_prepare_message_context", fake_prepare_message_context)
    monkeypatch.setattr(emotion_ws, "session_commit_full_turn", fake_commit_full_turn)
    monkeypatch.setattr(emotion_ws, "session_close_session_record", fake_close_session_record)
    monkeypatch.setattr(emotion_ws, "session_append_step_marker", fake_append_step_marker)
    monkeypatch.setattr(emotion_ws, "post_action_generate_analysis_card_async", fakepost_action_generate_analysis_card_async)
    monkeypatch.setattr(emotion_ws, "resolve_emotion_user_id", lambda _db, _user: store.user_id)
    monkeypatch.setattr(emotion_ws, "get_system_prompt", lambda: "system")
    monkeypatch.setattr(emotion_ws, "get_task_prompt", lambda: "task")
    monkeypatch.setattr(emotion_ws, "is_activity_turn", lambda **_kwargs: False)
    monkeypatch.setattr(emotion_ws, "stream_noa_response", fake_stream_noa_response)
    monkeypatch.setattr(emotion_ws, "greeting_pick_greeting_message", fake_pick_greeting_message)
    monkeypatch.setattr(emotion_ws, "session_commit_opening_message", fake_commit_opening_message)
    monkeypatch.setattr(emotion_ws, "session_load_flow_state", lambda _db, _sid: store.flow_state)

    def fake_save_flow_state(_db, _sid, state):
        store.flow_state = dict(state)

    monkeypatch.setattr(emotion_ws, "session_save_flow_state", fake_save_flow_state)
    monkeypatch.setattr(emotion_ws.CFG, "GREETING_DELAY_MIN_SEC", 0.0)
    monkeypatch.setattr(emotion_ws.CFG, "GREETING_DELAY_MAX_SEC", 0.0)

    app = FastAPI()
    app.include_router(emotion_ws.router)
    client = TestClient(app)
    return store, client


@contextmanager
def _open_ws(client: TestClient):
    with client.websocket_connect("/ws/emotion") as ws:
        open_event = ws.receive_json()
        assert open_event["type"] == "open_ok"
        greeting_events = [ws.receive_json() for _ in range(3)]
        assert [e["type"] for e in greeting_events] == ["message_start", "message", "message_end"]
        assert greeting_events[1]["message"] == "테스트 인사말"
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


def test_close_still_returns_close_ok_without_soft_trigger(ws_harness, monkeypatch):
    store, client = ws_harness
    store.current_steps = [3]
    store.llm_outputs = ["continue"]
    analysis_card_calls = []

    async def fakepost_action_generate_analysis_card_async(session_id):
        analysis_card_calls.append(session_id)
        return {
            "session_id": str(session_id),
            "summary": "should not be generated",
        }

    monkeypatch.setattr(emotion_ws, "post_action_generate_analysis_card_async", fakepost_action_generate_analysis_card_async)

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
    assert analysis_card_calls == []


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
        ("assistant", "", "테스트 인사말"),
        ("user", "I have been under pressure all week.", ""),
        ("assistant", "", "Thanks for sharing that."),
    ]
    assert store.session is not None
    assert store.session.ended_at is not None


def test_reserved_close_token_is_hidden_from_client_visible_message(ws_harness):
    store, client = ws_harness
    store.current_steps = [11]
    store.llm_outputs = [
        store.with_reserved_close_token("오늘은 여기까지 해도 괜찮겠어.")
    ]

    with _open_ws(client) as ws:
        events = _send_message_and_collect(
            ws,
            "이제 조금 정리된 것 같아.",
            ["message_start", "message_delta", "message_end", "message"],
        )

    assert events[1]["delta"] == "오늘은 여기까지 해도 괜찮겠어."
    assert events[3]["message"] == "오늘은 여기까지 해도 괜찮겠어."
    assert emotion_ws.RESERVED_CONFIRM_CLOSE_TOKEN not in events[1]["delta"]
    assert emotion_ws.RESERVED_CONFIRM_CLOSE_TOKEN not in events[3]["message"]
    assert [(step.step_type, step.gpt_response) for step in store.steps] == [
        ("assistant", "테스트 인사말"),
        ("user", ""),
        ("assistant", "오늘은 여기까지 해도 괜찮겠어."),
    ]


def test_message_without_reserved_close_token_does_not_auto_close_session(ws_harness):
    store, client = ws_harness
    store.current_steps = [12]
    store.llm_outputs = ["오늘은 여기까지. 얘기해줘서 고마워 즐거웠어. 조심히 들어가."]

    with _open_ws(client) as ws:
        events = _send_message_and_collect(
            ws,
            "아직은 더 말하고 싶어.",
            ["message_start", "message_delta", "message_end", "message"],
        )
        assert events[3]["message"] == "오늘은 여기까지. 얘기해줘서 고마워 즐거웠어. 조심히 들어가."
        assert store.session is not None
        assert store.session.ended_at is None
        ws.send_json({"type": "close"})
        close_event = _receive_non_step_event(ws)

    assert close_event["type"] == "close_ok"


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


# ---- 판단기(진행 메모) 연동 ----

def _enable_judge(monkeypatch, result):
    from app.backend.services.judge_service import JudgeResult  # noqa: F401

    monkeypatch.setattr(emotion_ws.CFG, "JUDGE_ENABLED", True)
    monkeypatch.setattr(emotion_ws, "get_judge_prompt", lambda: "judge-prompt")
    monkeypatch.setattr(emotion_ws, "run_judge", lambda *_a, **_k: result)


def _capture_stream(monkeypatch, output="응답"):
    seen = {}

    def fake_stream(**kwargs):
        seen["conversation"] = kwargs["conversation"]
        yield output

    monkeypatch.setattr(emotion_ws, "stream_noa_response", fake_stream)
    return seen


def test_judge_memo_is_attached_to_last_user_message_only_for_llm(ws_harness, monkeypatch):
    from app.backend.services.judge_service import JudgeResult

    store, client = ws_harness
    store.current_steps = [3]
    _enable_judge(monkeypatch, JudgeResult(read="반어", thread="언제부터인지"))
    seen = _capture_stream(monkeypatch)

    with _open_ws(client) as ws:
        _send_message_and_collect(
            ws, "아 진짜 좋네", ["message_start", "message_delta", "message_end", "message"]
        )

    last_role, last_text = seen["conversation"][-1]
    assert last_role == "user"
    assert last_text.startswith("아 진짜 좋네\n\n[진행 메모: 읽기: 반어 / 더 들어가 볼 것: 언제부터인지")
    # 메모는 DB에 저장되지 않는다.
    assert [s.user_input for s in store.steps if s.step_type == "user"] == ["아 진짜 좋네"]


def test_judge_failure_falls_back_to_no_memo(ws_harness, monkeypatch):
    ws_harness[0].current_steps = [3]
    _enable_judge(monkeypatch, None)
    seen = _capture_stream(monkeypatch)

    with _open_ws(ws_harness[1]) as ws:
        _send_message_and_collect(
            ws, "안녕", ["message_start", "message_delta", "message_end", "message"]
        )

    assert seen["conversation"][-1] == ("user", "안녕")


def test_judge_exception_does_not_break_chat(ws_harness, monkeypatch):
    ws_harness[0].current_steps = [3]
    _enable_judge(monkeypatch, None)

    def boom(*_a, **_k):
        raise RuntimeError("judge down")

    monkeypatch.setattr(emotion_ws, "run_judge", boom)
    seen = _capture_stream(monkeypatch)

    with _open_ws(ws_harness[1]) as ws:
        events = _send_message_and_collect(
            ws, "안녕", ["message_start", "message_delta", "message_end", "message"]
        )

    assert events[3]["message"] == "응답"
    assert seen["conversation"][-1] == ("user", "안녕")


def test_close_token_at_early_turn_is_suppressed_without_judge_approval(ws_harness, monkeypatch):
    from app.backend.services.judge_service import JudgeResult

    store, client = ws_harness
    store.current_steps = [3]
    _enable_judge(monkeypatch, JudgeResult(thread="x"))
    _capture_stream(monkeypatch, store.with_reserved_close_token("끝"))

    with _open_ws(client) as ws:
        _send_message_and_collect(
            ws, "안녕", ["message_start", "message_delta", "message_end", "message"]
        )

    assert store.session.ended_at is None


def test_close_token_at_early_turn_closes_when_judge_confirmed_end(ws_harness, monkeypatch):
    from app.backend.services.judge_service import JudgeResult

    store, client = ws_harness
    store.current_steps = [3]
    _enable_judge(monkeypatch, JudgeResult(end_ok="예"))
    seen = _capture_stream(monkeypatch, store.with_reserved_close_token("오늘은 여기까지"))

    with _open_ws(client) as ws:
        _send_message_and_collect(
            ws, "응 그래 고마워", ["message_start", "message_delta", "message_end", "message"]
        )
        _receive_non_step_event(ws)  # close 관련 후속 이벤트

    assert seen["conversation"][-1][1].endswith("[진행 메모: 대화 종료]")
    assert store.session.ended_at is not None


# ---- 데모 1.2 흐름(상태 저장/복원, 끝인사 종료) ----

def test_flow_state_is_saved_and_reloaded_between_turns(ws_harness, monkeypatch):
    from app.backend.services.flow_phrases import OFFER
    from app.backend.services.judge_service import JudgeResult

    store, client = ws_harness
    store.current_steps = [3, 3]
    store.flow_state = {"flow": "자유"}
    # 이미 사용자 말 3개가 오간 대화 → 이번이 4번째 말
    for i in range(3):
        store.steps.append(SimpleNamespace(step_order=2 * i + 2, step_type="user", user_input=f"u{i}", gpt_response=""))
        store.steps.append(SimpleNamespace(step_order=2 * i + 3, step_type="assistant", user_input="", gpt_response=f"a{i}"))
    results = iter([
        JudgeResult(offer=True),
        JudgeResult(accept="예", covered=("상황",), ask_item="감정", ask="그때 어땠어"),
    ])
    _enable_judge(monkeypatch, None)
    monkeypatch.setattr(emotion_ws, "run_judge", lambda *_a, **_k: next(results))
    seen_memos = []

    def fake_stream(**kwargs):
        seen_memos.append(kwargs["conversation"][-1][1])
        yield "응답"

    monkeypatch.setattr(emotion_ws, "stream_noa_response", fake_stream)

    expected = ["message_start", "message_delta", "message_end", "message"]
    with _open_ws(client) as ws:
        _send_message_and_collect(ws, "계속 속상해", expected)
        assert store.flow_state["flow"] == "제안함"
        _send_message_and_collect(ws, "응 해볼래", expected)

    assert f"이번에 할 것: {OFFER}" in seen_memos[0]
    assert seen_memos[1].endswith("[진행 메모: 물어볼 것: 그때 어땠어]")
    assert store.flow_state["flow"] == "단계"
    assert store.flow_state["asked"] == ["감정"]
    assert store.flow_state["covered"] == ["상황"]


def test_goodbye_stage_closes_session_even_without_token(ws_harness, monkeypatch):
    from app.backend.services.flow_phrases import WRAP_ORDER
    from app.backend.services.judge_service import JudgeResult

    store, client = ws_harness
    store.current_steps = [3]
    store.flow_state = {"flow": "단계", "deep_at": 1, "wrap": list(WRAP_ORDER), "wrap_idx": 4}
    _enable_judge(monkeypatch, JudgeResult(end_ok="예"))
    seen = _capture_stream(monkeypatch, "오늘 얘기해 줘서 고마워")

    with _open_ws(client) as ws:
        _send_message_and_collect(
            ws, "응 고마워", ["message_start", "message_delta", "message_end", "message"]
        )
        _receive_non_step_event(ws)

    assert seen["conversation"][-1][1].endswith("/ 대화 종료]")
    assert store.session.ended_at is not None
    assert store.flow_state["flow"] == "종료"


def test_unrequested_emoji_is_removed_from_reply(ws_harness, monkeypatch):
    from app.backend.services.judge_service import JudgeResult

    store, client = ws_harness
    store.current_steps = [3]
    _enable_judge(monkeypatch, JudgeResult(thread="t"))
    _capture_stream(monkeypatch, "그랬구나 🌊 언제부터야?")

    with _open_ws(client) as ws:
        # 오프닝 인사(step 1) 다음 첫 말 → user_order=2 → (2//2)%3 != 0 → 이모지 권하지 않음
        events = _send_message_and_collect(
            ws, "요즘 좀 그래", ["message_start", "message_delta", "message_end", "message"]
        )

    assert events[3]["message"] == "그랬구나 언제부터야?"
