from __future__ import annotations

import asyncio
import hashlib
import hmac

import pytest

from app.backend.routers import deploy_webhook as dw


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestSignatureRequiredAndValid:
    def test_missing_signature_header_is_rejected_when_secret_configured(self, monkeypatch):
        monkeypatch.setattr(dw, "GITHUB_WEBHOOK_SECRET", "my-secret")
        assert dw._signature_required_and_valid(b"{}", "") is False

    def test_wrong_signature_is_rejected(self, monkeypatch):
        monkeypatch.setattr(dw, "GITHUB_WEBHOOK_SECRET", "my-secret")
        assert dw._signature_required_and_valid(b"{}", "sha256=deadbeef") is False

    def test_correct_signature_is_accepted(self, monkeypatch):
        monkeypatch.setattr(dw, "GITHUB_WEBHOOK_SECRET", "my-secret")
        body = b'{"ref": "refs/heads/main"}'
        assert dw._signature_required_and_valid(body, _sign(body, "my-secret")) is True

    def test_no_secret_configured_skips_verification(self, monkeypatch):
        monkeypatch.setattr(dw, "GITHUB_WEBHOOK_SECRET", "")
        assert dw._signature_required_and_valid(b"{}", "") is True


class TestIsGithubApiUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://api.github.com/repos/org/repo/pulls/1/commits",
            "https://api.github.com/repositories/123/commits?page=2",
        ],
    )
    def test_accepts_github_api_host(self, url):
        assert dw._is_github_api_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://attacker.example/internal",
            "http://api.github.com/repos/org/repo/pulls/1/commits",
            "https://api.github.com.attacker.example/x",
            "",
        ],
    )
    def test_rejects_non_github_api_host(self, url):
        assert dw._is_github_api_url(url) is False


class TestFetchPrCommitsRejectsForeignHost:
    def test_raises_before_any_network_call(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError("httpx should not be called for a disallowed host")

        monkeypatch.setattr(dw.httpx, "AsyncClient", _boom)

        with pytest.raises(ValueError):
            asyncio.run(dw._fetch_pr_commits("https://attacker.example/steal"))
