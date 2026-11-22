from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.backend.core import prompt_loader


class PromptLoaderTests(unittest.TestCase):
    def tearDown(self) -> None:
        prompt_loader.get_system_prompt.cache_clear()
        prompt_loader.get_task_prompt.cache_clear()
        prompt_loader.get_judge_prompt.cache_clear()

    def test_get_task_prompt_returns_fallback_when_file_is_missing(self) -> None:
        missing_path = Path(tempfile.gettempdir()) / "missing-task-prompt-for-test.txt"
        if missing_path.exists():
            missing_path.unlink()

        with patch.object(prompt_loader, "TASK_PROMPT_PATH", missing_path):
            prompt_loader.get_task_prompt.cache_clear()
            result = prompt_loader.get_task_prompt()

        self.assertEqual(result, prompt_loader.FALLBACK_TASK_PROMPT)

    def test_get_system_prompt_defines_progress_memo_and_close_token(self) -> None:
        prompt_loader.get_system_prompt.cache_clear()

        result = prompt_loader.get_system_prompt()

        self.assertIn("[진행 메모: ...]", result)
        self.assertIn("[[CONFIRM_CLOSE]]", result)
        self.assertIn("109", result)

    def test_get_judge_prompt_loads_file_and_requires_json_output(self) -> None:
        prompt_loader.get_judge_prompt.cache_clear()

        result = prompt_loader.get_judge_prompt()

        self.assertIn("JSON으로만 답한다", result)
        self.assertIn('"risk":false', result)

    def test_get_judge_prompt_is_empty_when_file_is_missing(self) -> None:
        missing_path = Path(tempfile.gettempdir()) / "missing-judge-prompt-for-test.txt"
        if missing_path.exists():
            missing_path.unlink()

        with patch.object(prompt_loader, "JUDGE_PROMPT_PATH", missing_path):
            prompt_loader.get_judge_prompt.cache_clear()
            result = prompt_loader.get_judge_prompt()
        prompt_loader.get_judge_prompt.cache_clear()

        self.assertEqual(result, "")


# ---- 테스트 런타임 DB 오버라이드 (/prompts API로 저장한 프롬프트) ----

import pytest  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from app.backend.models.prompt_revision import PromptRevision  # noqa: E402


@pytest.fixture
def override_db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    @contextmanager
    def _scope():
        with Session(engine) as s:
            yield s

    monkeypatch.setattr(prompt_loader, "session_scope", _scope)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
    monkeypatch.delenv("RENDER_SERVICE_ID", raising=False)
    prompt_loader.get_system_prompt.cache_clear()
    yield engine
    prompt_loader.get_system_prompt.cache_clear()


def _add_revision(engine, content, prompt_type="system"):
    with Session(engine) as s:
        s.add(PromptRevision(prompt_type=prompt_type, content=content))
        s.commit()


def test_db_override_used_on_render_test_service(override_db, monkeypatch):
    monkeypatch.setenv("RENDER_SERVICE_NAME", "Deep_me_test_server")
    _add_revision(override_db, "old")
    _add_revision(override_db, "new")

    assert prompt_loader.get_system_prompt() == "new"


def test_db_override_ignored_on_production(override_db, monkeypatch):
    # 운영 서비스가 테스트 서버와 DB를 공유하더라도 오버라이드를 읽지 않아야 한다.
    monkeypatch.setenv("RENDER_SERVICE_NAME", "Deep_me_V2")
    _add_revision(override_db, "override")

    assert prompt_loader.get_system_prompt() == prompt_loader.get_file_prompt("system")


def test_reset_revision_falls_back_to_file(override_db, monkeypatch):
    monkeypatch.setenv("RENDER_SERVICE_NAME", "Deep_me_test_server")
    _add_revision(override_db, "override")
    _add_revision(override_db, None)

    assert prompt_loader.get_system_prompt() == prompt_loader.get_file_prompt("system")


def test_db_failure_falls_back_to_file(monkeypatch):
    monkeypatch.setenv("RENDER_SERVICE_NAME", "Deep_me_test_server")

    @contextmanager
    def _broken():
        raise RuntimeError("db down")
        yield

    monkeypatch.setattr(prompt_loader, "session_scope", _broken)
    assert prompt_loader.get_db_override("system") is None


def test_judge_db_override_used_on_render_test_service(override_db, monkeypatch):
    monkeypatch.setenv("RENDER_SERVICE_NAME", "Deep_me_test_server")
    _add_revision(override_db, "judge-new", prompt_type="judge")
    prompt_loader.get_judge_prompt.cache_clear()

    assert prompt_loader.get_judge_prompt() == "judge-new"
    prompt_loader.get_judge_prompt.cache_clear()


if __name__ == "__main__":
    unittest.main()
