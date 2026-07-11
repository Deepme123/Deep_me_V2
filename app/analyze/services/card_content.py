from __future__ import annotations

from typing import Any, Mapping

CONTENT_FIELDS = (
    "summary",
    "core_emotions",
    "situation",
    "situation_steps",
    "physical_reactions",
    "behavior_patterns",
    "coping_actions",
    "tags",
    "insight",
    "thoughts",
)


def has_meaningful_content(values: Mapping[str, Any]) -> bool:
    for key in CONTENT_FIELDS:
        value = values.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and value:
            return True
    return False
