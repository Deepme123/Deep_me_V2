from __future__ import annotations

from types import SimpleNamespace

from app.core.llm import LLMJsonSchema, LLMMessage, OpenAIProvider


def _build_settings(model: str):
    return SimpleNamespace(
        provider="openai",
        model=model,
        temperature=0.3,
        max_tokens=256,
        timeout_sec=12.0,
        openai_api_key="test-key",
        anthropic_api_key="",
    )


def _make_chunk(text: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=text),
            )
        ]
    )


class FakeStreamContext:
    def __init__(self, events, final_response=None):
        self._events = list(events)
        self._final_response = final_response or SimpleNamespace(output_text="")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._events)

    def get_final_response(self):
        return self._final_response


class FakeResponsesAPI:
    def __init__(self, *, create_result=None, create_errors=None, stream_result=None, stream_error=None):
        self.create_result = create_result
        self.create_errors = list(create_errors or [])
        self.stream_result = stream_result
        self.stream_error = stream_error
        self.create_calls = []
        self.stream_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        if self.create_errors:
            raise self.create_errors.pop(0)
        return self.create_result

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        if self.stream_error is not None:
            raise self.stream_error
        return self.stream_result


class FakeChatCompletionsAPI:
    def __init__(self, *, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class FakeClient:
    def __init__(self, *, responses: FakeResponsesAPI, chat_result=None, chat_error=None):
        self.responses = responses
        self.chat = SimpleNamespace(
            completions=FakeChatCompletionsAPI(result=chat_result, error=chat_error)
        )


def test_generate_json_parses_responses_output_text():
    responses = FakeResponsesAPI(create_result=SimpleNamespace(output_text='{"ok": true}'))
    client = FakeClient(responses=responses)
    provider = OpenAIProvider(settings=_build_settings("gpt-4.1-mini"), client=client)

    result = provider.generate_json(
        messages=[
            LLMMessage(role="system", content="Return JSON."),
            LLMMessage(role="user", content="Ping"),
        ],
        schema=LLMJsonSchema(name="sample", schema={"type": "object"}),
    )

    assert result == {"ok": True}
    assert responses.create_calls[0]["model"] == "gpt-4.1-mini"
    assert responses.create_calls[0]["text"]["format"]["json_schema"]["name"] == "sample"


def test_generate_json_normalizes_openai_strict_schema_for_optional_fields():
    schema = LLMJsonSchema(
        name="sample",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string"},
                "tags": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "label": {"type": "string"},
                            "score": {"type": "integer"},
                        },
                        "required": ["label"],
                    },
                },
            },
            "required": ["summary"],
        },
    )

    normalized = schema.to_openai_response_format()["json_schema"]["schema"]

    assert normalized["required"] == ["summary", "tags"]
    assert normalized["properties"]["summary"]["type"] == "string"
    assert normalized["properties"]["tags"]["type"] == ["array", "null"]
    assert normalized["properties"]["tags"]["items"]["required"] == ["label", "score"]
    assert normalized["properties"]["tags"]["items"]["properties"]["score"]["type"] == [
        "integer",
        "null",
    ]


def test_generate_json_falls_back_to_legacy_responses_response_format():
    responses = FakeResponsesAPI(
        create_result=SimpleNamespace(output_text='{"ok": true}'),
        create_errors=[TypeError("got an unexpected keyword argument 'text'")],
    )
    client = FakeClient(responses=responses)
    provider = OpenAIProvider(settings=_build_settings("gpt-4.1-mini"), client=client)

    result = provider.generate_json(
        messages=[
            LLMMessage(role="system", content="Return JSON."),
            LLMMessage(role="user", content="Ping"),
        ],
        schema=LLMJsonSchema(name="sample", schema={"type": "object"}),
    )

    assert result == {"ok": True}
    assert "text" in responses.create_calls[0]
    assert responses.create_calls[1]["response_format"]["json_schema"]["name"] == "sample"


def test_stream_text_uses_primary_chat_model_for_non_reasoning_model():
    responses = FakeResponsesAPI()
    client = FakeClient(responses=responses, chat_result=[_make_chunk("hello "), _make_chunk("world")])
    provider = OpenAIProvider(settings=_build_settings("gpt-4o-mini"), client=client)

    output = "".join(
        provider.stream_text(
            messages=[
                LLMMessage(role="system", content="Be brief."),
                LLMMessage(role="user", content="Say hi"),
            ]
        )
    )

    assert output == "hello world"
    assert client.chat.completions.calls[0]["model"] == "gpt-4o-mini"
    assert responses.stream_calls == []


def test_stream_text_falls_back_from_reasoning_responses_to_chat_backups():
    responses = FakeResponsesAPI(stream_error=RuntimeError("responses failed"))
    client = FakeClient(responses=responses, chat_result=[_make_chunk("fallback")])
    provider = OpenAIProvider(
        settings=_build_settings("gpt-5-mini"),
        client=client,
        backup_models=("gpt-4o-mini",),
    )

    output = "".join(
        provider.stream_text(
            messages=[
                LLMMessage(role="system", content="System"),
                LLMMessage(role="user", content="User"),
            ]
        )
    )

    assert output == "fallback"
    assert responses.stream_calls[0]["model"] == "gpt-5-mini"
    assert client.chat.completions.calls[0]["model"] == "gpt-4o-mini"


def test_responses_input_uses_output_text_for_assistant_history():
    provider = OpenAIProvider(settings=_build_settings("gpt-5-mini"), client=FakeClient(responses=FakeResponsesAPI()))

    payload = provider._to_responses_input(
        [
            LLMMessage(role="system", content="System"),
            LLMMessage(role="assistant", content="Earlier reply"),
            LLMMessage(role="user", content="Latest user message"),
        ]
    )

    assert payload[0]["content"] == [{"type": "input_text", "text": "System"}]
    assert payload[1]["content"] == [{"type": "output_text", "text": "Earlier reply"}]
    assert payload[2]["content"] == [{"type": "input_text", "text": "Latest user message"}]
