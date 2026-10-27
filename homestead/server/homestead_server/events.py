"""Tells WebSocket clients (the web interface, Home Assistant) that data changed."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class Events:
    """Fan-out of "changed" notices.

    Requests run in worker threads, so `notify` can be called from any thread.
    Clients only learn that something changed and fetch what they need.
    """

    def __init__(self) -> None:
        """No loop until the server starts."""
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queues: set[asyncio.Queue[str]] = set()

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        """Attach to the server's event loop."""
        self._loop = loop

    def notify(self, topic: str = "changed") -> None:
        """Send a notice to every client."""
        if self._loop is None or self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._publish, topic)

    def _publish(self, topic: str) -> None:
        for queue in self._queues:
            queue.put_nowait(topic)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[str]]:
        """Receive notices while the context is open."""
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._queues.add(queue)
        try:
            yield queue
        finally:
            self._queues.discard(queue)
