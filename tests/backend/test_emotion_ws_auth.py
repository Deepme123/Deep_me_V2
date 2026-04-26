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

    monkeypatch.setattr(emotion_ws, "session_scope", fake_session_scope)
    monkeypatch.setattr(emotion_ws, "_with_db", fake_with_db)
    monkeypatch.setattr(emotion_ws, "_create_emotion_session", fake_create_emotion_session)
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

    app = FastAPI()
    app.include_router(emotion_ws.router)
    client = TestClient(app)

    with client.websocket_connect(
        "/ws/emotion",
        headers={"cookie": "access_token=cookie-token"},
    ) as ws:
        open_event = ws.receive_json()

    assert open_event["type"] == "open_ok"
    assert open_event["session_id"] == str(session_id)

