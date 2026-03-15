from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = APP_DIR.parent

load_dotenv(ROOT_DIR / ".env")
load_dotenv(APP_DIR / ".env")


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    temperature: float
    max_tokens: int
    timeout_sec: float
    openai_api_key: str
    anthropic_api_key: str


def _read_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _read_first(names: Sequence[str], default: str) -> str:
    for name in names:
        value = _read_env(name)
        if value is not None:
            return value
    return default


def _read_float(names: Sequence[str], default: float) -> float:
    value = _read_first(names, "")
    if value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _read_int(names: Sequence[str], default: int) -> int:
    value = _read_first(names, "")
    if value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _normalize_provider(value: str) -> str:
    provider = (value or "openai").strip().lower()
    return provider or "openai"


def get_llm_settings(
    *,
    model_default: str,
    model_legacy_names: Sequence[str] = (),
    temperature_default: float = 0.7,
    max_tokens_default: int = 800,
    timeout_default: float = 60.0,
) -> LLMSettings:
    model_names = ("LLM_MODEL", *model_legacy_names)
    return LLMSettings(
        provider=_normalize_provider(_read_first(("LLM_PROVIDER",), "openai")),
        model=_read_first(model_names, model_default),
        temperature=_read_float(("LLM_TEMPERATURE",), temperature_default),
        max_tokens=_read_int(("LLM_MAX_TOKENS",), max_tokens_default),
        timeout_sec=_read_float(("LLM_TIMEOUT_SEC",), timeout_default),
        openai_api_key=_read_first(("OPENAI_API_KEY",), ""),
        anthropic_api_key=_read_first(("ANTHROPIC_API_KEY",), ""),
    )


def build_openai_client_kwargs(
    *,
    api_key: str | None = None,
    timeout: float | None = None,
) -> dict[str, object]:
    client_kwargs: dict[str, object] = {}

    resolved_api_key = api_key if api_key is not None else _read_first(("OPENAI_API_KEY",), "")
    if resolved_api_key:
        client_kwargs["api_key"] = resolved_api_key

    base_url = _read_first(("OPENAI_BASE_URL",), "")
    if base_url:
        client_kwargs["base_url"] = base_url

    organization = _read_first(("OPENAI_ORG_ID",), "")
    if organization:
        client_kwargs["organization"] = organization

    project = _read_first(("OPENAI_PROJECT",), "")
    if project:
        client_kwargs["project"] = project

    if timeout is not None:
        client_kwargs["timeout"] = timeout

    return client_kwargs
