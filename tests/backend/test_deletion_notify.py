import importlib
import json
import sys
import threading
import types
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

deletion_notify = importlib.import_module("app.backend.services.deletion_notify")

WEBHOOK_URL = "http://example.invalid/deletion-webhook"


class _SyncThread:
    """threading.Thread 대역 — start()에서 target을 동기 실행해, 백그라운드 스레드
    완료를 기다리지 않고 검사할 때 생기는 레이스 컨디션을 제거한다."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self) -> None:
        self._target(*self._args, **self._kwargs)


class _FakeResponse:
    def __init__(self, status_code: int = 204):
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", WEBHOOK_URL)
            raise httpx.HTTPStatusError(
                "error", request=request, response=httpx.Response(self.status_code, request=request)
            )


class _FakeClient:
    """httpx.Client 대역 — 전송된 (url, json)을 sent에 기록한다."""

    sent: list = []
    status_code = 204
    error: Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def post(self, url, json=None, **kwargs):
        if _FakeClient.error is not None:
            raise _FakeClient.error
        _FakeClient.sent.append((url, json))
        return _FakeResponse(_FakeClient.status_code)


@pytest.fixture(autouse=True)
def _fake_transport(monkeypatch):
    _FakeClient.sent = []
    _FakeClient.status_code = 204
    _FakeClient.error = None
    monkeypatch.setattr(deletion_notify.httpx, "Client", _FakeClient)
    fake_threading = types.SimpleNamespace(Thread=_SyncThread, Lock=threading.Lock)
    monkeypatch.setattr(deletion_notify, "threading", fake_threading)
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)


def _payload_text(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


class TestNotifyDeletionRequested:
    def test_sends_user_id_reason_codes_and_scheduled_time(self, monkeypatch):
        monkeypatch.setenv("DISCORD_DELETION_WEBHOOK_URL", WEBHOOK_URL)
        user_id = uuid4()

        deletion_notify.notify_deletion_requested(
            user_id, [1, 3], datetime(2026, 10, 3, 12, 30)
        )

        assert len(_FakeClient.sent) == 1
        url, payload = _FakeClient.sent[0]
        assert url == WEBHOOK_URL
        text = _payload_text(payload)
        assert str(user_id) in text
        assert "1, 3" in text
        assert "2026-10-03 12:30 UTC" in text

    def test_env_label_defaults_to_local(self, monkeypatch):
        monkeypatch.setenv("DISCORD_DELETION_WEBHOOK_URL", WEBHOOK_URL)

        deletion_notify.notify_deletion_requested(uuid4(), [1], datetime(2026, 10, 3))

        assert "[local]" in _payload_text(_FakeClient.sent[0][1])

    def test_env_label_uses_render_service_name(self, monkeypatch):
        monkeypatch.setenv("DISCORD_DELETION_WEBHOOK_URL", WEBHOOK_URL)
        monkeypatch.setenv("RENDER_SERVICE_NAME", "deep-me-v2-test")

        deletion_notify.notify_deletion_requested(uuid4(), [1], datetime(2026, 10, 3))

        assert "[deep-me-v2-test]" in _payload_text(_FakeClient.sent[0][1])

    def test_skips_when_webhook_url_unset(self, monkeypatch):
        monkeypatch.delenv("DISCORD_DELETION_WEBHOOK_URL", raising=False)

        deletion_notify.notify_deletion_requested(uuid4(), [1], datetime(2026, 10, 3))

        assert _FakeClient.sent == []

    def test_swallows_network_errors(self, monkeypatch):
        monkeypatch.setenv("DISCORD_DELETION_WEBHOOK_URL", WEBHOOK_URL)
        _FakeClient.error = RuntimeError("network down")

        # 예외가 올라오면 테스트 실패
        deletion_notify.notify_deletion_requested(uuid4(), [1], datetime(2026, 10, 3))

    def test_swallows_http_status_errors(self, monkeypatch):
        monkeypatch.setenv("DISCORD_DELETION_WEBHOOK_URL", WEBHOOK_URL)
        _FakeClient.status_code = 404

        deletion_notify.notify_deletion_requested(uuid4(), [1], datetime(2026, 10, 3))

        assert len(_FakeClient.sent) == 1

    def test_swallows_payload_build_errors(self, monkeypatch):
        monkeypatch.setenv("DISCORD_DELETION_WEBHOOK_URL", WEBHOOK_URL)

        # reason_codes가 이터러블이 아니어도 탈퇴 로직으로 예외가 새면 안 된다.
        deletion_notify.notify_deletion_requested(uuid4(), None, datetime(2026, 10, 3))

        assert _FakeClient.sent == []


class TestNotifyDeletionCompleted:
    def test_sends_user_id_and_timestamps(self, monkeypatch):
        monkeypatch.setenv("DISCORD_DELETION_WEBHOOK_URL", WEBHOOK_URL)
        user_id = uuid4()

        deletion_notify.notify_deletion_completed(
            user_id, datetime(2026, 9, 28, 9, 0), datetime(2026, 10, 3, 9, 5)
        )

        assert len(_FakeClient.sent) == 1
        url, payload = _FakeClient.sent[0]
        assert url == WEBHOOK_URL
        text = _payload_text(payload)
        assert str(user_id) in text
        assert "2026-09-28 09:00 UTC" in text
        assert "2026-10-03 09:05 UTC" in text

    def test_handles_missing_requested_at(self, monkeypatch):
        monkeypatch.setenv("DISCORD_DELETION_WEBHOOK_URL", WEBHOOK_URL)

        deletion_notify.notify_deletion_completed(uuid4(), None, datetime(2026, 10, 3, 9, 5))

        assert len(_FakeClient.sent) == 1

    def test_skips_when_webhook_url_unset(self, monkeypatch):
        monkeypatch.delenv("DISCORD_DELETION_WEBHOOK_URL", raising=False)

        deletion_notify.notify_deletion_completed(uuid4(), None, datetime(2026, 10, 3))

        assert _FakeClient.sent == []

    def test_swallows_network_errors(self, monkeypatch):
        monkeypatch.setenv("DISCORD_DELETION_WEBHOOK_URL", WEBHOOK_URL)
        _FakeClient.error = RuntimeError("network down")

        deletion_notify.notify_deletion_completed(uuid4(), None, datetime(2026, 10, 3))
