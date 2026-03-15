from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.llm import AnthropicProvider, OpenAIProvider
from app.core.llm import factory


def _build_settings(provider: str = "openai"):
    return SimpleNamespace(
        provider=provider,
        model="gpt-test",
        temperature=0.2,
        max_tokens=123,
        timeout_sec=9.0,
        openai_api_key="test-key",
        anthropic_api_key="anthropic-key",
    )


def test_create_llm_provider_from_settings_selects_openai_provider():
    provider = factory.create_llm_provider_from_settings(_build_settings())

    assert isinstance(provider, OpenAIProvider)


def test_create_llm_provider_from_settings_selects_anthropic_provider():
    provider = factory.create_llm_provider_from_settings(_build_settings(provider="anthropic"))

    assert isinstance(provider, AnthropicProvider)


def test_create_llm_provider_from_settings_rejects_unsupported_provider():
    with pytest.raises(ValueError, match="Unsupported LLM provider: bedrock"):
        factory.create_llm_provider_from_settings(_build_settings(provider="bedrock"))


def test_create_llm_provider_resolves_settings_before_selecting(monkeypatch):
    captured = {}
    settings = _build_settings()

    def _fake_get_llm_settings(**kwargs):
        captured["kwargs"] = kwargs
        return settings

    def _fake_create_llm_provider_from_settings(resolved_settings):
        captured["settings"] = resolved_settings
        return "provider-instance"

    monkeypatch.setattr(factory, "get_llm_settings", _fake_get_llm_settings)
    monkeypatch.setattr(
        factory,
        "create_llm_provider_from_settings",
        _fake_create_llm_provider_from_settings,
    )

    result = factory.create_llm_provider(
        model_default="gpt-default",
        model_legacy_names=("LEGACY_MODEL",),
        temperature_default=0.6,
        max_tokens_default=456,
        timeout_default=33.0,
    )

    assert result == "provider-instance"
    assert captured["settings"] is settings
    assert captured["kwargs"] == {
        "model_default": "gpt-default",
        "model_legacy_names": ("LEGACY_MODEL",),
        "temperature_default": 0.6,
        "max_tokens_default": 456,
        "timeout_default": 33.0,
    }
