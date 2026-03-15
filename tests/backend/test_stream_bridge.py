from __future__ import annotations

import unittest

from app.backend.services.stream_bridge import iter_chunks_async


class StreamBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_iter_chunks_async_wraps_sync_iterables(self) -> None:
        def _sync_source():
            yield "a"
            yield "b"

        items = []
        async for item in iter_chunks_async(_sync_source()):
            items.append(item)

        self.assertEqual(items, ["a", "b"])

    async def test_iter_chunks_async_propagates_sync_errors(self) -> None:
        def _broken_source():
            yield "a"
            raise RuntimeError("boom")

        items = []
        with self.assertRaisesRegex(RuntimeError, "boom"):
            async for item in iter_chunks_async(_broken_source()):
                items.append(item)

        self.assertEqual(items, ["a"])


if __name__ == "__main__":
    unittest.main()
