from __future__ import annotations

from app.core.llm_settings import get_llm_settings


def test_max_tokens_falls_back_to_shared_llm_max_tokens_when_no_override(monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS", "1024")
    monkeypatch.delenv("CARD_MAX_TOKENS", raising=False)

    settings = get_llm_settings(
        model_default="gpt-test",
        max_tokens_default=4000,
        max_tokens_override_names=("CARD_MAX_TOKENS",),
    )

    assert settings.max_tokens == 1024


def test_max_tokens_override_name_takes_priority_over_shared_llm_max_tokens(monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS", "1024")
    monkeypatch.setenv("CARD_MAX_TOKENS", "4000")

    settings = get_llm_settings(
        model_default="gpt-test",
        max_tokens_default=800,
        max_tokens_override_names=("CARD_MAX_TOKENS",),
    )

    assert settings.max_tokens == 4000


def test_max_tokens_uses_default_when_nothing_set(monkeypatch):
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    monkeypatch.delenv("CARD_MAX_TOKENS", raising=False)

    settings = get_llm_settings(
        model_default="gpt-test",
        max_tokens_default=4000,
        max_tokens_override_names=("CARD_MAX_TOKENS",),
    )

    assert settings.max_tokens == 4000
