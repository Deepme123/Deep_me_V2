from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.backend.services.llm_service import generate_noa_response, stream_noa_response
from app.backend.services.stream_bridge import iter_chunks_async

router = APIRouter(prefix="/health", tags=["health"])

DEFAULT_PONG_PROMPT = "\ub108\ub294 \uac04\ub2e8\ud788 \ud55c \ub2e8\uc5b4\ub85c\ub9cc \ub300\ub2f5\ud574: pong"
HEALTHCHECK_QUERY_DESCRIPTION = (
    "\ud14c\uc2a4\ud2b8\uc6a9 \ud504\ub86c\ud504\ud2b8(\uc5c6\uc73c\uba74 \uae30\ubcf8 pong \uac80\uc0ac)"
)


@router.get("/llm")
def health_llm(
    q: Optional[str] = Query(None, description=HEALTHCHECK_QUERY_DESCRIPTION),
):
    text = generate_noa_response(
        system_prompt="(healthcheck)",
        task_prompt=None,
        conversation=[("user", q or DEFAULT_PONG_PROMPT)],
    )
    text = (text or "").strip()

    if not text:
        raise HTTPException(status_code=503, detail="llm_empty_response")

    if q is None and "pong" not in text.lower():
        return {"ok": False, "detail": "unexpected_content", "text": text}

    return {"ok": True, "text": text}


@router.get("/llm/stream")
async def health_llm_stream(
    q: Optional[str] = Query(None, description=HEALTHCHECK_QUERY_DESCRIPTION),
):
    tokens: list[str] = []
    try:
        async for piece in iter_chunks_async(
            stream_noa_response(
                system_prompt="(healthcheck-stream)",
                task_prompt=None,
                conversation=[("user", q or DEFAULT_PONG_PROMPT)],
            )
        ):
            if piece:
                tokens.append(piece)
    except RuntimeError as e:
        msg = str(e)
        if msg == "blocked_by_content_filter":
            raise HTTPException(status_code=503, detail="blocked_by_content_filter")
        if msg == "empty_completion_from_llm":
            raise HTTPException(status_code=503, detail="llm_empty_response")
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"llm_stream_error: {e}")

    text = ("".join(tokens)).strip()
    if not text:
        raise HTTPException(status_code=503, detail="llm_stream_empty")

    if q is None and "pong" not in text.lower():
        return {
            "ok": False,
            "detail": "unexpected_content",
            "tokens": len(tokens),
            "text": text,
        }

    return {"ok": True, "tokens": len(tokens), "text": text}
