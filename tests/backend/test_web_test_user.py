import os
import sys
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

os.environ.setdefault("JWT_SECRET_KEY", "test_secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test_refresh")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.backend.services.web_test_user import resolve_emotion_user_id  # noqa: E402


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(autouse=True)
def _isolate_render_service(monkeypatch):
    # Render 셸·CI 등 외부에서 RENDER_SERVICE_NAME/ID가 들어와도 결과가 바뀌지 않도록 격리한다.
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
    monkeypatch.delenv("RENDER_SERVICE_ID", raising=False)


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session


def test_authenticated_user_bypasses_web_test_flag_entirely(db, monkeypatch):
    monkeypatch.delenv("EMOTION_NO_AUTH_WEB_TEST", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    user_id = "11111111-1111-1111-1111-111111111111"

    result = resolve_emotion_user_id(db, user_id)

    assert result == UUID(user_id)


def test_no_auth_rejected_when_web_test_flag_off(db, monkeypatch):
    monkeypatch.setenv("EMOTION_NO_AUTH_WEB_TEST", "false")
    monkeypatch.setenv("APP_ENV", "development")

    with pytest.raises(HTTPException) as exc_info:
        resolve_emotion_user_id(db, None)

    assert exc_info.value.status_code == 401


def test_no_auth_rejected_when_app_env_unset_defaults_to_production(db, monkeypatch):
    monkeypatch.setenv("EMOTION_NO_AUTH_WEB_TEST", "true")
    monkeypatch.delenv("APP_ENV", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        resolve_emotion_user_id(db, None)

    assert exc_info.value.status_code == 401


def test_no_auth_rejected_when_app_env_is_production(db, monkeypatch):
    monkeypatch.setenv("EMOTION_NO_AUTH_WEB_TEST", "true")
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(HTTPException) as exc_info:
        resolve_emotion_user_id(db, None)

    assert exc_info.value.status_code == 401


def test_no_auth_allowed_when_flag_on_and_app_env_development(db, monkeypatch):
    monkeypatch.setenv("EMOTION_NO_AUTH_WEB_TEST", "true")
    monkeypatch.setenv("APP_ENV", "development")

    result = resolve_emotion_user_id(db, None)

    assert isinstance(result, UUID)


# 웹테스트 페이지는 Google 로그인으로 토큰을 받으므로 Render 테스트 서비스에서도 우회를 열지 않는다.
@pytest.mark.parametrize(
    "service_id, service_name",
    [
        ("", "Deep_me_test_server"),
        ("srv-d9j0musm0tmc73a7ntv0", "renamed-test-server"),
        ("srv-d9j0musm0tmc73a7ntv0", "Deep_me_test_server"),
    ],
)
def test_no_auth_rejected_on_render_test_service_even_when_flag_on(db, monkeypatch, service_id, service_name):
    monkeypatch.setenv("EMOTION_NO_AUTH_WEB_TEST", "true")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("RENDER_SERVICE_ID", service_id)
    monkeypatch.setenv("RENDER_SERVICE_NAME", service_name)

    with pytest.raises(HTTPException) as exc_info:
        resolve_emotion_user_id(db, None)

    assert exc_info.value.status_code == 401


def test_no_auth_allowed_when_flag_on_and_app_env_local_on_render_test_service(db, monkeypatch):
    monkeypatch.setenv("EMOTION_NO_AUTH_WEB_TEST", "true")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("RENDER_SERVICE_NAME", "Deep_me_test_server")

    result = resolve_emotion_user_id(db, None)

    assert isinstance(result, UUID)


def test_no_auth_rejected_on_production_service_id(db, monkeypatch):
    monkeypatch.setenv("EMOTION_NO_AUTH_WEB_TEST", "true")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-d267fau3jp1c73cmcr1g")
    monkeypatch.setenv("RENDER_SERVICE_NAME", "Deep_me_V2")

    with pytest.raises(HTTPException) as exc_info:
        resolve_emotion_user_id(db, None)

    assert exc_info.value.status_code == 401


# 운영 서비스나 이름이 비슷한 서비스로 우회가 열리지 않는지 고정한다.
@pytest.mark.parametrize("service", ["Deep_me_V2", "Deep_me_test_server_old", "Deep_me_test_serve", ""])
def test_no_auth_rejected_on_other_render_services(db, monkeypatch, service):
    monkeypatch.setenv("EMOTION_NO_AUTH_WEB_TEST", "true")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("RENDER_SERVICE_NAME", service)

    with pytest.raises(HTTPException) as exc_info:
        resolve_emotion_user_id(db, None)

    assert exc_info.value.status_code == 401
