import logging
import os
import sys
import threading
import time

import httpx

DISCORD_ERROR_WEBHOOK_URL = os.getenv("DISCORD_ERROR_WEBHOOK_URL", "")
_ERROR_NOTIFY_THROTTLE_SEC = 30


class DiscordErrorHandler(logging.Handler):
    """ERROR 이상 로그를 Discord 웹훅으로 전송.

    동일 로거+포맷 문자열은 _ERROR_NOTIFY_THROTTLE_SEC 동안 한 번만 보내서
    장애 폭주 시 같은 에러로 채널이 도배되는 것을 막음. 전송은 백그라운드
    스레드에서 처리해 요청 처리 흐름을 막지 않고, 전송 실패도 앱에 영향을
    주지 않도록 절대 예외를 올리지 않음.
    """

    def __init__(self, webhook_url: str, throttle_sec: int = _ERROR_NOTIFY_THROTTLE_SEC):
        super().__init__(level=logging.ERROR)
        self._webhook_url = webhook_url
        self._throttle_sec = throttle_sec
        self._last_sent: dict[str, float] = {}
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        # record.msg(치환 전 포맷 문자열)로 throttle 키를 잡아서 session_id 같은
        # 가변 값 때문에 매번 다른 키로 취급돼 throttle이 무력화되는 걸 방지.
        key = f"{record.name}:{record.levelname}:{record.msg}"
        now = time.monotonic()
        with self._lock:
            last = self._last_sent.get(key)
            if last is not None and now - last < self._throttle_sec:
                return
            self._last_sent[key] = now

        try:
            message = self.format(record)
        except Exception:
            return

        threading.Thread(target=self._post, args=(message,), daemon=True).start()

    def _post(self, message: str) -> None:
        try:
            with httpx.Client(timeout=10) as client:
                client.post(
                    self._webhook_url,
                    json={"content": f"```\n{message[:1900]}\n```"},
                )
        except Exception:
            pass


def setup_logging(level: int = logging.INFO) -> None:
    logger = logging.getLogger()
    if logger.handlers:
        return  # 중복 설정 방지
    logger.setLevel(level)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s - %(message)s"
    ))
    logger.addHandler(h)

    if DISCORD_ERROR_WEBHOOK_URL:
        discord_handler = DiscordErrorHandler(DISCORD_ERROR_WEBHOOK_URL)
        discord_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s - %(message)s"
        ))
        logger.addHandler(discord_handler)
