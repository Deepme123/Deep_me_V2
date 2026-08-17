from __future__ import annotations

from app.core.llm import LLMJsonSchema

CARD_SCHEMA = LLMJsonSchema(
    name="analysis_card",
    schema={
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "core_emotions",
            "situation",
            "situation_steps",
            "physical_reactions",
            "behavior_patterns",
            "tags",
            "insight",
            "thoughts",
        ],
        "properties": {
            "summary": {"type": "string", "maxLength": 20},
            "core_emotions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "primary": {"type": "string"},
                        "sub": {"type": "array", "items": {"type": "string"}},
                        "quote": {"type": "string"},
                        "reasoning": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 3,
                        },
                    },
                    "required": ["primary", "sub", "quote", "reasoning"],
                },
            },
            "situation": {"type": "string"},
            "situation_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "interpretations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 3,
                            "maxItems": 3,
                        },
                    },
                    "required": ["title", "description", "interpretations"],
                },
                "minItems": 1,
                "maxItems": 2,
            },
            "physical_reactions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "primary": {"type": "string"},
                    },
                    "required": ["title", "description", "primary"],
                },
                "minItems": 1,
                "maxItems": 4,
            },
            "behavior_patterns": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "primary": {"type": "string"},
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 3,
                        },
                    },
                    "required": ["title", "primary", "items"],
                },
            },
            "coping_actions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "insight": {"type": "string"},
            "thoughts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "primary": {"type": "string"},
                        "quote": {"type": "string"},
                        "thoughts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 3,
                        },
                    },
                    "required": ["primary", "quote", "thoughts"],
                },
                "minItems": 1,
                "maxItems": 3,
            },
        },
    },
)
