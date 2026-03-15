from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.llm import AnthropicProvider, LLMJsonSchema, LLMMessage


def _build_settings(model: str):
    return SimpleNamespace(
        provider="anthropic",
        model=model,
        temperature=0.25,
        max_tokens=256,
        timeout_sec=18.0,
        openai_api_key="",
        anthropic_api_key="anthropic-test-key",
    )


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _tool_block(name: str, payload):
    return SimpleNamespace(type="tool_use", name=name, input=payload)


class FakeMessagesStream:
    def __init__(self, pieces, *, final_message=None):
        self.text_stream = list(pieces)
        self._final_message = final_message or SimpleNamespace(content=[])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get_final_message(self):
        return self._final_message


class FakeMessagesAPI:
    def __init__(self, *, create_result=None, create_error=None, stream_result=None, stream_error=None):
        self.create_result = create_result
        self.create_error = create_error
        self.stream_result = stream_result
        self.stream_error = stream_error
        self.create_calls = []
        self.stream_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        if self.create_error is not None:
            raise self.create_error
        return self.create_result

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        if self.stream_error is not None:
            raise self.stream_error
        return self.stream_result


class FakeClient:
    def __init__(self, *, messages: FakeMessagesAPI):
        self.messages = messages
        self.with_options_calls = []

    def with_options(self, **kwargs):
        self.with_options_calls.append(kwargs)
        return self


def test_generate_text_uses_messages_api_and_system_prompt_separately():
    client = FakeClient(
        messages=FakeMessagesAPI(
            create_result=SimpleNamespace(content=[_text_block("hello "), _text_block("world")])
        )
    )
    provider = AnthropicProvider(settings=_build_settings("claude-sonnet-4-5"), client=client)

    result = provider.generate_text(
        messages=[
            LLMMessage(role="system", content="You are brief."),
            LLMMessage(role="assistant", content="Earlier reply"),
            LLMMessage(role="user", content="Say hi"),
        ]
    )

    assert result == "hello world"
    assert client.with_options_calls == [{"timeout": 18.0}]
    call = client.messages.create_calls[0]
    assert call["model"] == "claude-sonnet-4-5"
    assert call["system"] == "You are brief."
    assert call["messages"] == [
        {"role": "assistant", "content": "Earlier reply"},
        {"role": "user", "content": "Say hi"},
    ]


def test_stream_text_yields_text_stream_chunks():
    client = FakeClient(
        messages=FakeMessagesAPI(
            stream_result=FakeMessagesStream(["hel", "lo"], final_message=SimpleNamespace(content=[]))
        )
    )
    provider = AnthropicProvider(settings=_build_settings("claude-sonnet-4-5"), client=client)

    output = "".join(
        provider.stream_text(
            messages=[
                LLMMessage(role="system", content="System"),
                LLMMessage(role="user", content="User"),
            ]
        )
    )

    assert output == "hello"
    call = client.messages.stream_calls[0]
    assert call["system"] == "System"
    assert call["messages"] == [{"role": "user", "content": "User"}]


def test_generate_json_returns_tool_input_payload():
    client = FakeClient(
        messages=FakeMessagesAPI(
            create_result=SimpleNamespace(
                stop_reason="tool_use",
                content=[_tool_block("need_analysis", {"needs": []})],
            )
        )
    )
    provider = AnthropicProvider(settings=_build_settings("claude-sonnet-4-5"), client=client)

    result = provider.generate_json(
        messages=[
            LLMMessage(role="system", content="Return JSON."),
            LLMMessage(role="user", content="Analyze this."),
        ],
        schema=LLMJsonSchema(
            name="need_analysis",
            schema={"type": "object", "properties": {"needs": {"type": "array"}}},
        ),
    )

    assert result == {"needs": []}
    call = client.messages.create_calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "need_analysis"}
    assert call["disable_parallel_tool_use"] is True
    assert call["tools"][0]["name"] == "need_analysis"
    assert call["tools"][0]["strict"] is True
    assert call["tools"][0]["input_schema"] == {
        "type": "object",
        "properties": {"needs": {"type": "array"}},
    }


def test_generate_json_raises_when_tool_output_is_missing():
    client = FakeClient(
        messages=FakeMessagesAPI(
            create_result=SimpleNamespace(
                stop_reason="end_turn",
                content=[_text_block("not json")],
            )
        )
    )
    provider = AnthropicProvider(settings=_build_settings("claude-sonnet-4-5"), client=client)

    with pytest.raises(RuntimeError, match="Anthropic JSON generation failed"):
        provider.generate_json(
            messages=[LLMMessage(role="user", content="Analyze")],
            schema=LLMJsonSchema(name="need_analysis", schema={"type": "object"}),
        )
