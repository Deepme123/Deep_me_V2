from __future__ import annotations

import os

RESERVED_CONFIRM_CLOSE_TOKEN = "[[CONFIRM_CLOSE]]"
END_SESSION_TOKEN = "__END_SESSION__"
CANCEL_CLOSE_MESSAGE_TYPE = "cancel_close"
CANCEL_CLOSE_OK_MESSAGE_TYPE = "cancel_close_ok"
CANCEL_CLOSE_STEP_TYPE = os.getenv("CANCEL_CLOSE_STEP_TYPE", "cancel_close")


def extract_end_session_marker(text: str) -> tuple[str, bool]:
    if not text:
        return "", False
    if RESERVED_CONFIRM_CLOSE_TOKEN not in text:
        return text, False
    cleaned = text.replace(RESERVED_CONFIRM_CLOSE_TOKEN, "").strip()
    return cleaned, True


def build_cancel_close_ok_message() -> dict[str, str]:
    return {"type": CANCEL_CLOSE_OK_MESSAGE_TYPE}


class StreamingConfirmCloseFilter:
    """LLM 스트리밍 청크에서 [[CONFIRM_CLOSE]] 토큰을 검출/제거하는 필터.

    각 청크가 도착할 때마다 feed()로 안전하게 방출 가능한 텍스트만 돌려준다.
    토큰이 검출되면 그 이후 모든 입력은 무시되고 end_detected가 True가 된다.

    토큰이 청크 경계에 걸쳐 분할되어 도착해도(`abc[[CONF` + `IRM_CLOSE]] end`)
    토큰 접두사가 될 수 있는 꼬리를 내부 버퍼에 보류하므로 절대 부분 토큰이
    클라이언트에 노출되지 않는다.
    """

    TOKEN = RESERVED_CONFIRM_CLOSE_TOKEN

    def __init__(self) -> None:
        self._pending: str = ""
        self._end_detected: bool = False

    @property
    def end_detected(self) -> bool:
        return self._end_detected

    def feed(self, piece: str) -> str:
        if self._end_detected:
            return ""
        if not piece:
            return ""
        self._pending += piece

        idx = self._pending.find(self.TOKEN)
        if idx >= 0:
            emit = self._pending[:idx].rstrip()
            self._pending = ""
            self._end_detected = True
            return emit

        keep = self._holdback_length(self._pending)
        if keep == 0:
            emit = self._pending
            self._pending = ""
            return emit
        if keep >= len(self._pending):
            return ""
        emit = self._pending[:-keep]
        self._pending = self._pending[-keep:]
        return emit

    def flush(self) -> str:
        if self._end_detected:
            self._pending = ""
            return ""
        idx = self._pending.find(self.TOKEN)
        if idx >= 0:
            emit = self._pending[:idx].rstrip()
            self._pending = ""
            self._end_detected = True
            return emit
        emit = self._pending
        self._pending = ""
        return emit

    @classmethod
    def _holdback_length(cls, text: str) -> int:
        """Hold back any token-prefix suffix plus the trailing whitespace
        immediately preceding it, so that when the token completes we can
        cleanly rstrip the leading content (matching the legacy strip()
        behavior of extract_end_session_marker).
        """
        prefix_len = cls._longest_token_prefix_suffix(text)
        i = len(text) - prefix_len
        while i > 0 and text[i - 1].isspace():
            i -= 1
        return len(text) - i

    @classmethod
    def _longest_token_prefix_suffix(cls, text: str) -> int:
        max_keep = min(len(text), len(cls.TOKEN) - 1)
        for k in range(max_keep, 0, -1):
            if text.endswith(cls.TOKEN[:k]):
                return k
        return 0
