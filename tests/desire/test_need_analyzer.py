from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from app.desire.services import need_analyzer


class _FakeProvider:
    def __init__(self, *, payload=None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls = []

    def generate_json(self, *, messages, schema, options=None):
        self.calls.append((messages, schema, options))
        if self.error is not None:
            raise self.error
        return self.payload


def _valid_need_payload():
    codes = [code.value for code in need_analyzer.NeedCode]
    return {
        "needs": [
            {
                "code": code,
                "score": 100 - (idx * 5),
                "rank": idx + 1,
                "rationale": f"signal-{code.lower()}",
            }
            for idx, code in enumerate(codes)
        ]
    }


class NeedAnalyzerTests(unittest.TestCase):
    def test_analyze_needs_uses_common_generate_json_contract(self) -> None:
        provider = _FakeProvider(payload=_valid_need_payload())

        with patch.object(need_analyzer, "get_llm_provider", return_value=provider):
            result = asyncio.run(need_analyzer.analyze_needs("I need more stability in my life."))

        self.assertEqual(len(result.needs), 8)
        self.assertEqual(len(result.top4), 4)
        self.assertEqual(result.needs[0].rank, 1)
        messages, schema, _options = provider.calls[0]
        self.assertEqual(messages[0].role, "system")
        self.assertIn("stability", messages[1].content)
        self.assertEqual(schema.name, "need_analysis")

    def test_analyze_needs_falls_back_on_json_generation_failure(self) -> None:
        provider = _FakeProvider(error=RuntimeError("LLM response was not valid JSON."))

        with patch.object(need_analyzer, "get_llm_provider", return_value=provider):
            result = asyncio.run(need_analyzer.analyze_needs("Conversation text"))

        self.assertEqual(
            [item.score for item in result.needs],
            [need_analyzer.DEFAULT_NEED_SCORE] * 8,
        )
        self.assertEqual([item.rank for item in result.needs], list(range(1, 9)))
        self.assertEqual(len(result.top4), 4)

    def test_analyze_needs_falls_back_on_schema_validation_failure(self) -> None:
        provider = _FakeProvider(payload={"needs": [{"code": "Choice"}]})

        with patch.object(need_analyzer, "get_llm_provider", return_value=provider):
            result = asyncio.run(need_analyzer.analyze_needs("Conversation text"))

        self.assertEqual(
            [item.score for item in result.needs],
            [need_analyzer.DEFAULT_NEED_SCORE] * 8,
        )
        self.assertEqual([item.rank for item in result.needs], list(range(1, 9)))


if __name__ == "__main__":
    unittest.main()
