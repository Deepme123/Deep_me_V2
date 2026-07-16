import importlib
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

os.environ.setdefault("JWT_SECRET_KEY", "test_secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test_refresh")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

summaries_router = importlib.import_module("app.analyze.routers.summaries")
auth_module = importlib.import_module("app.backend.dependencies.auth")
emotion_models = importlib.import_module("app.backend.models.emotion")
user_model = importlib.import_module("app.backend.models.user")


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _make_user_and_session(db: Session) -> tuple:
    user = user_model.User(name="tester", email=f"{uuid4()}@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)

    session = emotion_models.EmotionSession(user_id=user.user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return user, session


def _build_client(engine, current_user_id: str | None):
    app = FastAPI()
    app.include_router(summaries_router.router)

    def _get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[summaries_router.get_db] = _get_db
    if current_user_id is not None:
        app.dependency_overrides[auth_module.get_current_user] = lambda: current_user_id
    return TestClient(app)


def test_list_summaries_requires_auth(engine):
    client = _build_client(engine, current_user_id=None)

    response = client.get("/api/summaries")

    assert response.status_code == 401


def test_list_summaries_only_returns_own_cards(engine, add_analysis_card):
    with Session(engine) as db:
        owner, owner_session = _make_user_and_session(db)
        _other, other_session = _make_user_and_session(db)
        add_analysis_card(db, owner_session.session_id, summary="요약")
        add_analysis_card(db, other_session.session_id, summary="요약")
        owner_user_id = str(owner.user_id)
        owner_session_id = str(owner_session.session_id)

    client = _build_client(engine, current_user_id=owner_user_id)

    response = client.get("/api/summaries")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["session_id"] == owner_session_id


def test_list_session_summaries_excludes_other_users_session(engine, add_analysis_card):
    with Session(engine) as db:
        owner, owner_session = _make_user_and_session(db)
        _other, other_session = _make_user_and_session(db)
        add_analysis_card(db, other_session.session_id, summary="요약")
        owner_user_id = str(owner.user_id)
        other_session_id = other_session.session_id

    client = _build_client(engine, current_user_id=owner_user_id)

    response = client.get(f"/api/sessions/{other_session_id}/summaries")

    assert response.status_code == 200
    assert response.json() == []
