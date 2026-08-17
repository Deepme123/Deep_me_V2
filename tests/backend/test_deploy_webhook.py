from __future__ import annotations

import asyncio
import hashlib
import hmac

import httpx
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


class TestSafeJson:
    """Render가 2xx 응답인데도 body가 JSON이 아닌 경우(공백/평문 등)를 대비한
    _safe_json이 예외 없이 {}를 반환하는지 확인 — 배포 트리거 자체는 성공했는데
    파싱 실패로 실패 처리되던 버그의 회귀 테스트."""

    def test_returns_empty_dict_for_empty_content(self):
        resp = httpx.Response(status_code=200, content=b"")
        assert dw._safe_json(resp) == {}

    def test_parses_valid_json(self):
        resp = httpx.Response(status_code=200, content=b'{"deploy": {"id": "dep-123"}}')
        assert dw._safe_json(resp) == {"deploy": {"id": "dep-123"}}

    def test_returns_empty_dict_instead_of_raising_for_non_json_content(self):
        resp = httpx.Response(status_code=200, content=b"\n")
        assert dw._safe_json(resp) == {}


class TestFetchPrCommitsRejectsForeignHost:
    def test_raises_before_any_network_call(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError("httpx should not be called for a disallowed host")

        monkeypatch.setattr(dw.httpx, "AsyncClient", _boom)

        with pytest.raises(ValueError):
            asyncio.run(dw._fetch_pr_commits("https://attacker.example/steal"))
