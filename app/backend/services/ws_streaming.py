from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from app.backend.services.ws_utils import safe_str


async def ws_send_safe(
    websocket: WebSocket,
    data: dict,
    *,
    timeout: float | None = None,
    logger: logging.Logger,
) -> None:
    payload = jsonable_encoder(data, exclude_none=True)

    async def _send() -> None:
        await websocket.send_json(payload)

    try:
        if timeout:
            await asyncio.wait_for(_send(), timeout=timeout)
        else:
            await _send()
    except Exception as exc:
        logger.warning("WS send failed | %s | keys=%s", safe_str(exc), list(data.keys()))


class OutboundWSChannel:
    def __init__(
        self,
        *,
        websocket: WebSocket,
        heartbeat_sec: float,
        send_buffer: int,
        shutdown: asyncio.Event,
        logger: logging.Logger,
        close_ws: Callable[..., Awaitable[None]],
        send_backpressure_error: type[Exception],
        ping_message: dict[str, Any],
    ) -> None:
        self.websocket = websocket
        self.heartbeat_sec = heartbeat_sec
        self.shutdown = shutdown
        self.logger = logger
        self.close_ws = close_ws
        self.send_backpressure_error = send_backpressure_error
        self.ping_message = ping_message
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=send_buffer)
        self.loop = asyncio.get_running_loop()
        self.last_active = self.loop.time()

    async def sender(self) -> None:
        try:
            while not self.shutdown.is_set():
                try:
                    item = await asyncio.wait_for(self.queue.get(), timeout=self.heartbeat_sec)
                except asyncio.TimeoutError:
                    await ws_send_safe(
                        self.websocket,
                        self.ping_message,
                        logger=self.logger,
                    )
                    continue
                try:
                    await ws_send_safe(self.websocket, item, logger=self.logger)
                    self.last_active = self.loop.time()
                finally:
                    self.queue.task_done()
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            self.logger.warning("WS sender loop error | %s", safe_str(exc))
        finally:
            self.shutdown.set()

    async def guard_send(self, data: dict[str, Any]) -> None:
        if self.shutdown.is_set():
            return
        try:
            await asyncio.wait_for(self.queue.put(data), timeout=self.heartbeat_sec)
        except asyncio.TimeoutError:
            self.shutdown.set()
            with suppress(Exception):
                await ws_send_safe(
                    self.websocket,
                    {"type": "error", "message": "send_backpressure"},
                    timeout=1,
                    logger=self.logger,
                )
            with suppress(Exception):
                await self.close_ws(code=1013, reason="send_backpressure")
            raise self.send_backpressure_error("send_queue_backpressure")

    async def flush(self) -> None:
        try:
            await asyncio.wait_for(self.queue.join(), timeout=self.heartbeat_sec)
        except asyncio.TimeoutError:
            self.logger.warning("WS outbound flush timed out before close")
