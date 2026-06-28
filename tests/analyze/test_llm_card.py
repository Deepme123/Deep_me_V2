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


class _SequenceFakeProvider:
    """호출마다 결과를 순서대로 반환 — 재시도 시나리오 테스트용."""

    def __init__(self, results: list) -> None:
        self.results = list(results)
        self.calls = []

    def generate_json(self, *, messages, schema, options=None):
        self.calls.append((messages, schema, options))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


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
                "physical_reactions": [
                    {"title": "Tight chest", "description": "Chest tightened from pressure.", "primary": "불안"},
                    {"title": "Shallow breathing", "description": "Breath shortened when stressed.", "primary": "불안"},
                ],
                "coping_actions": ["took a short walk"],
                "tags": ["work", "stress"],
                "insight": "Rest and clearer boundaries may help.",
            }
        )

        with patch.object(llm_card, "get_card_provider", return_value=provider):
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
        self.assertIn(
            "keep schema keys in English, but write every summary, label, sentence, and list item in Korean.",
            messages[1].content,
        )
        self.assertEqual(schema.name, "analysis_card")

    def test_analyze_dialogue_to_card_falls_back_on_json_generation_failure(self) -> None:
        provider = _FakeProvider(error=RuntimeError("LLM response was not valid JSON."))

        with patch.object(llm_card, "get_card_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns())

        self.assertEqual(card.model_dump(), sc.CardCreate().model_dump())

    def test_analyze_dialogue_to_card_falls_back_on_schema_validation_failure(self) -> None:
        provider = _FakeProvider(
            payload={
                "summary": "The user is stressed.",
                "core_emotions": "anxiety",
            }
        )

        with patch.object(llm_card, "get_card_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns())

        self.assertEqual(card.model_dump(), sc.CardCreate().model_dump())

    def test_analyze_dialogue_to_card_passes_rich_transcript_details_to_prompt(self) -> None:
        provider = _FakeProvider(
            payload={
                "summary": "The user felt anxious in a team meeting.",
                "situation": "A team meeting at work.",
                "physical_reactions": [
                    {"title": "Tight chest", "description": "Chest tightened during the meeting.", "primary": "불안"},
                ],
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

        with patch.object(llm_card, "get_card_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(turns)

        self.assertEqual(card.situation, "A team meeting at work.")
        self.assertEqual(card.physical_reactions[0].title, "Tight chest")
        messages, _schema, _options = provider.calls[0]
        user_prompt = messages[1].content
        self.assertIn("team meeting", user_prompt)
        self.assertIn("felt anxious", user_prompt)
        self.assertIn("would freeze", user_prompt)
        self.assertIn("chest got tight", user_prompt)
        self.assertIn("avoided eye contact", user_prompt)


    def test_core_emotions_with_invalid_primary_label_are_dropped(self) -> None:
        provider = _FakeProvider(
            payload={
                "summary": "The user feels something.",
                "core_emotions": [
                    {"primary": "존재하지않는감정", "sub": ["아무말"]},
                    {"primary": "불안", "sub": ["긴장한"]},
                ],
            }
        )

        with patch.object(llm_card, "get_card_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns())

        # 분류 체계에 없는 primary 항목은 걸러지고, 유효한 항목만 남아야 한다.
        self.assertEqual(len(card.core_emotions), 1)
        self.assertEqual(card.core_emotions[0].primary, "불안")

    def test_core_emotions_all_invalid_falls_back_to_none_not_empty_card(self) -> None:
        provider = _FakeProvider(
            payload={
                "summary": "The user feels something.",
                "core_emotions": [{"primary": "존재하지않는감정", "sub": ["아무말"]}],
            }
        )

        with patch.object(llm_card, "get_card_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns())

        # core_emotions만 비어도 summary가 남아있으니 fallback이 아니라 부분 카드여야 한다.
        self.assertIsNone(card.core_emotions)
        self.assertEqual(card.summary, "The user feels something.")

    def test_physical_reaction_primary_label_is_not_validated_against_taxonomy(self) -> None:
        # 신규 발견: core_emotions의 primary는 _validate_emotion_entries로 분류 체계와
        # 대조해 걸러지지만, physical_reactions[].primary는 같은 검증을 거치지 않는다.
        # LLM이 분류 체계에 없는 레이블을 써도 그대로 통과한다.
        provider = _FakeProvider(
            payload={
                "summary": "Body reaction noted.",
                "physical_reactions": [
                    {
                        "title": "Tight chest",
                        "description": "Chest tightened.",
                        "primary": "분류체계에없는감정",
                    }
                ],
            }
        )

        with patch.object(llm_card, "get_card_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns())

        self.assertEqual(card.physical_reactions[0].primary, "분류체계에없는감정")

    def test_behavior_pattern_primary_label_is_not_validated_against_taxonomy(self) -> None:
        # 신규 발견: behavior_patterns[].primary도 physical_reactions와 동일하게
        # 분류 체계 검증을 거치지 않고 그대로 통과한다.
        provider = _FakeProvider(
            payload={
                "summary": "Behavior noted.",
                "behavior_patterns": [
                    {
                        "title": "Avoidance",
                        "primary": "분류체계에없는감정",
                        "items": ["미루기"],
                    }
                ],
            }
        )

        with patch.object(llm_card, "get_card_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns())

        self.assertEqual(card.behavior_patterns[0].primary, "분류체계에없는감정")

    def test_situation_step_interpretation_count_is_not_enforced_outside_llm_schema(self) -> None:
        # 신규 발견: JSON 스키마(_CARD_SCHEMA)는 interpretations에 minItems=3,
        # maxItems=3을 요구하지만, 이를 검증하는 pydantic 모델(_SituationStep)에는
        # 길이 제약이 전혀 없다. OpenAI strict 모드는 스키마를 강제하지만 Anthropic
        # tool-use는 JSON Schema의 minItems/maxItems를 항상 강제하지 않으므로,
        # 프로바이더에 따라 1개 또는 5개짜리 interpretations가 그대로 저장될 수 있다.
        provider = _FakeProvider(
            payload={
                "summary": "Situation noted.",
                "situation_steps": [
                    {
                        "title": "Step",
                        "description": "Something happened.",
                        "interpretations": ["해석 한 개뿐"],
                    }
                ],
            }
        )

        with patch.object(llm_card, "get_card_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns())

        self.assertEqual(len(card.situation_steps[0].interpretations), 1)

    def test_retries_once_after_transient_failure_then_succeeds(self) -> None:
        # P1-1 회귀 테스트: 첫 시도가 트랜지언트 오류로 실패해도, 재시도에서
        # 성공하면 fallback이 아니라 실제 카드를 돌려줘야 한다.
        provider = _SequenceFakeProvider(
            [
                RuntimeError("OpenAI JSON generation was truncated by max_output_tokens."),
                {"summary": "Recovered on retry."},
            ]
        )

        with patch.object(llm_card, "get_card_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns())

        self.assertEqual(card.summary, "Recovered on retry.")
        self.assertEqual(len(provider.calls), 2)

    def test_falls_back_only_after_all_attempts_exhausted(self) -> None:
        provider = _SequenceFakeProvider(
            [
                RuntimeError("first failure"),
                RuntimeError("second failure"),
            ]
        )

        with patch.object(llm_card, "get_card_provider", return_value=provider):
            card = llm_card.analyze_dialogue_to_card(_build_turns())

        self.assertEqual(card.model_dump(), sc.CardCreate().model_dump())
        self.assertEqual(len(provider.calls), 2)


if __name__ == "__main__":
    unittest.main()
