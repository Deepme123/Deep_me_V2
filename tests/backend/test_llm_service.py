from __future__ import annotations

import unittest
from unittest.mock import patch

from app.backend.services import llm_service
from app.core.llm_settings import LLMSettings


class _FakeProvider:
    def __init__(self) -> None:
        self.generate_calls = []
        self.stream_calls = []

    def generate_text(self, *, messages, options=None):
        self.generate_calls.append((messages, options))
        return "generated"

    def stream_text(self, *, messages, options=None):
        self.stream_calls.append((messages, options))
        yield "hello "
        yield "world"

    def generate_json(self, *, messages, schema, options=None):  # pragma: no cover
        raise NotImplementedError


class LLMServiceTests(unittest.TestCase):
    def test_get_backend_llm_settings_uses_common_defaults(self) -> None:
        settings = LLMSettings(
            provider="openai",
            model="gpt-test",
            temperature=0.1,
            max_tokens=222,
            timeout_sec=45.0,
            openai_api_key="",
            anthropic_api_key="",
        )

        with patch.object(llm_service, "get_llm_settings", return_value=settings) as mocked:
            result = llm_service._get_backend_llm_settings()

        self.assertIs(result, settings)
        mocked.assert_called_once_with(
            model_default="gpt-4o-mini",
            timeout_default=60.0,
        )

    def test_get_backend_llm_provider_uses_resolved_settings(self) -> None:
        sentinel = object()
        settings = LLMSettings(
            provider="openai",
            model="gpt-test",
            temperature=0.1,
            max_tokens=222,
            timeout_sec=45.0,
            openai_api_key="",
            anthropic_api_key="",
        )

        with (
            patch.object(llm_service, "_get_backend_llm_settings", return_value=settings),
            patch.object(llm_service, "create_llm_provider_from_settings", return_value=sentinel) as mocked,
        ):
            result = llm_service._get_backend_llm_provider()

        self.assertIs(result, sentinel)
        mocked.assert_called_once_with(settings)

    def test_get_backend_llm_info_returns_resolved_provider_and_model(self) -> None:
        settings = LLMSettings(
            provider="anthropic",
            model="claude-test",
            temperature=0.1,
            max_tokens=222,
            timeout_sec=45.0,
            openai_api_key="",
            anthropic_api_key="",
        )

        with patch.object(llm_service, "_get_backend_llm_settings", return_value=settings):
            info = llm_service.get_backend_llm_info()
            overridden = llm_service.get_backend_llm_info(model=" claude-override ")

        self.assertEqual(info.provider, "anthropic")
        self.assertEqual(info.model, "claude-test")
        self.assertEqual(overridden.provider, "anthropic")
        self.assertEqual(overridden.model, "claude-override")

    def test_generate_noa_response_uses_common_provider_messages(self) -> None:
        provider = _FakeProvider()

        with patch.object(llm_service, "_get_backend_llm_provider", return_value=provider):
            result = llm_service.generate_noa_response(
                system_prompt="sys",
                task_prompt="task",
                conversation=[("assistant", "earlier"), ("user", "latest")],
                temperature=0.4,
                max_tokens=321,
                model="gpt-test",
            )

        self.assertEqual(result, "generated")
        messages, options = provider.generate_calls[0]
        self.assertEqual(
            [(message.role, message.content) for message in messages],
            [
                ("system", "sys\n\n---\n[Task Prompt]\ntask"),
                ("assistant", "earlier"),
                ("user", "latest"),
            ],
        )
        self.assertEqual(options.temperature, 0.4)
        self.assertEqual(options.max_tokens, 321)
        self.assertEqual(options.model, "gpt-test")

    def test_stream_noa_response_yields_provider_chunks(self) -> None:
        provider = _FakeProvider()

        with patch.object(llm_service, "_get_backend_llm_provider", return_value=provider):
            chunks = list(
                llm_service.stream_noa_response(
                    system_prompt="sys",
                    task_prompt=None,
                    conversation=[("user", "hello")],
                )
            )

        self.assertEqual(chunks, ["hello ", "world"])
        messages, options = provider.stream_calls[0]
        self.assertEqual([(message.role, message.content) for message in messages], [("system", "sys"), ("user", "hello")])
        self.assertEqual(options.max_tokens, 800)


if __name__ == "__main__":
    unittest.main()
