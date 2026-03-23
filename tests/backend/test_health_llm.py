from __future__ import annotations

import asyncio
import importlib
import sys
import types
import unittest

DEFAULT_PONG_PROMPT = "\ub108\ub294 \uac04\ub2e8\ud788 \ud55c \ub2e8\uc5b4\ub85c\ub9cc \ub300\ub2f5\ud574: pong"


def _install_fastapi_stub():
    fastapi = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, *, status_code: int, detail):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class APIRouter:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def _decorator(fn):
                return fn

            return _decorator

    def Query(default=None, **kwargs):
        return default

    fastapi.APIRouter = APIRouter
    fastapi.HTTPException = HTTPException
    fastapi.Query = Query
    sys.modules["fastapi"] = fastapi
    return HTTPException


def _load_health_module():
    http_exception = _install_fastapi_stub()
    sys.modules.pop("app.backend.routers.health_llm", None)
    module = importlib.import_module("app.backend.routers.health_llm")
    return module, http_exception


class HealthLLMTests(unittest.TestCase):
    def test_health_llm_passes_backend_signature(self) -> None:
        module, _ = _load_health_module()
        captured = {}

        def _fake_generate_noa_response(**kwargs):
            captured.update(kwargs)
            return "pong"

        module.generate_noa_response = _fake_generate_noa_response

        result = module.health_llm()

        self.assertEqual(result, {"ok": True, "text": "pong"})
        self.assertEqual(
            captured,
            {
                "system_prompt": "(healthcheck)",
                "task_prompt": None,
                "conversation": [("user", DEFAULT_PONG_PROMPT)],
            },
        )

    def test_health_llm_raises_on_empty_text(self) -> None:
        module, http_exception = _load_health_module()
        module.generate_noa_response = lambda **kwargs: ""

        with self.assertRaises(http_exception) as ctx:
            module.health_llm()

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail, "llm_empty_response")

    def test_health_llm_returns_unexpected_content_for_default_probe(self) -> None:
        module, _ = _load_health_module()
        module.generate_noa_response = lambda **kwargs: "hello"

        result = module.health_llm()

        self.assertEqual(
            result,
            {"ok": False, "detail": "unexpected_content", "text": "hello"},
        )

    def test_health_llm_custom_query_skips_default_pong_check(self) -> None:
        module, _ = _load_health_module()
        captured = {}

        def _fake_generate_noa_response(**kwargs):
            captured.update(kwargs)
            return "hello"

        module.generate_noa_response = _fake_generate_noa_response

        result = module.health_llm(q="say hello")

        self.assertEqual(result, {"ok": True, "text": "hello"})
        self.assertEqual(
            captured,
            {
                "system_prompt": "(healthcheck)",
                "task_prompt": None,
                "conversation": [("user", "say hello")],
            },
        )

    def test_health_llm_stream_collects_chunks_via_bridge(self) -> None:
        module, _ = _load_health_module()
        captured = {}

        def _fake_stream_noa_response(**kwargs):
            captured.update(kwargs)
            yield "po"
            yield "ng"

        module.stream_noa_response = _fake_stream_noa_response

        result = asyncio.run(module.health_llm_stream())

        self.assertEqual(
            captured,
            {
                "system_prompt": "(healthcheck-stream)",
                "task_prompt": None,
                "conversation": [("user", DEFAULT_PONG_PROMPT)],
            },
        )
        self.assertEqual(result, {"ok": True, "tokens": 2, "text": "pong"})

    def test_health_llm_stream_returns_unexpected_content_for_default_probe(self) -> None:
        module, _ = _load_health_module()

        def _fake_stream_noa_response(**kwargs):
            yield "hello"

        module.stream_noa_response = _fake_stream_noa_response

        result = asyncio.run(module.health_llm_stream())

        self.assertEqual(
            result,
            {"ok": False, "detail": "unexpected_content", "tokens": 1, "text": "hello"},
        )

    def test_health_llm_stream_maps_blocked_content_filter_error(self) -> None:
        module, http_exception = _load_health_module()
        module.stream_noa_response = lambda **kwargs: iter(())

        async def _fake_iter_chunks_async(_iterable):
            if False:
                yield ""
            raise RuntimeError("blocked_by_content_filter")

        module.iter_chunks_async = _fake_iter_chunks_async

        with self.assertRaises(http_exception) as ctx:
            asyncio.run(module.health_llm_stream())

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail, "blocked_by_content_filter")

    def test_health_llm_stream_maps_generic_error(self) -> None:
        module, http_exception = _load_health_module()
        module.stream_noa_response = lambda **kwargs: iter(())

        async def _fake_iter_chunks_async(_iterable):
            if False:
                yield ""
            raise ValueError("boom")

        module.iter_chunks_async = _fake_iter_chunks_async

        with self.assertRaises(http_exception) as ctx:
            asyncio.run(module.health_llm_stream())

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail, "llm_stream_error: boom")


if __name__ == "__main__":
    unittest.main()
