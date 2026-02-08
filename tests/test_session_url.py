import importlib
import sys
from pathlib import Path

import pytest
from sqlalchemy.engine import url as sa_url

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


BASE_DSN = "user:pass@db.example.com:5432/deepme"


@pytest.fixture
def session_module(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg2://{BASE_DSN}")
    monkeypatch.delenv("DB_SSLMODE", raising=False)
    import app.db.session as session

    return importlib.reload(session)


@pytest.mark.parametrize(
    ("raw_url", "expected_url"),
    [
        (f"postgresql://{BASE_DSN}", f"postgresql+psycopg2://{BASE_DSN}"),
        (f"postgres://{BASE_DSN}", f"postgresql+psycopg2://{BASE_DSN}"),
        (f"postgresql+psycopg2://{BASE_DSN}", f"postgresql+psycopg2://{BASE_DSN}"),
        (f"postgresql+psycopg://{BASE_DSN}", f"postgresql+psycopg://{BASE_DSN}"),
    ],
)
def test_build_db_url_accepts_and_normalizes_supported_schemes(
    session_module, monkeypatch, raw_url, expected_url
):
    monkeypatch.setenv("DATABASE_URL", raw_url)

    assert session_module._build_db_url() == expected_url


def test_build_db_url_uses_policy_driver_for_legacy_scheme(session_module, monkeypatch):
    monkeypatch.setenv("DATABASE_DRIVER", "psycopg")
    monkeypatch.setenv("DATABASE_URL", f"postgresql://{BASE_DSN}")

    assert session_module._build_db_url() == f"postgresql+psycopg://{BASE_DSN}"


def test_build_db_url_applies_db_sslmode_policy_when_set(session_module, monkeypatch):
    raw_url = "postgresql://user:pass@db.example.com:5432/deepme"
    monkeypatch.setenv("DATABASE_URL", raw_url)
    monkeypatch.setenv("DB_SSLMODE", "require")

    built = session_module._build_db_url()

    assert built == "postgresql+psycopg2://user:pass@db.example.com:5432/deepme?sslmode=require"


def test_build_db_url_overrides_existing_sslmode_without_duplicates(session_module, monkeypatch):
    raw_url = "postgresql://user:pass@db.example.com:5432/deepme?connect_timeout=10&sslmode=disable"
    monkeypatch.setenv("DATABASE_URL", raw_url)
    monkeypatch.setenv("DB_SSLMODE", "prefer")

    built = session_module._build_db_url()
    parsed = sa_url.make_url(built)

    assert parsed.query["sslmode"] == "prefer"
    assert built.count("sslmode=") == 1
    assert "sslmode=disable" not in built


def test_build_db_url_keeps_existing_sslmode_without_policy(session_module, monkeypatch):
    raw_url = "postgresql://user:pass@db.example.com:5432/deepme?sslmode=disable"
    monkeypatch.setenv("DATABASE_URL", raw_url)

    built = session_module._build_db_url()

    assert built == "postgresql+psycopg2://user:pass@db.example.com:5432/deepme?sslmode=disable"


def test_build_db_url_rejects_invalid_db_sslmode(session_module, monkeypatch):
    monkeypatch.setenv("DB_SSLMODE", "required")

    with pytest.raises(RuntimeError, match="DB_SSLMODE must be one of"):
        session_module._build_db_url()
