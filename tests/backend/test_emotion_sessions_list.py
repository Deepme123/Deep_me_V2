import importlib
import os
import sys
from datetime import datetime
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

emotion_router = importlib.import_module("app.backend.routers.emotion")
emotion_models = importlib.import_module("app.backend.models.emotion")
user_model = importlib.import_module("app.backend.models.user")
db_session_module = importlib.import_module("app.db.session")
analyze_models = importlib.import_module("app.analyze.models")


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _make_user_and_session(db: Session):
    user = user_model.User(name="tester", email=f"{uuid4()}@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)

    session = emotion_models.EmotionSession(user_id=user.user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return user, session


def _add_step(db: Session, session_id, *, order: int, user_input: str) -> None:
    db.add(
        emotion_models.EmotionStep(
            session_id=session_id,
            step_order=order,
            step_type="message",
            user_input=user_input,
            gpt_response="응답",
        )
    )
    db.commit()


def _add_card(db: Session, session_id, **fields) -> None:
    db.add(analyze_models.AnalysisCard(session_id=session_id, **fields))
    db.commit()


def _end_session(db: Session, session) -> None:
    session.ended_at = datetime.utcnow()
    db.add(session)
    db.commit()


def _build_client(engine, user_id):
    app = FastAPI()
    app.include_router(emotion_router.router)

    def _get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[db_session_module.get_session] = _get_db
    app.dependency_overrides[emotion_router._emotion_user_id] = lambda: user_id
    return TestClient(app)


def test_list_sessions_excludes_empty_sessions(engine):
    with Session(engine) as db:
        user, session_with_msg = _make_user_and_session(db)
        _add_step(db, session_with_msg.session_id, order=1, user_input="안녕")
        _add_card(db, session_with_msg.session_id, summary="요약")

        # 사용자 발화 없는 빈 세션 (스텝 자체가 없음)
        empty = emotion_models.EmotionSession(user_id=user.user_id)
        db.add(empty)
        db.commit()

        user_id = user.user_id
        kept_id = str(session_with_msg.session_id)

    client = _build_client(engine, user_id)

    response = client.get("/emotion/sessions")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["session_id"] == kept_id


def test_list_sessions_excludes_sessions_with_only_blank_user_input(engine):
    with Session(engine) as db:
        user, blank_session = _make_user_and_session(db)
        # gpt_response만 있고 user_input이 빈 문자열인 스텝
        _add_step(db, blank_session.session_id, order=1, user_input="")

        user_id = user.user_id

    client = _build_client(engine, user_id)

    response = client.get("/emotion/sessions")

    assert response.status_code == 200
    assert response.json() == []


def test_list_sessions_excludes_in_progress_sessions_without_analysis_card(engine):
    """메시지는 있지만 아직 종료되지 않고(ended_at 없음) 분석카드도 없는
    세션(대화 진행 중)은 클릭해도 조회되는 내용이 없으므로 제외되어야 한다."""
    with Session(engine) as db:
        user, no_card_session = _make_user_and_session(db)
        _add_step(db, no_card_session.session_id, order=1, user_input="안녕")

        user_id = user.user_id

    client = _build_client(engine, user_id)

    response = client.get("/emotion/sessions")

    assert response.status_code == 200
    assert response.json() == []


def test_list_sessions_includes_ended_sessions_without_analysis_card(engine):
    """종료(ended_at 있음)됐지만 카드 생성이 실패했거나 아직 재시도되지 않아
    분석카드가 없는 세션은, 정상적으로 끝난 대화이므로 계속 노출되어야 한다."""
    with Session(engine) as db:
        user, ended_session = _make_user_and_session(db)
        _add_step(db, ended_session.session_id, order=1, user_input="안녕")
        _end_session(db, ended_session)

        user_id = user.user_id
        kept_id = str(ended_session.session_id)

    client = _build_client(engine, user_id)

    response = client.get("/emotion/sessions")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["session_id"] == kept_id


def test_list_sessions_excludes_sessions_with_empty_analysis_card(engine):
    """카드 row는 존재하지만 내용이 완전히 비어있는 레거시 데이터는 클릭 시
    빈 화면이 되므로 카드 유무와 무관하게 제외되어야 한다."""
    with Session(engine) as db:
        user, ended_session = _make_user_and_session(db)
        _add_step(db, ended_session.session_id, order=1, user_input="안녕")
        _end_session(db, ended_session)
        _add_card(db, ended_session.session_id)  # 모든 콘텐츠 필드가 None인 빈 카드

        user_id = user.user_id

    client = _build_client(engine, user_id)

    response = client.get("/emotion/sessions")

    assert response.status_code == 200
    assert response.json() == []


def test_list_sessions_includes_sessions_with_analysis_card(engine):
    with Session(engine) as db:
        user, session_with_card = _make_user_and_session(db)
        _add_step(db, session_with_card.session_id, order=1, user_input="안녕")
        _add_card(db, session_with_card.session_id, summary="요약")

        user_id = user.user_id
        kept_id = str(session_with_card.session_id)

    client = _build_client(engine, user_id)

    response = client.get("/emotion/sessions")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["session_id"] == kept_id
