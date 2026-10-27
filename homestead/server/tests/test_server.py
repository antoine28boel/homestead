"""The server as it really runs: uvicorn, HTTP and WebSocket on a port."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
import socket
import threading
import time

import httpx
import uvicorn
import websockets

from homestead_server.api import create_app
from homestead_server.config import Settings

from .conftest import BRUSSELS, HA_CONFIG


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_uvicorn_serves_websocket(tmp_path: Path) -> None:
    """The installed uvicorn can upgrade to WebSocket."""
    port = _free_port()
    app = create_app(
        Settings(data_dir=tmp_path, port=port),
        now=lambda: datetime(2027, 3, 20, 9, 0, tzinfo=BRUSSELS),
        ha_config=HA_CONFIG,
    )
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            assert time.monotonic() < deadline, "server did not start"
            time.sleep(0.05)

        async def exchange() -> list[dict]:
            async with websockets.connect(f"ws://127.0.0.1:{port}/api/ws") as socket_:
                hello = json.loads(await socket_.recv())
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"http://127.0.0.1:{port}/api/journal", json={"note": "x"}
                    )
                notice = json.loads(await asyncio.wait_for(socket_.recv(), 5))
                return [hello, notice]

        hello, notice = asyncio.run(exchange())
        assert hello["type"] == "hello"
        assert notice == {"type": "changed"}
    finally:
        server.should_exit = True
        thread.join(10)
