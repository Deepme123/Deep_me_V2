from __future__ import annotations

import os

END_SESSION_TOKEN = "__END_SESSION__"
CANCEL_CLOSE_MESSAGE_TYPE = "cancel_close"
CANCEL_CLOSE_OK_MESSAGE_TYPE = "cancel_close_ok"
CANCEL_CLOSE_STEP_TYPE = os.getenv("CANCEL_CLOSE_STEP_TYPE", "cancel_close")


def extract_end_session_marker(text: str) -> tuple[str, bool]:
    if not text:
        return "", False
    if END_SESSION_TOKEN not in text:
        return text, False
    cleaned = text.replace(END_SESSION_TOKEN, "").strip()
    return cleaned, True


def build_cancel_close_ok_message() -> dict[str, str]:
    return {"type": CANCEL_CLOSE_OK_MESSAGE_TYPE}
