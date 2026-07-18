import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")
os.environ.setdefault("JWT_SECRET_KEY", "test-need-card-analyze-auth-secret")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.desire.routers import need_card as need_card_router
from app.desire.schemas.need_card import NeedCardResponse


def _build_client(current_user_id: str, db: MagicMock):
    app = FastAPI()
    app.include_router(need_card_router.router)
    app.dependency_overrides[need_card_router.get_session] = lambda: db
    app.dependency_overrides[need_card_router.get_current_user] = lambda: current_user_id
    return TestClient(app)


def test_analyze_requires_authentication():
    app = FastAPI()
    app.include_router(need_card_router.router)
    app.dependency_overrides[need_card_router.get_session] = lambda: MagicMock()
    client = TestClient(app)

    response = client.post(
        "/need-cards/analyze",
        json={"session_id": str(uuid4()), "conversation_text": "hello"},
    )

    assert response.status_code in (401, 403)


def test_analyze_rejects_session_owned_by_another_user():
    """session_id가 다른 유저 소유면, 그 유저의 과거 욕구 선택 이력이
    개인화 힌트로 새어나가지 않도록 404로 거부해야 한다."""
    other_user_id = uuid4()
    db = MagicMock()
    db.get.return_value = SimpleNamespace(user_id=other_user_id)
    client = _build_client(str(uuid4()), db)

    response = client.post(
        "/need-cards/analyze",
        json={"session_id": str(uuid4()), "conversation_text": "hello"},
    )

    assert response.status_code == 404


def test_analyze_rejects_nonexistent_session():
    db = MagicMock()
    db.get.return_value = None
    client = _build_client(str(uuid4()), db)

    response = client.post(
        "/need-cards/analyze",
        json={"session_id": str(uuid4()), "conversation_text": "hello"},
    )

    assert response.status_code == 404


def test_analyze_allows_session_owned_by_requester():
    user_id = uuid4()
    db = MagicMock()
    db.get.return_value = SimpleNamespace(user_id=user_id)
    client = _build_client(str(user_id), db)

    fake_response = NeedCardResponse(needs=[], top4=[])

    with patch.object(
        need_card_router, "analyze_needs", new=AsyncMock(return_value=fake_response)
    ) as mock_analyze:
        response = client.post(
            "/need-cards/analyze",
            json={"session_id": str(uuid4()), "conversation_text": "hello"},
        )

    assert response.status_code == 200
    mock_analyze.assert_awaited_once()
