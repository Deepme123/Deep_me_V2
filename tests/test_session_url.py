import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


BASE_DSN = "user:pass@db.example.com:5432/deepme"


@pytest.fixture
def session_module(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg2://{BASE_DSN}")
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


def test_build_db_url_adds_sslmode_for_managed_hosts_when_missing(session_module, monkeypatch):
    raw_url = "postgresql://user:pass@my-project.neon.tech:5432/deepme"
    monkeypatch.setenv("DATABASE_URL", raw_url)

    built = session_module._build_db_url()

    assert built == "postgresql+psycopg2://user:pass@my-project.neon.tech:5432/deepme?sslmode=require"


def test_build_db_url_keeps_existing_sslmode(session_module, monkeypatch):
    raw_url = "postgresql://user:pass@my-project.neon.tech:5432/deepme?sslmode=disable"
    monkeypatch.setenv("DATABASE_URL", raw_url)

    built = session_module._build_db_url()

    assert built == "postgresql+psycopg2://user:pass@my-project.neon.tech:5432/deepme?sslmode=disable"
