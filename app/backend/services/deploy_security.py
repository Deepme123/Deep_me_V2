"""GitHub 웹훅 서명 검증 및 SSRF 방지용 호스트 검증."""

import hashlib
import hmac
import os
from urllib.parse import urlparse

GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")
GITHUB_API_HOST = "api.github.com"


def _verify_signature(payload_bytes: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _signature_required_and_valid(raw_body: bytes, signature: str) -> bool:
    """GITHUB_WEBHOOK_SECRET이 설정된 경우, 서명이 없거나 틀리면 거부.

    이전엔 `signature` 헤더 자체가 없으면 검증을 통째로 스킵해서
    헤더를 안 보내는 것만으로 인증을 우회할 수 있었음.
    """
    if not GITHUB_WEBHOOK_SECRET:
        return True
    if not signature:
        return False
    return _verify_signature(raw_body, signature, GITHUB_WEBHOOK_SECRET)


def _is_github_api_url(url: str) -> bool:
    """commits_url은 PR 웹훅 페이로드에서 그대로 들어오는 값이라,
    GitHub API 호스트가 아니면 거부해서 SSRF를 막음."""
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == GITHUB_API_HOST
