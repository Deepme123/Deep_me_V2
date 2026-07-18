from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

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
                "reflection_message": f"reflection-{code.lower()}",
            }
            for idx, code in enumerate(codes)
        ]
    }


class NeedAnalyzerTests(unittest.TestCase):
    def test_analyze_needs_uses_common_generate_json_contract(self) -> None:
        provider = _FakeProvider(payload=_valid_need_payload())

        with patch.object(need_analyzer, "get_llm_provider", return_value=provider), \
             patch.object(need_analyzer, "save_need_card_result"):
            result = asyncio.run(need_analyzer.analyze_needs(
                "I need more stability in my life.", uuid4(), MagicMock()
            ))

        self.assertEqual(len(result.needs), 8)
        self.assertEqual(len(result.top4), 4)
        self.assertEqual(result.needs[0].rank, 1)
        self.assertEqual(
            result.needs[0].reflection_message,
            f"reflection-{result.needs[0].code.lower()}",
        )
        messages, schema, _options = provider.calls[0]
        self.assertEqual(messages[0].role, "system")
        self.assertIn("stability", messages[1].content)
        self.assertEqual(schema.name, "need_analysis")

    def test_analyze_needs_falls_back_on_json_generation_failure(self) -> None:
        provider = _FakeProvider(error=RuntimeError("LLM response was not valid JSON."))

        with patch.object(need_analyzer, "get_llm_provider", return_value=provider), \
             patch.object(need_analyzer, "save_need_card_result"):
            result = asyncio.run(need_analyzer.analyze_needs("Conversation text", uuid4(), MagicMock()))

        self.assertEqual(
            [item.score for item in result.needs],
            [need_analyzer.DEFAULT_NEED_SCORE] * 8,
        )
        self.assertEqual([item.rank for item in result.needs], list(range(1, 9)))
        self.assertEqual(len(result.top4), 4)

    def test_analyze_needs_falls_back_on_schema_validation_failure(self) -> None:
        provider = _FakeProvider(payload={"needs": [{"code": "Choice"}]})

        with patch.object(need_analyzer, "get_llm_provider", return_value=provider), \
             patch.object(need_analyzer, "save_need_card_result"):
            result = asyncio.run(need_analyzer.analyze_needs("Conversation text", uuid4(), MagicMock()))

        self.assertEqual(
            [item.score for item in result.needs],
            [need_analyzer.DEFAULT_NEED_SCORE] * 8,
        )
        self.assertEqual([item.rank for item in result.needs], list(range(1, 9)))


class PersonalizationHintTests(unittest.TestCase):
    def test_build_hint_returns_empty_when_no_selections(self) -> None:
        self.assertEqual(need_analyzer._build_personalization_hint([]), "")

    def test_build_hint_summarizes_top_frequent_codes(self) -> None:
        selections = [
            MagicMock(selected_codes=["Together"]),
            MagicMock(selected_codes=["Together"]),
            MagicMock(selected_codes=["Together"]),
            MagicMock(selected_codes=["Peace"]),
            MagicMock(selected_codes=["Peace"]),
            MagicMock(selected_codes=["Grow"]),
        ]

        hint = need_analyzer._build_personalization_hint(selections)

        self.assertIn("소속감", hint)
        self.assertIn("평온", hint)
        self.assertNotIn("성장", hint)

    def test_call_llm_includes_hint_section_when_present(self) -> None:
        provider = _FakeProvider(payload=_valid_need_payload())

        with patch.object(need_analyzer, "get_llm_provider", return_value=provider):
            need_analyzer._call_llm("conversation", personalization_hint="자율, 안전")

        messages, _schema, _options = provider.calls[0]
        self.assertIn("자율, 안전", messages[1].content)

    def test_call_llm_omits_hint_section_when_absent(self) -> None:
        provider = _FakeProvider(payload=_valid_need_payload())

        with patch.object(need_analyzer, "get_llm_provider", return_value=provider):
            need_analyzer._call_llm("conversation")

        messages, _schema, _options = provider.calls[0]
        self.assertNotIn("참고용 사용자 성향 힌트", messages[1].content)


if __name__ == "__main__":
    unittest.main()
