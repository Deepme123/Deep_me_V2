import inspect
import os
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")
os.environ.setdefault("JWT_SECRET_KEY", "test-need-card-history-secret")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.analyze.models  # noqa: F401  (테이블 등록)
from app.backend.models import refresh_token as _m_refresh  # noqa: F401
from app.backend.models import task as _m_task  # noqa: F401
from app.core.models.emotion import EmotionSession
from app.backend.models.user import User
from app.desire.models.need_card import NeedCardResult, NeedCardScore
from app.desire.routers import need_card as need_card_router
from app.desire.schemas.need_card import NeedCode

RESULT_COUNT = 20


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def user_id(engine):
    uid = uuid4()
    codes = [code.value for code in NeedCode]
    with Session(engine) as db:
        db.add(User(user_id=uid, email="history@example.com", name="history"))
        db.commit()
        for i in range(RESULT_COUNT):
            session = EmotionSession(user_id=uid)
            db.add(session)
            db.flush()
            result = NeedCardResult(session_id=session.session_id)
            db.add(result)
            db.flush()
            for rank, code in enumerate(codes, start=1):
                db.add(
                    NeedCardScore(
                        result_id=result.result_id,
                        code=code,
                        score=100 - rank,
                        rank=rank,
                        reflection_message=f"{i}-{code}",
                    )
                )
        db.commit()
    return uid


def _build_client(engine, current_user_id: str):
    def _session():
        with Session(engine) as db:
            yield db

    app = FastAPI()
    app.include_router(need_card_router.router)
    app.dependency_overrides[need_card_router.get_session] = _session
    app.dependency_overrides[need_card_router.get_current_user] = lambda: current_user_id
    return TestClient(app)


def test_history_query_count_does_not_grow_with_rows(engine, user_id):
    """히스토리 조회는 결과 행 수와 무관하게 고정된 쿼리 수로 끝나야 한다
    (count + 목록 + scores 일괄 로딩). 행마다 scores를 지연 로딩하면 N+1이 된다."""
    client = _build_client(engine, str(user_id))
    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        response = client.get("/need-cards/history", params={"limit": RESULT_COUNT})
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert response.status_code == 200
    assert len(statements) <= 3, f"쿼리 {len(statements)}개 실행됨"


def test_history_response_shape(engine, user_id):
    client = _build_client(engine, str(user_id))

    response = client.get("/need-cards/history", params={"limit": RESULT_COUNT})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == RESULT_COUNT
    assert len(body["items"]) == RESULT_COUNT
    expected_codes = [code.value for code in NeedCode][:4]
    for item in body["items"]:
        assert [need["code"] for need in item["top4"]] == expected_codes
        assert [need["rank"] for need in item["top4"]] == [1, 2, 3, 4]
        assert all(need["reflection_message"] for need in item["top4"])


@pytest.mark.parametrize(
    "handler",
    [
        need_card_router.get_need_card_history,
        need_card_router.get_last_selection,
        need_card_router.post_selected_need_cards,
    ],
)
def test_sync_db_handlers_are_not_coroutines(handler):
    """동기 DB 호출만 하는 핸들러는 def여야 스레드풀에서 실행된다.
    async def로 두면 쿼리 동안 이벤트 루프(WebSocket 스트리밍 포함)가 멈춘다."""
    assert not inspect.iscoroutinefunction(handler)
