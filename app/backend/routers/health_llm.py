from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.backend.services.llm_service import generate_noa_response, stream_noa_response

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/llm")
def health_llm(
    q: Optional[str] = Query(None, description="Healthcheck prompt (defaults to pong check)"),
):
    prompt = q or "Respond with only one word: pong"
    text = generate_noa_response(
        system_prompt="(healthcheck)",
        task_prompt=None,
        conversation=[("user", prompt)],
    )
    text = (text or "").strip()

    if not text:
        raise HTTPException(status_code=503, detail="llm_empty_response")

    if q is None and "pong" not in text.lower():
        return {"ok": False, "detail": "unexpected_content", "text": text}

    return {"ok": True, "text": text}


@router.get("/llm/stream")
def health_llm_stream(
    q: Optional[str] = Query(None, description="Healthcheck prompt (defaults to pong check)"),
):
    prompt = q or "Respond with only one word: pong"

    tokens: list[str] = []
    try:
        for piece in stream_noa_response(
            system_prompt="(healthcheck-stream)",
            task_prompt=None,
            conversation=[("user", prompt)],
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
