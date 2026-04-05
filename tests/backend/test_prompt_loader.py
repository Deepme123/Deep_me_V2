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

    def test_get_task_prompt_returns_fallback_when_file_is_missing(self) -> None:
        missing_path = Path(tempfile.gettempdir()) / "missing-task-prompt-for-test.txt"
        if missing_path.exists():
            missing_path.unlink()

        with patch.object(prompt_loader, "TASK_PROMPT_PATH", missing_path):
            prompt_loader.get_task_prompt.cache_clear()
            result = prompt_loader.get_task_prompt()

        self.assertEqual(result, prompt_loader.FALLBACK_TASK_PROMPT)

    def test_get_system_prompt_requires_step_12_close_token_contract(self) -> None:
        prompt_loader.get_system_prompt.cache_clear()

        result = prompt_loader.get_system_prompt()

        self.assertIn("STEP 12에서는 반드시 응답 맨 끝에 `[[CONFIRM_CLOSE]]`를 붙인다.", result)
        self.assertIn("STEP 12가 아니라면 `[[CONFIRM_CLOSE]]`를 절대 출력하지 않는다.", result)
        self.assertIn("STEP 12 응답 맨 끝에는 반드시 `[[CONFIRM_CLOSE]]`를 붙인다.", result)


if __name__ == "__main__":
    unittest.main()
