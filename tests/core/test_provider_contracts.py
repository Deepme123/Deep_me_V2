from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.llm import LLMJsonSchema, LLMMessage
from app.core.llm import factory
from app.core.llm.anthropic_provider import AnthropicProvider as RealAnthropicProvider
from app.core.llm.openai_provider import OpenAIProvider as RealOpenAIProvider


def _build_settings(*, provider: str, model: str):
    return SimpleNamespace(
        provider=provider,
        model=model,
        temperature=0.2,
        max_tokens=128,
        timeout_sec=9.0,
        openai_api_key="openai-test-key",
        anthropic_api_key="anthropic-test-key",
    )


def _messages() -> list[LLMMessage]:
    return [
        LLMMessage(role="system", content="You are concise."),
        LLMMessage(role="assistant", content="Earlier reply"),
        LLMMessage(role="user", content="Say hello"),
    ]


def _json_messages() -> list[LLMMessage]:
    return [
        LLMMessage(role="system", content="Return JSON."),
        LLMMessage(role="user", content="Return status"),
    ]


def _json_schema() -> LLMJsonSchema:
    return LLMJsonSchema(
        name="provider_contract",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"status": {"type": "string"}},
            "required": ["status"],
        },
    )


def _openai_chunk(text: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
    )


def _anthropic_text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _anthropic_tool_block(name: str, payload):
    return SimpleNamespace(type="tool_use", name=name, input=payload)


class FakeChatCompletionsAPI:
    def __init__(self, *results) -> None:
        self._results = list(results)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._results:
            raise AssertionError("Unexpected extra chat completion call.")
        return self._results.pop(0)


class FakeOpenAIResponsesAPI:
    def __init__(self, *, json_result) -> None:
        self._json_result = json_result
        self.create_calls = []
        self.stream_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._json_result

    def stream(self, **kwargs):  # pragma: no cover
        self.stream_calls.append(kwargs)
        raise AssertionError("Responses streaming should not be used in this contract test.")


class FakeOpenAIClient:
    def __init__(self, *, chat_results, json_result) -> None:
        self.responses = FakeOpenAIResponsesAPI(
            json_result=json_result
        )
        self.chat = SimpleNamespace(
            completions=FakeChatCompletionsAPI(*chat_results)
        )


class FakeAnthropicMessagesStream:
    def __init__(self, pieces) -> None:
        self.text_stream = list(pieces)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get_final_message(self):
        return SimpleNamespace(content=[])


class FakeAnthropicMessagesAPI:
    def __init__(self, *create_results, stream_pieces) -> None:
        self._create_results = list(create_results)
        self._stream_pieces = list(stream_pieces)
        self.create_calls = []
        self.stream_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        if not self._create_results:
            raise AssertionError("Unexpected extra Anthropic create call.")
        return self._create_results.pop(0)

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        return FakeAnthropicMessagesStream(self._stream_pieces)


class FakeAnthropicClient:
    def __init__(self, *, create_results, stream_pieces) -> None:
        self.messages = FakeAnthropicMessagesAPI(
            *create_results,
            stream_pieces=stream_pieces,
        )
        self.with_options_calls = []

    def with_options(self, **kwargs):
        self.with_options_calls.append(kwargs)
        return self


def _make_openai_provider(settings, *, chat_results, json_result):
    return RealOpenAIProvider(
        settings=settings,
        client=FakeOpenAIClient(chat_results=chat_results, json_result=json_result),
    )


def _make_anthropic_provider(settings, *, create_results, stream_pieces):
    return RealAnthropicProvider(
        settings=settings,
        client=FakeAnthropicClient(
            create_results=create_results,
            stream_pieces=stream_pieces,
        ),
    )


def _patch_factory(monkeypatch, *, openai_builder, anthropic_builder):
    monkeypatch.setattr(factory, "OpenAIProvider", lambda *, settings: openai_builder(settings))
    monkeypatch.setattr(
        factory,
        "AnthropicProvider",
        lambda *, settings: anthropic_builder(settings),
    )


@pytest.mark.parametrize(
    ("provider_name", "model", "expected_type"),
    [
        ("openai", "gpt-4o-mini", RealOpenAIProvider),
        ("anthropic", "claude-sonnet-4-5", RealAnthropicProvider),
    ],
)
def test_provider_switch_preserves_text_contract(
    monkeypatch,
    provider_name: str,
    model: str,
    expected_type,
):
    _patch_factory(
        monkeypatch,
        openai_builder=lambda settings: _make_openai_provider(
            settings,
            chat_results=[[_openai_chunk("text-"), _openai_chunk("ok")]],
            json_result=SimpleNamespace(output_text='{"status":"ok"}'),
        ),
        anthropic_builder=lambda settings: _make_anthropic_provider(
            settings,
            create_results=[SimpleNamespace(content=[_anthropic_text_block("text-ok")])],
            stream_pieces=["stream-", "ok"],
        ),
    )

    provider = factory.create_llm_provider_from_settings(
        _build_settings(provider=provider_name, model=model)
    )

    result = provider.generate_text(messages=_messages())

    assert isinstance(provider, expected_type)
    assert result == "text-ok"


@pytest.mark.parametrize(
    "provider_name, model",
    [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-sonnet-4-5"),
    ],
)
def test_provider_switch_preserves_stream_contract(
    monkeypatch,
    provider_name: str,
    model: str,
):
    _patch_factory(
        monkeypatch,
        openai_builder=lambda settings: _make_openai_provider(
            settings,
            chat_results=[[_openai_chunk("stream-"), _openai_chunk("ok")]],
            json_result=SimpleNamespace(output_text='{"status":"ok"}'),
        ),
        anthropic_builder=lambda settings: _make_anthropic_provider(
            settings,
            create_results=[SimpleNamespace(content=[_anthropic_text_block("text-ok")])],
            stream_pieces=["stream-", "ok"],
        ),
    )

    provider = factory.create_llm_provider_from_settings(
        _build_settings(provider=provider_name, model=model)
    )

    result = list(provider.stream_text(messages=_messages()))

    assert result == ["stream-", "ok"]


@pytest.mark.parametrize(
    "provider_name, model",
    [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-sonnet-4-5"),
    ],
)
def test_provider_switch_preserves_json_contract(
    monkeypatch,
    provider_name: str,
    model: str,
):
    _patch_factory(
        monkeypatch,
        openai_builder=lambda settings: _make_openai_provider(
            settings,
            chat_results=[[_openai_chunk("stream-"), _openai_chunk("ok")]],
            json_result=SimpleNamespace(output_text='{"status":"ok"}'),
        ),
        anthropic_builder=lambda settings: _make_anthropic_provider(
            settings,
            create_results=[
                SimpleNamespace(
                    stop_reason="tool_use",
                    content=[_anthropic_tool_block("provider_contract", {"status": "ok"})],
                )
            ],
            stream_pieces=["stream-", "ok"],
        ),
    )

    provider = factory.create_llm_provider_from_settings(
        _build_settings(provider=provider_name, model=model)
    )

    result = provider.generate_json(messages=_json_messages(), schema=_json_schema())

    assert result == {"status": "ok"}
