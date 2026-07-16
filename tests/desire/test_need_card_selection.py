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


def test_post_selection_uses_session_specific_result_not_latest():
    """세션A를 분석해 고른 욕구를, 세션B를 나중에 분석한 뒤 선택해도
    세션A의 reflection_message가 반환되어야 한다 (최신 분석 결과로 오염되면 안 됨)."""
    client = _build_client(str(uuid4()))
    session_a_id = uuid4()
    session_a_result = _fake_result([("Together", "세션A: 그때는 어쩌면 혼자인 느낌이 스쳤을 수도 있었지.")])
    session_b_result = _fake_result([("Together", "세션B: 전혀 다른 대화 내용.")])

    with patch.object(need_card_router, "save_user_need_selection"), \
         patch.object(
             need_card_router, "get_need_card_result_by_session", return_value=session_a_result
         ) as mock_by_session, \
         patch.object(
             need_card_router, "get_last_need_card_result_by_user", return_value=session_b_result
         ) as mock_by_user:
        response = client.post(
            "/need-cards/selection",
            json={"selected_need": "Together", "session_id": str(session_a_id)},
        )

    assert response.status_code == 200
    assert response.json()["reflection_message"] == "세션A: 그때는 어쩌면 혼자인 느낌이 스쳤을 수도 있었지."
    mock_by_session.assert_called_once()
    mock_by_user.assert_not_called()


def test_post_selection_falls_back_to_latest_when_no_session_id():
    client = _build_client(str(uuid4()))
    fake_result = _fake_result([("Together", "그때는 어쩌면 혼자인 느낌이 스쳤을 수도 있었지.")])

    with patch.object(need_card_router, "save_user_need_selection"), \
         patch.object(need_card_router, "get_last_need_card_result_by_user", return_value=fake_result):
        response = client.post("/need-cards/selection", json={"selected_need": "Together"})

    assert response.status_code == 200
    assert response.json()["reflection_message"] == "그때는 어쩌면 혼자인 느낌이 스쳤을 수도 있었지."


def test_post_selection_falls_back_to_latest_when_session_lookup_finds_nothing():
    """session_id가 왔지만 그 세션의 분석 결과가 없거나(소유권 불일치 등) 못 찾으면
    기존처럼 유저의 최신 분석 결과로 폴백한다."""
    client = _build_client(str(uuid4()))
    fallback_result = _fake_result([("Together", "폴백된 최신 결과.")])

    with patch.object(need_card_router, "save_user_need_selection"), \
         patch.object(need_card_router, "get_need_card_result_by_session", return_value=None), \
         patch.object(
             need_card_router, "get_last_need_card_result_by_user", return_value=fallback_result
         ):
        response = client.post(
            "/need-cards/selection",
            json={"selected_need": "Together", "session_id": str(uuid4())},
        )

    assert response.status_code == 200
    assert response.json()["reflection_message"] == "폴백된 최신 결과."


def test_post_selection_returns_empty_reflection_message_when_no_result():
    client = _build_client(str(uuid4()))

    with patch.object(need_card_router, "save_user_need_selection"), \
         patch.object(need_card_router, "get_last_need_card_result_by_user", return_value=None):
        response = client.post("/need-cards/selection", json={"selected_need": "Together"})

    assert response.status_code == 200
    assert response.json()["reflection_message"] == ""


def test_last_selection_uses_stored_session_id_not_latest_result():
    client = _build_client(str(uuid4()))
    stored_session_id = uuid4()
    fake_selection = SimpleNamespace(selected_codes=["Together"], session_id=stored_session_id)
    session_specific_result = _fake_result([("Together", "선택 당시 세션의 서술문.")])
    unrelated_latest_result = _fake_result([("Together", "그 이후 분석된 무관한 서술문.")])

    with patch.object(
             need_card_router, "get_last_user_need_selection", return_value=fake_selection
         ), \
         patch.object(
             need_card_router,
             "get_need_card_result_by_session",
             return_value=session_specific_result,
         ) as mock_by_session, \
         patch.object(
             need_card_router,
             "get_last_need_card_result_by_user",
             return_value=unrelated_latest_result,
         ) as mock_by_user:
        response = client.get("/need-cards/last-selection")

    assert response.status_code == 200
    assert response.json()["reflection_message"] == "선택 당시 세션의 서술문."
    mock_by_session.assert_called_once()
    mock_by_user.assert_not_called()


def test_last_selection_falls_back_when_selection_has_no_session_id():
    client = _build_client(str(uuid4()))
    fake_selection = SimpleNamespace(selected_codes=["Together"], session_id=None)
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
