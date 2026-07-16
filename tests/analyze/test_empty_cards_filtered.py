import importlib
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

os.environ.setdefault("JWT_SECRET_KEY", "test_secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test_refresh")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

cards_router = importlib.import_module("app.analyze.routers.cards")
summaries_router = importlib.import_module("app.analyze.routers.summaries")
models = importlib.import_module("app.analyze.models")
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


def _build_cards_client(engine, current_user_id: str | None):
    app = FastAPI()
    app.include_router(cards_router.router)

    def _get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[cards_router.get_db] = _get_db
    if current_user_id is not None:
        app.dependency_overrides[cards_router.get_current_user] = lambda: current_user_id
    return TestClient(app)


def _build_summaries_client(engine, current_user_id: str | None):
    app = FastAPI()
    app.include_router(summaries_router.router)

    def _get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[summaries_router.get_db] = _get_db
    if current_user_id is not None:
        app.dependency_overrides[summaries_router.get_current_user] = lambda: current_user_id
    return TestClient(app)


def test_create_card_rejects_empty_payload(engine):
    with Session(engine) as db:
        owner, owner_session = _make_user_and_session(db)
        owner_user_id = str(owner.user_id)
        session_id = owner_session.session_id

    client = _build_cards_client(engine, current_user_id=owner_user_id)

    response = client.post(f"/api/sessions/{session_id}/cards", json={})

    assert response.status_code == 400
    with Session(engine) as db:
        assert db.exec(select(models.AnalysisCard)).all() == []


def test_create_card_accepts_meaningful_payload(engine):
    with Session(engine) as db:
        owner, owner_session = _make_user_and_session(db)
        owner_user_id = str(owner.user_id)
        session_id = owner_session.session_id

    client = _build_cards_client(engine, current_user_id=owner_user_id)

    response = client.post(
        f"/api/sessions/{session_id}/cards",
        json={"summary": "요약"},
    )

    assert response.status_code == 200
    assert response.json()["summary"] == "요약"


def test_list_cards_excludes_empty_card(engine, add_analysis_card):
    with Session(engine) as db:
        owner, owner_session = _make_user_and_session(db)
        add_analysis_card(db, owner_session.session_id)  # 빈 카드 (모든 콘텐츠 필드 None)
        owner_user_id = str(owner.user_id)
        session_id = owner_session.session_id

    client = _build_cards_client(engine, current_user_id=owner_user_id)

    response = client.get(f"/api/sessions/{session_id}/cards")

    assert response.status_code == 200
    assert response.json() == []


def test_list_cards_returns_meaningful_card(engine, add_analysis_card):
    with Session(engine) as db:
        owner, owner_session = _make_user_and_session(db)
        add_analysis_card(db, owner_session.session_id, summary="요약")
        owner_user_id = str(owner.user_id)
        session_id = owner_session.session_id

    client = _build_cards_client(engine, current_user_id=owner_user_id)

    response = client.get(f"/api/sessions/{session_id}/cards")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["summary"] == "요약"


def test_get_card_returns_404_for_empty_card(engine, add_analysis_card):
    with Session(engine) as db:
        owner, owner_session = _make_user_and_session(db)
        empty_card = add_analysis_card(db, owner_session.session_id)
        owner_user_id = str(owner.user_id)
        card_id = empty_card.card_id

    client = _build_cards_client(engine, current_user_id=owner_user_id)

    response = client.get(f"/api/cards/{card_id}")

    assert response.status_code == 404


def test_list_summaries_excludes_empty_card_but_keeps_meaningful_one(engine, add_analysis_card):
    with Session(engine) as db:
        owner, empty_session = _make_user_and_session(db)
        _other_owner, meaningful_session = _make_user_and_session(db)
        meaningful_session.user_id = owner.user_id
        db.add(meaningful_session)
        db.commit()

        add_analysis_card(db, empty_session.session_id)  # 빈 카드
        add_analysis_card(db, meaningful_session.session_id, summary="요약")
        owner_user_id = str(owner.user_id)

    client = _build_summaries_client(engine, current_user_id=owner_user_id)

    response = client.get("/api/summaries")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["summary"] == "요약"
