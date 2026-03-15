from __future__ import annotations

import unittest
from unittest.mock import patch

from app.backend.services import llm_service


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
