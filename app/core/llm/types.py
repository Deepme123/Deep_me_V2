from __future__ import annotations

from copy import deepcopy
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

    def to_openai_strict_schema(self) -> dict[str, Any]:
        return _normalize_openai_schema(deepcopy(dict(self.schema)))

    def to_openai_response_format(self) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": self.name,
                "schema": self.to_openai_strict_schema(),
                "strict": self.strict,
            },
        }


def _normalize_openai_schema(node: Any, *, force_nullable: bool = False) -> Any:
    if isinstance(node, list):
        return [_normalize_openai_schema(item) for item in node]

    if not isinstance(node, dict):
        return node

    normalized = {key: _normalize_openai_schema(value) for key, value in node.items()}
    properties = normalized.get("properties")
    if isinstance(properties, dict):
        original_required = {
            key for key in node.get("required", []) if isinstance(key, str)
        }
        normalized_properties: dict[str, Any] = {}
        for key, value in properties.items():
            normalized_properties[key] = _normalize_openai_schema(
                value,
                force_nullable=key not in original_required,
            )
        normalized["properties"] = normalized_properties
        normalized["required"] = list(normalized_properties.keys())

    if force_nullable:
        normalized = _allow_null_in_schema(normalized)

    return normalized


def _allow_null_in_schema(schema: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(schema)
    schema_type = normalized.get("type")

    if isinstance(schema_type, str):
        if schema_type != "null":
            normalized["type"] = [schema_type, "null"]
        return normalized

    if isinstance(schema_type, list):
        if "null" not in schema_type:
            normalized["type"] = [*schema_type, "null"]
        return normalized

    enum_values = normalized.get("enum")
    if isinstance(enum_values, list) and None not in enum_values:
        normalized["enum"] = [*enum_values, None]

    return normalized
