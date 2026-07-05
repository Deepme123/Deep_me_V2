import importlib
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")
os.environ.setdefault("JWT_SECRET_KEY", "test-satisfaction-secret")
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

satisfaction = importlib.import_module("app.analyze.routers.satisfaction")
m = importlib.import_module("app.analyze.models")


class FakeExecResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    def __init__(self, sessions):
        self.sessions = sessions
        self.ratings = []
        self._active_session_id = None

    def get(self, model, pk):
        if getattr(model, "__name__", "") == "EmotionSession":
            self._active_session_id = pk
            return self.sessions.get(pk)
        return None

    def exec(self, stmt):
        try:
            model = stmt.column_descriptions[0]["type"]
        except (AttributeError, IndexError, KeyError, TypeError):
            model = None
        if getattr(model, "__name__", "") == "SatisfactionRating":
            matching = [r for r in self.ratings if r.session_id == self._active_session_id]
            return FakeExecResult(matching)
        return FakeExecResult([])

    def add(self, obj):
        if obj not in self.ratings:
            self.ratings.append(obj)

    def commit(self):
        return None

    def refresh(self, _obj):
        return None


def _build_client(fake_db, current_user_id=None):
    app = FastAPI()
    app.include_router(satisfaction.router)
    app.dependency_overrides[satisfaction.get_db] = lambda: fake_db
    app.dependency_overrides[satisfaction.get_current_user] = lambda: current_user_id
    return TestClient(app)


def test_upsert_creates_rating_on_first_submit():
    session_id = uuid4()
    user_id = uuid4()
    fake_db = FakeDB(sessions={session_id: SimpleNamespace(session_id=session_id, user_id=user_id)})
    client = _build_client(fake_db, current_user_id=str(user_id))

    response = client.put(f"/api/sessions/{session_id}/satisfaction", json={"rating": 4})

    assert response.status_code == 200
    assert response.json()["rating"] == 4
    assert len(fake_db.ratings) == 1


def test_upsert_overwrites_existing_rating_on_resubmit():
    session_id = uuid4()
    user_id = uuid4()
    fake_db = FakeDB(sessions={session_id: SimpleNamespace(session_id=session_id, user_id=user_id)})
    client = _build_client(fake_db, current_user_id=str(user_id))

    first = client.put(f"/api/sessions/{session_id}/satisfaction", json={"rating": 2})
    second = client.put(f"/api/sessions/{session_id}/satisfaction", json={"rating": 5})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["rating"] == 5
    assert len(fake_db.ratings) == 1


def test_upsert_rejects_out_of_range_rating():
    session_id = uuid4()
    user_id = uuid4()
    fake_db = FakeDB(sessions={session_id: SimpleNamespace(session_id=session_id, user_id=user_id)})
    client = _build_client(fake_db, current_user_id=str(user_id))

    response = client.put(f"/api/sessions/{session_id}/satisfaction", json={"rating": 6})

    assert response.status_code == 422
    assert fake_db.ratings == []


def test_upsert_forbidden_for_other_users_session():
    session_id = uuid4()
    owner_id = uuid4()
    other_user_id = uuid4()
    fake_db = FakeDB(sessions={session_id: SimpleNamespace(session_id=session_id, user_id=owner_id)})
    client = _build_client(fake_db, current_user_id=str(other_user_id))

    response = client.put(f"/api/sessions/{session_id}/satisfaction", json={"rating": 3})

    assert response.status_code == 403
    assert fake_db.ratings == []


def test_get_satisfaction_returns_404_when_missing():
    session_id = uuid4()
    user_id = uuid4()
    fake_db = FakeDB(sessions={session_id: SimpleNamespace(session_id=session_id, user_id=user_id)})
    client = _build_client(fake_db, current_user_id=str(user_id))

    response = client.get(f"/api/sessions/{session_id}/satisfaction")

    assert response.status_code == 404
