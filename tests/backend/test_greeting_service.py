import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

os.environ.setdefault("JWT_SECRET_KEY", "test_secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test_refresh")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.backend.core import greeting_loader  # noqa: E402
from app.backend.models.greeting_message import GreetingMessageStat  # noqa: E402
from app.backend.services import greeting_service  # noqa: E402


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session


def test_get_greeting_messages_loads_ten_candidates():
    messages = greeting_loader.get_greeting_messages()
    assert len(messages) == 10
    assert all(isinstance(m, str) and m for m in messages)


def test_pick_greeting_message_prefers_lower_count(db, monkeypatch):
    db.add(GreetingMessageStat(message_index=0, selected_count=5))
    db.add(GreetingMessageStat(message_index=1, selected_count=1))
    db.commit()

    monkeypatch.setattr(greeting_service.random, "sample", lambda pool, k: [0, 1])

    index, text = greeting_service.pick_greeting_message(db)

    assert index == 1
    assert text == greeting_loader.get_greeting_messages()[1]


def test_pick_greeting_message_breaks_tie_randomly(db, monkeypatch):
    db.add(GreetingMessageStat(message_index=2, selected_count=3))
    db.add(GreetingMessageStat(message_index=3, selected_count=3))
    db.commit()

    monkeypatch.setattr(greeting_service.random, "sample", lambda pool, k: [2, 3])
    monkeypatch.setattr(greeting_service.random, "choice", lambda choices: choices[0])

    index, _ = greeting_service.pick_greeting_message(db)

    assert index == 2


def test_pick_greeting_message_increments_selected_count(db, monkeypatch):
    db.add(GreetingMessageStat(message_index=0, selected_count=0))
    db.add(GreetingMessageStat(message_index=1, selected_count=0))
    db.commit()

    monkeypatch.setattr(greeting_service.random, "sample", lambda pool, k: [0, 1])
    monkeypatch.setattr(greeting_service.random, "choice", lambda choices: choices[0])

    index, _ = greeting_service.pick_greeting_message(db)

    stat = db.get(GreetingMessageStat, index)
    assert stat.selected_count == 1


def test_pick_greeting_message_handles_missing_stat_row(db, monkeypatch):
    # 마이그레이션 시드가 없는 인덱스도 count=0 취급하며 에러 없이 동작해야 한다.
    monkeypatch.setattr(greeting_service.random, "sample", lambda pool, k: [4, 5])
    monkeypatch.setattr(greeting_service.random, "choice", lambda choices: choices[0])

    index, _ = greeting_service.pick_greeting_message(db)

    assert index == 4
    stat = db.get(GreetingMessageStat, 4)
    assert stat.selected_count == 1
