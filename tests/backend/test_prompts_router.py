import importlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path

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

prompts_router_module = importlib.import_module("app.backend.routers.prompts")
prompt_loader = importlib.import_module("app.backend.core.prompt_loader")
db_session_module = importlib.import_module("app.db.session")


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
def _isolate_runtime(monkeypatch, engine):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("RENDER_SERVICE_NAME", "deep-me-v2-test")

    # 대화 경로(prompt_loader)도 같은 DB를 보게 해 저장 → 즉시 반영을 검증한다.
    @contextmanager
    def _scope():
        with Session(engine) as s:
            yield s

    monkeypatch.setattr(prompt_loader, "session_scope", _scope)
    prompt_loader.get_system_prompt.cache_clear()
    prompt_loader.get_task_prompt.cache_clear()
    yield
    prompt_loader.get_system_prompt.cache_clear()
    prompt_loader.get_task_prompt.cache_clear()


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(prompts_router_module.router)

    def _get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[db_session_module.get_session] = _get_db
    return TestClient(app)


def test_get_returns_file_prompt_by_default(client):
    res = client.get("/prompts/system")

    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "system"
    assert body["source"] == "file"
    assert body["content"] == prompt_loader.get_file_prompt("system")


def test_put_saves_and_applies_immediately(client):
    # 저장 전에 캐시를 한 번 채워둬도 저장 후엔 새 값이 나와야 한다.
    prompt_loader.get_system_prompt()

    res = client.put("/prompts/system", json={"content": "  연구용 프롬프트  "})

    assert res.status_code == 200
    assert res.json()["content"] == "연구용 프롬프트"
    assert res.json()["source"] == "db"
    assert client.get("/prompts/system").json()["content"] == "연구용 프롬프트"
    assert prompt_loader.get_system_prompt() == "연구용 프롬프트"
    # 다른 타입에는 영향이 없다.
    assert prompt_loader.get_task_prompt() == prompt_loader.get_file_prompt("task")


def test_delete_resets_to_file_and_history_keeps_all(client):
    client.put("/prompts/task", json={"content": "v1"})
    client.put("/prompts/task", json={"content": "v2"})

    res = client.delete("/prompts/task")

    assert res.status_code == 200
    assert res.json()["source"] == "file"
    assert prompt_loader.get_task_prompt() == prompt_loader.get_file_prompt("task")

    history = client.get("/prompts/task/history").json()
    assert [h["content"] for h in history] == [None, "v2", "v1"]
    assert [h["is_reset"] for h in history] == [True, False, False]


@pytest.mark.parametrize(
    "content, detail",
    [("   ", "content_empty"), ("가" * (20 * 1024), "content_too_large")],
)
def test_put_rejects_invalid_content(client, content, detail):
    res = client.put("/prompts/system", json={"content": content})

    assert res.status_code == 400
    assert res.json()["detail"] == detail


def test_unknown_prompt_type_rejected(client):
    assert client.get("/prompts/other").status_code == 422


@pytest.mark.parametrize("service", ["deep-me-v2", "deep-me-v2-test-old", ""])
def test_all_routes_404_outside_test_runtime(client, monkeypatch, service):
    monkeypatch.setenv("RENDER_SERVICE_NAME", service)

    assert client.get("/prompts/system").status_code == 404
    assert client.put("/prompts/system", json={"content": "x"}).status_code == 404
    assert client.delete("/prompts/system").status_code == 404
    assert client.get("/prompts/system/history").status_code == 404
