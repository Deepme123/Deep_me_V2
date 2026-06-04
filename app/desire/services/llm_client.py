from __future__ import annotations

from app.core.llm import LLMProvider
from app.core.llm.providers import get_desire_provider


def get_llm_provider() -> LLMProvider:
    return get_desire_provider()
