from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Sequence

from .types import JSONValue, LLMJsonSchema, LLMMessage, LLMRequestOptions


class LLMProvider(ABC):
    @abstractmethod
    def generate_text(
        self,
        *,
        messages: Sequence[LLMMessage],
        options: LLMRequestOptions | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def stream_text(
        self,
        *,
        messages: Sequence[LLMMessage],
        options: LLMRequestOptions | None = None,
    ) -> Iterator[str]:
        raise NotImplementedError

    @abstractmethod
    def generate_json(
        self,
        *,
        messages: Sequence[LLMMessage],
        schema: LLMJsonSchema,
        options: LLMRequestOptions | None = None,
    ) -> JSONValue:
        raise NotImplementedError
