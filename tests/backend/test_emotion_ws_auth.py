import importlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ws_auth.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-ws-auth-secret")
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

emotion_ws = importlib.import_module("app.backend.routers.emotion_ws")


class FakeDB:
    def __init__(self) -> None:
        self.session = None

    def get(self, model, pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "User":
            return SimpleNamespace(user_id=pk)
        if model_name == "EmotionSession" and self.session and self.session.session_id == pk:
            return self.session
        return None


def test_websocket_accepts_access_token_cookie(monkeypatch):
    fake_db = FakeDB()
    user_id = uuid4()
    session_id = uuid4()

    @contextmanager
    def fake_session_scope():
        yield fake_db

    async def fake_with_db(fn, *args, **kwargs):
        return fn(fake_db, *args, **kwargs)

    def fake_create_emotion_session(_db, uid_val):
        fake_db.session = SimpleNamespace(
            session_id=session_id,
            user_id=uid_val,
            started_at=None,
            ended_at=None,
            emotion_label=None,
            topic=None,
            trigger_summary=None,
            insight_summary=None,
        )
        return fake_db.session

    def fake_pick_greeting_message(_db):
        return 0, "테스트 인사말"

    def fake_commit_opening_message(_db, session_id_arg, assistant_text):
        assert fake_db.session is not None
        assert fake_db.session.session_id == session_id_arg

    monkeypatch.setattr(emotion_ws, "session_scope", fake_session_scope)
    monkeypatch.setattr(emotion_ws, "session_with_db", fake_with_db)
    monkeypatch.setattr(emotion_ws, "session_create_emotion_session", fake_create_emotion_session)
    monkeypatch.setattr(
        emotion_ws,
        "protocol_decode_user_id_from_token",
        lambda token: user_id if token == "cookie-token" else None,
    )
    monkeypatch.setattr(emotion_ws, "get_system_prompt", lambda: "system")
    monkeypatch.setattr(
        emotion_ws,
        "get_backend_llm_info",
        lambda: SimpleNamespace(provider="test", model="fake"),
    )
    monkeypatch.setattr(emotion_ws, "greeting_pick_greeting_message", fake_pick_greeting_message)
    monkeypatch.setattr(emotion_ws, "session_commit_opening_message", fake_commit_opening_message)
    monkeypatch.setattr(emotion_ws.CFG, "GREETING_DELAY_MIN_SEC", 0.0)
    monkeypatch.setattr(emotion_ws.CFG, "GREETING_DELAY_MAX_SEC", 0.0)

    app = FastAPI()
    app.include_router(emotion_ws.router)
    client = TestClient(app)

    with client.websocket_connect(
        "/ws/emotion",
        headers={"cookie": "access_token=cookie-token"},
    ) as ws:
        open_event = ws.receive_json()
        greeting_events = [ws.receive_json() for _ in range(3)]

    assert open_event["type"] == "open_ok"
    assert open_event["session_id"] == str(session_id)
    assert [e["type"] for e in greeting_events] == ["message_start", "message", "message_end"]
    assert greeting_events[1]["message"] == "테스트 인사말"

