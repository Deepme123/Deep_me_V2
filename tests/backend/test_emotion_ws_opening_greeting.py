import importlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

os.environ.setdefault("JWT_SECRET_KEY", "test-ws-opening-greeting-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-ws-opening-greeting-refresh")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

emotion_ws = importlib.import_module("app.backend.routers.emotion_ws")
ws_session_service = importlib.import_module("app.backend.services.ws_session_service")
greeting_service = importlib.import_module("app.backend.services.greeting_service")
greeting_loader = importlib.import_module("app.backend.core.greeting_loader")
user_model = importlib.import_module("app.backend.models.user")
GreetingMessageStat = importlib.import_module(
    "app.backend.models.greeting_message"
).GreetingMessageStat
EmotionStep = importlib.import_module("app.backend.models.emotion").EmotionStep


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def ws_app(engine, monkeypatch):
    with Session(engine) as setup_db:
        user = user_model.User(name="tester", email=f"{uuid4()}@example.com")
        setup_db.add(user)
        setup_db.commit()
        setup_db.refresh(user)
        user_id = user.user_id

        for index in range(len(greeting_loader.get_greeting_messages())):
            setup_db.add(GreetingMessageStat(message_index=index, selected_count=0))
        setup_db.commit()

    @contextmanager
    def fake_session_scope():
        with Session(engine) as db:
            yield db

    monkeypatch.setattr(emotion_ws, "session_scope", fake_session_scope)
    monkeypatch.setattr(ws_session_service, "session_scope", fake_session_scope)
    monkeypatch.setattr(
        emotion_ws, "protocol_decode_user_id_from_token", lambda token: user_id if token == "test-token" else None
    )
    monkeypatch.setattr(emotion_ws, "get_system_prompt", lambda: "system")
    monkeypatch.setattr(emotion_ws.CFG, "GREETING_DELAY_MIN_SEC", 0.01)
    monkeypatch.setattr(emotion_ws.CFG, "GREETING_DELAY_MAX_SEC", 0.02)

    app = FastAPI()
    app.include_router(emotion_ws.router)
    client = TestClient(app)
    return client, engine, user_id


def test_opening_greeting_prefers_less_selected_candidate_and_persists_count(ws_app, monkeypatch):
    client, engine, user_id = ws_app

    with Session(engine) as db:
        stat0 = db.get(GreetingMessageStat, 0)
        stat1 = db.get(GreetingMessageStat, 1)
        stat0.selected_count = 5
        stat1.selected_count = 1
        db.add(stat0)
        db.add(stat1)
        db.commit()

    monkeypatch.setattr(greeting_service.random, "sample", lambda pool, k: [0, 1])

    with client.websocket_connect(
        "/ws/emotion",
        headers={"cookie": "access_token=test-token"},
    ) as ws:
        open_event = ws.receive_json()
        message_start = ws.receive_json()
        message = ws.receive_json()
        message_end = ws.receive_json()

    assert open_event["type"] == "open_ok"
    assert message_start["type"] == "message_start"
    assert message_end["type"] == "message_end"
    assert message["type"] == "message"
    assert message["message"] == greeting_loader.get_greeting_messages()[1]

    with Session(engine) as db:
        stat1 = db.get(GreetingMessageStat, 1)
        assert stat1.selected_count == 2

        session_id = UUID(open_event["session_id"])

        steps = list(
            db.exec(select(EmotionStep).where(EmotionStep.session_id == session_id))
        )
        assert len(steps) == 1
        assert steps[0].step_order == 1
        assert steps[0].step_type == "assistant"
        assert steps[0].gpt_response == greeting_loader.get_greeting_messages()[1]


def test_opening_greeting_falls_back_to_random_pick_when_db_selection_fails(ws_app, monkeypatch):
    """DB 기반 선택(카운터 조회/증가)이 실패해도 인사말 자체는 전송돼야 한다."""
    client, engine, user_id = ws_app

    def _boom(db):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(emotion_ws, "greeting_pick_greeting_message", _boom)
    monkeypatch.setattr(emotion_ws.random, "choice", lambda pool: pool[3])

    with client.websocket_connect(
        "/ws/emotion",
        headers={"cookie": "access_token=test-token"},
    ) as ws:
        open_event = ws.receive_json()
        message_start = ws.receive_json()
        message = ws.receive_json()
        message_end = ws.receive_json()

    assert open_event["type"] == "open_ok"
    assert message_start["type"] == "message_start"
    assert message_end["type"] == "message_end"
    assert message["type"] == "message"
    assert message["message"] == greeting_loader.get_greeting_messages()[3]

    with Session(engine) as db:
        session_id = UUID(open_event["session_id"])
        steps = list(
            db.exec(select(EmotionStep).where(EmotionStep.session_id == session_id))
        )
        assert len(steps) == 1
        assert steps[0].gpt_response == greeting_loader.get_greeting_messages()[3]
