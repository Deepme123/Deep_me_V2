from __future__ import annotations

import asyncio
import inspect
import threading
from collections.abc import AsyncGenerator, AsyncIterable, Iterable
from typing import Any


def iter_chunks_async(
    source: Iterable[str] | AsyncIterable[str],
) -> AsyncGenerator[str, None]:
    if inspect.isasyncgen(source) or hasattr(source, "__aiter__"):
        async def _async_passthrough() -> AsyncGenerator[str, None]:
            async for item in source:  # type: ignore[misc]
                yield item

        return _async_passthrough()

    async def _from_sync_iterable() -> AsyncGenerator[str, None]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        def _worker() -> None:
            try:
                for item in source:  # type: ignore[union-attr]
                    loop.call_soon_threadsafe(queue.put_nowait, ("data", item))
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

        threading.Thread(target=_worker, daemon=True).start()

        while True:
            kind, payload = await queue.get()
            if kind == "data":
                yield payload
                continue
            if kind == "error":
                raise payload
            break

    return _from_sync_iterable()
