import importlib
import logging
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logging_config = importlib.import_module("app.backend.core.logging_config")


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
    sent = []
    handler = logging_config.DiscordErrorHandler("http://example.invalid/webhook", throttle_sec=60)
    monkeypatch.setattr(handler, "_post", lambda message: sent.append(message))

    handler.emit(_record("failed | session_id=%s", ("aaa",)))
    handler.emit(_record("failed | session_id=%s", ("bbb",)))

    assert len(sent) == 1


def test_emit_allows_again_after_throttle_window(monkeypatch):
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
