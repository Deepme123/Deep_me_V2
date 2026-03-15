from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator, Sequence

from .base import LLMProvider
from .types import JSONValue, LLMJsonSchema, LLMMessage, LLMRequestOptions

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.core.llm_settings import LLMSettings

try:
    from openai import BadRequestError, OpenAI  # type: ignore
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

    class BadRequestError(Exception):
        pass


@dataclass(frozen=True)
class _ResolvedOptions:
    model: str
    temperature: float
    max_tokens: int
    timeout_sec: float


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        *,
        settings: LLMSettings,
        client: Any | None = None,
        backup_models: Sequence[str] = (),
    ) -> None:
        self._settings = settings
        self._client = client
        self._backup_models = self._resolve_backup_models(backup_models)

    def generate_text(
        self,
        *,
        messages: Sequence[LLMMessage],
        options: LLMRequestOptions | None = None,
    ) -> str:
        return "".join(self.stream_text(messages=messages, options=options))

    def stream_text(
        self,
        *,
        messages: Sequence[LLMMessage],
        options: LLMRequestOptions | None = None,
    ) -> Iterator[str]:
        resolved = self._resolve_options(options)
        client = self._get_client(timeout_sec=resolved.timeout_sec)

        if self._is_reasoning_model(resolved.model):
            try:
                yield from self._stream_with_responses(
                    client=client,
                    model=resolved.model,
                    messages=messages,
                    options=resolved,
                )
                return
            except Exception as exc:
                logger.warning(
                    "OpenAI responses stream failed for %s; falling back to chat: %s",
                    resolved.model,
                    exc,
                )

        last_error: Exception | None = None
        for model in self._chat_fallback_models(resolved.model):
            try:
                yield from self._stream_with_chat(
                    client=client,
                    model=model,
                    messages=messages,
                    options=resolved,
                )
                return
            except Exception as exc:
                last_error = exc
                logger.warning("OpenAI chat stream failed for %s: %s", model, exc)

        raise RuntimeError(
            f"OpenAI text streaming failed for model={resolved.model}; last={last_error}"
        )

    def generate_json(
        self,
        *,
        messages: Sequence[LLMMessage],
        schema: LLMJsonSchema,
        options: LLMRequestOptions | None = None,
    ) -> JSONValue:
        resolved = self._resolve_options(options)
        client = self._get_client(timeout_sec=resolved.timeout_sec)
        response_format = schema.to_openai_response_format()

        try:
            params: dict[str, Any] = {
                "model": resolved.model,
                "input": self._to_responses_input(messages),
                "response_format": response_format,
            }
            if resolved.max_tokens > 0:
                params["max_output_tokens"] = resolved.max_tokens
            if not self._is_reasoning_model(resolved.model):
                params["temperature"] = resolved.temperature

            response = client.responses.create(**params)
            return self._parse_json_response(response)
        except Exception as exc:
            logger.warning(
                "OpenAI responses JSON request failed for %s; falling back to chat: %s",
                resolved.model,
                exc,
            )

        last_error: Exception | None = None
        for model in self._chat_fallback_models(resolved.model):
            try:
                response = self._create_chat_completion(
                    client=client,
                    model=model,
                    messages=messages,
                    options=resolved,
                    stream=False,
                    response_format=response_format,
                )
                return self._parse_json_response(response)
            except Exception as exc:
                last_error = exc
                logger.warning("OpenAI chat JSON request failed for %s: %s", model, exc)

        raise RuntimeError(
            f"OpenAI JSON generation failed for model={resolved.model}; last={last_error}"
        )

    def _resolve_backup_models(self, backup_models: Sequence[str]) -> tuple[str, ...]:
        cleaned = tuple(model.strip() for model in backup_models if model.strip())
        if cleaned:
            return cleaned

        raw = os.getenv("LLM_BACKUP_MODELS") or "gpt-4o-mini,gpt-4o"
        return tuple(model.strip() for model in raw.split(",") if model.strip())

    def _resolve_options(self, options: LLMRequestOptions | None) -> _ResolvedOptions:
        if options is None:
            return _ResolvedOptions(
                model=self._settings.model,
                temperature=self._settings.temperature,
                max_tokens=self._settings.max_tokens,
                timeout_sec=self._settings.timeout_sec,
            )

        return _ResolvedOptions(
            model=(options.model or self._settings.model).strip() or self._settings.model,
            temperature=(
                self._settings.temperature
                if options.temperature is None
                else float(options.temperature)
            ),
            max_tokens=(
                self._settings.max_tokens if options.max_tokens is None else int(options.max_tokens)
            ),
            timeout_sec=(
                self._settings.timeout_sec
                if options.timeout_sec is None
                else float(options.timeout_sec)
            ),
        )

    def _get_client(self, *, timeout_sec: float) -> Any:
        if self._client is not None:
            return self._client
        if OpenAI is None:
            raise RuntimeError("openai package is not installed. Check requirements.txt.")
        from app.core.llm_settings import build_openai_client_kwargs

        return OpenAI(
            **build_openai_client_kwargs(
                api_key=self._settings.openai_api_key or None,
                timeout=timeout_sec,
            )
        )

    def _chat_fallback_models(self, primary_model: str) -> tuple[str, ...]:
        ordered: list[str] = []
        if not self._is_reasoning_model(primary_model):
            ordered.append(primary_model)
        ordered.extend(self._backup_models)

        deduped: list[str] = []
        for model in ordered:
            cleaned = model.strip()
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)
        return tuple(deduped)

    def _stream_with_responses(
        self,
        *,
        client: Any,
        model: str,
        messages: Sequence[LLMMessage],
        options: _ResolvedOptions,
    ) -> Iterator[str]:
        params: dict[str, Any] = {
            "model": model,
            "input": self._to_responses_input(messages),
        }
        if options.max_tokens > 0:
            params["max_output_tokens"] = options.max_tokens
        if not self._is_reasoning_model(model):
            params["temperature"] = options.temperature

        with client.responses.stream(**params) as stream:
            emitted = False
            for event in stream:
                event_type = getattr(event, "type", None)
                if event_type == "response.output_text.delta":
                    piece = getattr(event, "delta", None)
                    if piece:
                        emitted = True
                        yield piece
                elif event_type == "response.error":
                    error = getattr(event, "error", None)
                    raise RuntimeError(str(error) if error else "responses stream error")

            if emitted:
                return

            final_response = stream.get_final_response()
            try:
                final_text = self._extract_response_text(final_response)
            except ValueError:
                final_text = ""
            if final_text:
                yield final_text

    def _stream_with_chat(
        self,
        *,
        client: Any,
        model: str,
        messages: Sequence[LLMMessage],
        options: _ResolvedOptions,
    ) -> Iterator[str]:
        stream = self._create_chat_completion(
            client=client,
            model=model,
            messages=messages,
            options=options,
            stream=True,
        )
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except Exception:
                delta = None
            text = self._coerce_text(delta)
            if text:
                yield text

    def _create_chat_completion(
        self,
        *,
        client: Any,
        model: str,
        messages: Sequence[LLMMessage],
        options: _ResolvedOptions,
        stream: bool,
        response_format: dict[str, Any] | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_chat_messages(messages),
            "stream": stream,
        }
        if options.max_tokens > 0:
            kwargs["max_completion_tokens"] = options.max_tokens
        if response_format is not None:
            kwargs["response_format"] = response_format
        if not self._is_reasoning_model(model):
            kwargs["temperature"] = options.temperature

        try:
            return client.chat.completions.create(**kwargs)
        except BadRequestError as exc:
            if "max_completion_tokens" not in str(exc):
                raise
            kwargs.pop("max_completion_tokens", None)
            if options.max_tokens > 0:
                kwargs["max_tokens"] = options.max_tokens
            return client.chat.completions.create(**kwargs)

    def _parse_json_response(self, response: Any) -> JSONValue:
        raw_text = self._extract_response_text(response).strip()
        if not raw_text:
            raise RuntimeError("LLM returned an empty JSON response.")
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM response was not valid JSON.") from exc

    def _extract_response_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        text = self._coerce_text(output_text)
        if text:
            return text

        choices = getattr(response, "choices", None)
        if choices:
            choice = choices[0]
            message = getattr(choice, "message", None)
            text = self._coerce_text(getattr(message, "content", None))
            if text:
                return text

        output = getattr(response, "output", None)
        if output:
            fragments: list[str] = []
            for block in output:
                content_items = getattr(block, "content", None)
                if content_items is None and isinstance(block, dict):
                    content_items = block.get("content")
                for item in content_items or []:
                    text = getattr(item, "text", None)
                    if text is None and isinstance(item, dict):
                        text = item.get("text")
                    fragment = self._coerce_text(text)
                    if fragment:
                        fragments.append(fragment)
            if fragments:
                return "".join(fragments)

        raise ValueError("Unable to read content from OpenAI response.")

    def _to_responses_input(self, messages: Sequence[LLMMessage]) -> list[dict[str, Any]]:
        return [
            {
                "role": message.role,
                "content": [{"type": "input_text", "text": message.content}],
            }
            for message in messages
        ]

    def _to_chat_messages(self, messages: Sequence[LLMMessage]) -> list[dict[str, str]]:
        return [{"role": message.role, "content": message.content} for message in messages]

    def _coerce_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            fragments = [self._coerce_text(item) for item in value]
            return "".join(fragment for fragment in fragments if fragment)
        if isinstance(value, dict):
            text = value.get("text")
            if text is not None:
                return self._coerce_text(text)
            value_text = value.get("value")
            if value_text is not None:
                return self._coerce_text(value_text)
            return ""

        text_attr = getattr(value, "text", None)
        if text_attr is not None:
            return self._coerce_text(text_attr)
        value_attr = getattr(value, "value", None)
        if value_attr is not None:
            return self._coerce_text(value_attr)
        return ""

    def _is_reasoning_model(self, model: str) -> bool:
        normalized = (model or "").lower()
        return normalized.startswith("gpt-5") or normalized.startswith("o4") or normalized.startswith("o3")
