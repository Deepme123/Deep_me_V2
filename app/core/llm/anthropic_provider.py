from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator, Sequence

from .base import LLMProvider
from .types import JSONValue, LLMJsonSchema, LLMMessage, LLMRequestOptions

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.core.llm_settings import LLMSettings

_TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

try:
    from anthropic import APIError, Anthropic  # type: ignore
except ImportError:  # pragma: no cover
    Anthropic = None  # type: ignore

    class APIError(Exception):
        pass


@dataclass(frozen=True)
class _ResolvedOptions:
    model: str
    temperature: float
    max_tokens: int
    timeout_sec: float


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        *,
        settings: LLMSettings,
        client: Any | None = None,
    ) -> None:
        self._settings = settings
        self._client = client

    def generate_text(
        self,
        *,
        messages: Sequence[LLMMessage],
        options: LLMRequestOptions | None = None,
    ) -> str:
        resolved = self._resolve_options(options)
        client = self._get_request_client(timeout_sec=resolved.timeout_sec)
        params = self._build_message_params(messages=messages)
        try:
            response = client.messages.create(
                model=resolved.model,
                max_tokens=resolved.max_tokens,
                temperature=resolved.temperature,
                **params,
            )
            return self._extract_text_response(response)
        except Exception as exc:
            raise RuntimeError(
                f"Anthropic text generation failed for model={resolved.model}: {exc}"
            ) from exc

    def stream_text(
        self,
        *,
        messages: Sequence[LLMMessage],
        options: LLMRequestOptions | None = None,
    ) -> Iterator[str]:
        resolved = self._resolve_options(options)
        client = self._get_request_client(timeout_sec=resolved.timeout_sec)
        params = self._build_message_params(messages=messages)

        try:
            with client.messages.stream(
                model=resolved.model,
                max_tokens=resolved.max_tokens,
                temperature=resolved.temperature,
                **params,
            ) as stream:
                emitted = False
                for piece in getattr(stream, "text_stream", None) or ():
                    if piece:
                        emitted = True
                        yield piece

                if not emitted:
                    final_message = stream.get_final_message()
                    final_text = self._extract_text_response(final_message)
                    if final_text:
                        yield final_text
        except Exception as exc:
            raise RuntimeError(
                f"Anthropic text streaming failed for model={resolved.model}: {exc}"
            ) from exc

    def generate_json(
        self,
        *,
        messages: Sequence[LLMMessage],
        schema: LLMJsonSchema,
        options: LLMRequestOptions | None = None,
    ) -> JSONValue:
        resolved = self._resolve_options(options)
        client = self._get_request_client(timeout_sec=resolved.timeout_sec)
        params = self._build_message_params(messages=messages)
        tool_name = self._validate_tool_name(schema.name)
        tool = {
            "name": tool_name,
            "description": "Return JSON matching the provided schema exactly.",
            "input_schema": dict(schema.schema),
            "strict": schema.strict,
        }

        try:
            response = client.messages.create(
                model=resolved.model,
                max_tokens=resolved.max_tokens,
                temperature=resolved.temperature,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                disable_parallel_tool_use=True,
                **params,
            )
            return self._extract_tool_input(response=response, tool_name=tool_name)
        except Exception as exc:
            raise RuntimeError(
                f"Anthropic JSON generation failed for model={resolved.model}: {exc}"
            ) from exc

    def _resolve_options(self, options: LLMRequestOptions | None) -> _ResolvedOptions:
        if options is None:
            return _ResolvedOptions(
                model=self._settings.model,
                temperature=self._settings.temperature,
                max_tokens=max(1, int(self._settings.max_tokens)),
                timeout_sec=self._settings.timeout_sec,
            )

        resolved_model = (options.model or self._settings.model).strip() or self._settings.model
        resolved_temperature = (
            self._settings.temperature if options.temperature is None else float(options.temperature)
        )
        resolved_max_tokens = (
            self._settings.max_tokens if options.max_tokens is None else int(options.max_tokens)
        )
        resolved_timeout = (
            self._settings.timeout_sec
            if options.timeout_sec is None
            else float(options.timeout_sec)
        )
        return _ResolvedOptions(
            model=resolved_model,
            temperature=resolved_temperature,
            max_tokens=max(1, resolved_max_tokens),
            timeout_sec=resolved_timeout,
        )

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if Anthropic is None:
            raise RuntimeError("anthropic package is not installed. Check requirements.txt.")
        if not self._settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured.")
        return Anthropic(api_key=self._settings.anthropic_api_key)

    def _get_request_client(self, *, timeout_sec: float) -> Any:
        client = self._get_client()
        if hasattr(client, "with_options"):
            return client.with_options(timeout=timeout_sec)
        return client

    def _build_message_params(self, *, messages: Sequence[LLMMessage]) -> dict[str, Any]:
        system_parts: list[str] = []
        conversation: list[dict[str, str]] = []

        for message in messages:
            if message.role == "system":
                if message.content:
                    system_parts.append(message.content)
                continue
            conversation.append({"role": message.role, "content": message.content})

        if not conversation:
            raise ValueError("Anthropic requests require at least one non-system message.")

        params: dict[str, Any] = {"messages": conversation}
        if system_parts:
            params["system"] = "\n\n".join(system_parts)
        return params

    def _extract_text_response(self, response: Any) -> str:
        fragments: list[str] = []
        for block in self._iter_content_blocks(response):
            if self._block_type(block) != "text":
                continue
            text = self._read_block_value(block, "text")
            if text:
                fragments.append(text)

        if fragments:
            return "".join(fragments)

        raise ValueError("Unable to read text from Anthropic response.")

    def _extract_tool_input(self, *, response: Any, tool_name: str) -> JSONValue:
        for block in self._iter_content_blocks(response):
            if self._block_type(block) != "tool_use":
                continue
            if self._read_block_value(block, "name") != tool_name:
                continue

            payload = self._read_block_input(block)
            if isinstance(payload, (dict, list, str, int, float, bool)) or payload is None:
                return payload
            raise RuntimeError("Anthropic tool output was not JSON-serializable.")

        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "max_tokens":
            raise RuntimeError("Anthropic JSON generation hit max_tokens before tool output.")
        raise RuntimeError("Anthropic response did not include the requested tool output.")

    def _iter_content_blocks(self, response: Any) -> list[Any]:
        content = getattr(response, "content", None)
        if content is None and isinstance(response, dict):
            content = response.get("content")
        if not content:
            return []
        return list(content)

    def _block_type(self, block: Any) -> str | None:
        value = getattr(block, "type", None)
        if value is None and isinstance(block, dict):
            value = block.get("type")
        return value

    def _read_block_value(self, block: Any, key: str) -> Any:
        value = getattr(block, key, None)
        if value is None and isinstance(block, dict):
            value = block.get(key)
        return value

    def _read_block_input(self, block: Any) -> Any:
        value = getattr(block, "input", None)
        if value is None and isinstance(block, dict):
            value = block.get("input")
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return value

    def _validate_tool_name(self, value: str) -> str:
        if _TOOL_NAME_PATTERN.match(value or ""):
            return value
        raise ValueError(
            f"Anthropic tool names must match {_TOOL_NAME_PATTERN.pattern}; got {value!r}."
        )
