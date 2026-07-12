import importlib
import logging
import sys
import threading
import time
import types
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logging_config = importlib.import_module("app.backend.core.logging_config")


class _SyncThread:
    """threading.Thread 대역 — emit()이 백그라운드 스레드로 _post를 실행하므로,
    스레드 완료를 기다리지 않고 sent 리스트를 검사하면 실행 환경(CPU 부하 등)에 따라
    레이스 컨디션으로 flaky해진다. start()에서 target을 동기 실행해 이를 제거한다."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self) -> None:
        self._target(*self._args, **self._kwargs)


def _use_sync_thread(monkeypatch) -> None:
    fake_threading = types.SimpleNamespace(Thread=_SyncThread, Lock=threading.Lock)
    monkeypatch.setattr(logging_config, "threading", fake_threading)


def _record(msg: str, args: tuple = (), name: str = "test.logger") -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


def test_emit_sends_once_per_throttle_window(monkeypatch):
    _use_sync_thread(monkeypatch)
    sent = []
    handler = logging_config.DiscordErrorHandler("http://example.invalid/webhook", throttle_sec=60)
    monkeypatch.setattr(handler, "_post", lambda message: sent.append(message))

    handler.emit(_record("failed | session_id=%s", ("aaa",)))
    handler.emit(_record("failed | session_id=%s", ("bbb",)))

    assert len(sent) == 1


def test_emit_sends_first_message_even_when_monotonic_clock_is_near_zero(monkeypatch):
    # 컨테이너가 막 시작된 직후에는 time.monotonic()이 throttle_sec보다 작은 값을
    # 반환할 수 있다. 이때 "처음 보는 키"가 0.0 sentinel과 혼동되어 첫 메시지부터
    # 조용히 씹히면 안 된다.
    _use_sync_thread(monkeypatch)
    monkeypatch.setattr(logging_config.time, "monotonic", lambda: 2.0)
    sent = []
    handler = logging_config.DiscordErrorHandler("http://example.invalid/webhook", throttle_sec=60)
    monkeypatch.setattr(handler, "_post", lambda message: sent.append(message))

    handler.emit(_record("failed"))

    assert len(sent) == 1


def test_emit_allows_again_after_throttle_window(monkeypatch):
    _use_sync_thread(monkeypatch)
    sent = []
    handler = logging_config.DiscordErrorHandler("http://example.invalid/webhook", throttle_sec=0)
    monkeypatch.setattr(handler, "_post", lambda message: sent.append(message))

    handler.emit(_record("failed"))
    time.sleep(0.01)
    handler.emit(_record("failed"))

    assert len(sent) == 2


def test_post_swallows_network_errors(monkeypatch):
    class _BoomClient:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def post(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(logging_config.httpx, "Client", lambda *a, **k: _BoomClient())
    handler = logging_config.DiscordErrorHandler("http://example.invalid/webhook")

    handler._post("boom")  # 예외가 올라오면 테스트 실패
