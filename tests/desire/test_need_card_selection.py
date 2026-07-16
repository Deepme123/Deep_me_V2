import os
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")
os.environ.setdefault("JWT_SECRET_KEY", "test-need-card-selection-secret")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.desire.routers import need_card as need_card_router


def _build_client(current_user_id: str):
    app = FastAPI()
    app.include_router(need_card_router.router)
    app.dependency_overrides[need_card_router.get_session] = lambda: None
    app.dependency_overrides[need_card_router.get_current_user] = lambda: current_user_id
    return TestClient(app)


def _fake_result(scores: list[tuple[str, str]]):
    return SimpleNamespace(
        scores=[SimpleNamespace(code=code, reflection_message=message) for code, message in scores]
    )


def test_post_selection_includes_reflection_message_from_latest_result():
    client = _build_client(str(uuid4()))
    fake_result = _fake_result([("Together", "그때는 어쩌면 혼자인 느낌이 스쳤을 수도 있었지.")])

    with patch.object(need_card_router, "save_user_need_selection"), \
         patch.object(need_card_router, "get_last_need_card_result_by_user", return_value=fake_result):
        response = client.post("/need-cards/selection", json={"selected_need": "Together"})

    assert response.status_code == 200
    assert response.json()["reflection_message"] == "그때는 어쩌면 혼자인 느낌이 스쳤을 수도 있었지."


def test_post_selection_returns_empty_reflection_message_when_no_result():
    client = _build_client(str(uuid4()))

    with patch.object(need_card_router, "save_user_need_selection"), \
         patch.object(need_card_router, "get_last_need_card_result_by_user", return_value=None):
        response = client.post("/need-cards/selection", json={"selected_need": "Together"})

    assert response.status_code == 200
    assert response.json()["reflection_message"] == ""


def test_last_selection_includes_reflection_message():
    client = _build_client(str(uuid4()))
    fake_selection = SimpleNamespace(selected_codes=["Together"])
    fake_result = _fake_result([("Together", "이번엔 '소속'이라는 너의 바람이 조용히 마음을 두드린 걸지도 몰라.")])

    with patch.object(need_card_router, "get_last_user_need_selection", return_value=fake_selection), \
         patch.object(need_card_router, "get_last_need_card_result_by_user", return_value=fake_result):
        response = client.get("/need-cards/last-selection")

    assert response.status_code == 200
    assert response.json()["reflection_message"] == "이번엔 '소속'이라는 너의 바람이 조용히 마음을 두드린 걸지도 몰라."


def test_last_selection_returns_404_when_no_selection():
    client = _build_client(str(uuid4()))

    with patch.object(need_card_router, "get_last_user_need_selection", return_value=None):
        response = client.get("/need-cards/last-selection")

    assert response.status_code == 404
