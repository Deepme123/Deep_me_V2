from __future__ import annotations

import unittest
from unittest.mock import patch

from app.backend.services import task_llm_service


class _FakeProvider:
    def __init__(self, *, text: str = "", payload=None) -> None:
        self.text = text
        self.payload = payload
        self.text_calls = []
        self.json_calls = []

    def generate_text(self, *, messages, options=None):
        self.text_calls.append((messages, options))
        return self.text

    def stream_text(self, *, messages, options=None):  # pragma: no cover
        raise NotImplementedError

    def generate_json(self, *, messages, schema, options=None):
        self.json_calls.append((messages, schema, options))
        return self.payload


class TaskLLMServiceTests(unittest.TestCase):
    def test_get_task_llm_provider_uses_common_factory_defaults(self) -> None:
        sentinel = object()

        with patch.object(task_llm_service, "create_llm_provider", return_value=sentinel) as mocked:
            result = task_llm_service._get_task_llm_provider()

        self.assertIs(result, sentinel)
        mocked.assert_called_once_with(
            model_default="gpt-3.5-turbo",
            temperature_default=0.7,
            max_tokens_default=800,
        )

    def test_recommend_task_drafts_from_prompt_parses_legacy_text(self) -> None:
        provider = _FakeProvider(
            text="1. 제목: 산책하기\n설명: 10분만 밖으로 나가자.\n2. 제목: 물 마시기\n설명: 천천히 한 컵 마신다."
        )

        with patch.object(task_llm_service, "_get_task_llm_provider", return_value=provider):
            with patch.object(task_llm_service, "get_task_prompt", return_value="system prompt"):
                drafts = task_llm_service.recommend_task_drafts_from_prompt()

        self.assertEqual(
            drafts,
            [
                task_llm_service.TaskDraft(title="산책하기", description="10분만 밖으로 나가자."),
                task_llm_service.TaskDraft(title="물 마시기", description="천천히 한 컵 마신다."),
            ],
        )
        messages, _options = provider.text_calls[0]
        self.assertEqual(messages[0].content, "system prompt")
        self.assertEqual(messages[1].content, "지금 나에게 추천해줘.")

    def test_recommend_task_drafts_from_session_context_uses_json_generation(self) -> None:
        provider = _FakeProvider(
            payload=[
                {"title": "호흡 정리", "description": "1분 동안 숨 고르기"},
                {"title": "메모하기", "description": "지금 감정을 적기"},
            ]
        )
        context = task_llm_service.TaskRecommendationContext(
            emotion_label="불안",
            topic="회사",
            history_snippet="유저: 너무 불안해\nGPT: 조금 천천히 보자",
        )

        with patch.object(task_llm_service, "_get_task_llm_provider", return_value=provider):
            with patch.object(task_llm_service, "get_task_prompt", return_value="task prompt"):
                drafts = task_llm_service.recommend_task_drafts_from_session_context(
                    context=context,
                    n=1,
                )

        self.assertEqual(
            drafts,
            [task_llm_service.TaskDraft(title="호흡 정리", description="1분 동안 숨 고르기")],
        )
        messages, schema, _options = provider.json_calls[0]
        self.assertEqual(schema.name, "task_recommendations")
        self.assertIn("불안", messages[1].content)
        self.assertIn("추천 개수: 1", messages[1].content)

    def test_recommend_task_drafts_from_session_context_rejects_invalid_payload(self) -> None:
        provider = _FakeProvider(payload={"title": "not-a-list"})

        with patch.object(task_llm_service, "_get_task_llm_provider", return_value=provider):
            with patch.object(task_llm_service, "get_task_prompt", return_value="task prompt"):
                with self.assertRaisesRegex(RuntimeError, "GPT 응답 파싱 실패"):
                    task_llm_service.recommend_task_drafts_from_session_context(
                        context=task_llm_service.TaskRecommendationContext(),
                        n=3,
                    )


if __name__ == "__main__":
    unittest.main()
