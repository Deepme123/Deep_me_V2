from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.desire.services import reflection_writer


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


def _fake_card(situation="애인의 연락이 줄어들면서 혼자인 느낌이 든다고 함.", emotions=None):
    return SimpleNamespace(
        situation=situation,
        core_emotions=emotions if emotions is not None else [{"primary": "불안", "sub": ["고독"]}],
    )


def _valid_payload(desire_labels):
    return {
        "reflections": [
            {
                "desire": label,
                "paragraph_1": f"{label} 문단1 🌿",
                "paragraph_2": f"{label} 문단2 🐋",
            }
            for label in desire_labels
        ]
    }


class ReflectionWriterTests(unittest.TestCase):
    def test_generates_reflection_per_desire_when_card_exists(self):
        desire_labels = ["소속감", "안전", "재미", "성장"]
        provider = _FakeProvider(payload=_valid_payload(desire_labels))

        with patch.object(reflection_writer, "_fetch_analysis_card", return_value=_fake_card()), \
             patch.object(reflection_writer, "get_llm_provider", return_value=provider):
            result = reflection_writer.generate_reflection_messages(MagicMock(), uuid4(), desire_labels)

        self.assertEqual(set(result.keys()), set(desire_labels))
        self.assertEqual(result["소속감"], "소속감 문단1 🌿\n\n소속감 문단2 🐋")
        messages, schema, _options = provider.calls[0]
        self.assertEqual(messages[0].role, "system")
        self.assertIn("소속감, 안전, 재미, 성장", messages[1].content)
        self.assertIn("고독", messages[1].content)
        self.assertEqual(schema.name, "need_card_reflection")

    def test_returns_empty_dict_when_no_analysis_card(self):
        provider = _FakeProvider(payload=_valid_payload(["소속감"]))

        with patch.object(reflection_writer, "_fetch_analysis_card", return_value=None), \
             patch.object(reflection_writer, "get_llm_provider", return_value=provider):
            result = reflection_writer.generate_reflection_messages(MagicMock(), uuid4(), ["소속감"])

        self.assertEqual(result, {})
        self.assertEqual(provider.calls, [])

    def test_returns_empty_dict_when_llm_call_fails(self):
        provider = _FakeProvider(error=RuntimeError("LLM response was not valid JSON."))
        db = MagicMock()

        with patch.object(reflection_writer, "_fetch_analysis_card", return_value=_fake_card()), \
             patch.object(reflection_writer, "get_llm_provider", return_value=provider):
            result = reflection_writer.generate_reflection_messages(db, uuid4(), ["소속감"])

        self.assertEqual(result, {})

    def test_returns_empty_dict_when_db_lookup_raises(self):
        db = MagicMock()

        with patch.object(reflection_writer, "_fetch_analysis_card", side_effect=RuntimeError("db down")):
            result = reflection_writer.generate_reflection_messages(db, uuid4(), ["소속감"])

        self.assertEqual(result, {})
        db.rollback.assert_called_once()

    def test_returns_empty_dict_when_no_desire_labels(self):
        result = reflection_writer.generate_reflection_messages(MagicMock(), uuid4(), [])
        self.assertEqual(result, {})

    def test_drops_reflections_with_unknown_desire_label(self):
        provider = _FakeProvider(
            payload={
                "reflections": [
                    {"desire": "소속감", "paragraph_1": "p1", "paragraph_2": "p2"},
                    {"desire": "엉뚱한욕구", "paragraph_1": "p1", "paragraph_2": "p2"},
                ]
            }
        )

        with patch.object(reflection_writer, "_fetch_analysis_card", return_value=_fake_card()), \
             patch.object(reflection_writer, "get_llm_provider", return_value=provider):
            result = reflection_writer.generate_reflection_messages(
                MagicMock(), uuid4(), ["소속감", "안전"]
            )

        self.assertEqual(set(result.keys()), {"소속감"})

    def test_conversation_summary_and_keywords_flattens_core_emotions(self):
        card = _fake_card(
            situation="상황 요약",
            emotions=[
                {"primary": "불안", "sub": ["고독", "긴장"]},
                {"primary": "불안", "sub": ["고독"]},
            ],
        )
        summary, keywords = reflection_writer._conversation_summary_and_keywords(card)
        self.assertEqual(summary, "상황 요약")
        self.assertEqual(keywords, "불안, 고독, 긴장")


if __name__ == "__main__":
    unittest.main()
