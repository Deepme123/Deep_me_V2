from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, TypeAlias

LLMRole: TypeAlias = Literal["system", "user", "assistant"]
JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]

_ALLOWED_ROLES = frozenset({"system", "user", "assistant"})


@dataclass(frozen=True)
class LLMMessage:
    role: LLMRole
    content: str

    def __post_init__(self) -> None:
        if self.role not in _ALLOWED_ROLES:
            raise ValueError(f"Unsupported LLM message role: {self.role}")


@dataclass(frozen=True)
class LLMRequestOptions:
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_sec: float | None = None


@dataclass(frozen=True)
class LLMJsonSchema:
    name: str
    schema: Mapping[str, Any]
    strict: bool = True

    def to_openai_response_format(self) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": self.name,
                "schema": dict(self.schema),
                "strict": self.strict,
            },
        }
