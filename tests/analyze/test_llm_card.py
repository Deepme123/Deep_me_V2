from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")

from app.analyze import schemas as sc
from app.analyze.services import llm_card


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


def _build_turns() -> list[sc.ConversationTurn]:
    return [
        sc.ConversationTurn(role="user", speaker="USER", text="I am overwhelmed at work."),
        sc.ConversationTurn(role="assistant", speaker="NOA", text="What feels heaviest right now?"),
    ]


class LLMCardTests(unittest.TestCase):
    def test_analyze_dialogue_to_card_uses_common_generate_json_contract(self) -> None:
        provider = _FakeProvider(
            payload={
                "summary": "The user feels overwhelmed by work pressure.",
                "core_emotions": [
                    {"primary": "불안", "sub": ["긴장한", "걱정되는"]},
                    {"primary": "피곤", "sub": ["지친"]},
                ],
                "situation": "Heavy workload and pressure.",
                "emotion": "The user feels tense and exhausted.",
                "thoughts": "They feel they might fall behind.",
                "physical_reactions": "Tight chest and shallow breathing.",
                "behaviors": "They avoid resting and keep pushing.",
                "coping_actions": ["took a short walk"],
                "tags": ["work", "stress"],
                "insight": "Rest and clearer boundaries may help.",
            }
        )

        with patch.object(llm_card, "_get_card_llm_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns(), title_hint="work stress")

        self.assertEqual(card.summary, "The user feels overwhelmed by work pressure.")
        self.assertEqual(
            card.core_emotions,
            [
                sc.EmotionEntry(primary="불안", sub=["긴장한", "걱정되는"]),
                sc.EmotionEntry(primary="피곤", sub=["지친"]),
            ],
        )
        messages, schema, _options = provider.calls[0]
        self.assertEqual(messages[0].role, "system")
        self.assertIn("[감정 분류 체계", messages[0].content)
        self.assertIn("불안", messages[0].content)
        self.assertIn("work stress", messages[1].content)
        self.assertEqual(schema.name, "emotion_card")

    def test_analyze_dialogue_to_card_falls_back_on_json_generation_failure(self) -> None:
        provider = _FakeProvider(error=RuntimeError("LLM response was not valid JSON."))

        with patch.object(llm_card, "_get_card_llm_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns())

        self.assertEqual(card.model_dump(), sc.CardCreate().model_dump())

    def test_analyze_dialogue_to_card_falls_back_on_schema_validation_failure(self) -> None:
        provider = _FakeProvider(
            payload={
                "summary": "The user is stressed.",
                "core_emotions": "anxiety",
            }
        )

        with patch.object(llm_card, "_get_card_llm_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns())

        self.assertEqual(card.model_dump(), sc.CardCreate().model_dump())

    def test_analyze_dialogue_to_card_passes_rich_transcript_details_to_prompt(self) -> None:
        provider = _FakeProvider(
            payload={
                "summary": "The user felt anxious in a team meeting.",
                "situation": "A team meeting at work.",
                "emotion": "Anxious and afraid.",
                "thoughts": "They thought they would freeze.",
                "physical_reactions": "Tight chest.",
                "behaviors": "Avoided eye contact.",
            }
        )
        turns = [
            sc.ConversationTurn(
                role="user",
                speaker="USER",
                text="In today's team meeting I felt anxious.",
            ),
            sc.ConversationTurn(
                role="assistant",
                speaker="NOA",
                text="What went through your mind and body in that moment?",
            ),
            sc.ConversationTurn(
                role="user",
                speaker="USER",
                text="I thought I would freeze, my chest got tight, and I avoided eye contact.",
            ),
        ]

        with patch.object(llm_card, "_get_card_llm_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(turns)

        self.assertEqual(card.situation, "A team meeting at work.")
        self.assertEqual(card.emotion, "Anxious and afraid.")
        self.assertEqual(card.thoughts, "They thought they would freeze.")
        self.assertEqual(card.physical_reactions, "Tight chest.")
        self.assertEqual(card.behaviors, "Avoided eye contact.")
        messages, _schema, _options = provider.calls[0]
        user_prompt = messages[1].content
        self.assertIn("team meeting", user_prompt)
        self.assertIn("felt anxious", user_prompt)
        self.assertIn("would freeze", user_prompt)
        self.assertIn("chest got tight", user_prompt)
        self.assertIn("avoided eye contact", user_prompt)


if __name__ == "__main__":
    unittest.main()
