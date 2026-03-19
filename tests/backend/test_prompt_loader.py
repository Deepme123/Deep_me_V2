from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.backend.core import prompt_loader


class PromptLoaderTests(unittest.TestCase):
    def tearDown(self) -> None:
        prompt_loader.get_task_prompt.cache_clear()

    def test_get_task_prompt_returns_fallback_when_file_is_missing(self) -> None:
        missing_path = Path(tempfile.gettempdir()) / "missing-task-prompt-for-test.txt"
        if missing_path.exists():
            missing_path.unlink()

        with patch.object(prompt_loader, "TASK_PROMPT_PATH", missing_path):
            prompt_loader.get_task_prompt.cache_clear()
            result = prompt_loader.get_task_prompt()

        self.assertEqual(result, prompt_loader.FALLBACK_TASK_PROMPT)


if __name__ == "__main__":
    unittest.main()
