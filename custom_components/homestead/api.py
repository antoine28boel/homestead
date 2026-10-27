"""Client of the Homestead server's API."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import aiohttp


class HomesteadError(Exception):
    """The server answered with an error."""


class HomesteadConnectionError(HomesteadError):
    """The server cannot be reached."""


class HomesteadAuthError(HomesteadError):
    """The token was refused."""


class HomesteadClient:
    """Talks to one Homestead server."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        """Remember where the server is."""
        self._session = session
        self.url = url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self.url}/api/{path}",
                json=json,
                params=params,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status == 401:
                    raise HomesteadAuthError
                if response.status >= 400:
                    raise HomesteadError(f"{response.status}: {await response.text()}")
                if response.status == 204:
                    return None
                return await response.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomesteadConnectionError(str(err)) from err

    async def info(self) -> dict[str, Any]:
        """Version, language and identity of the server."""
        return await self._request("GET", "info")

    async def summary(self) -> dict[str, Any]:
        """Spaces, active plantings, tasks and upcoming events."""
        return await self._request("GET", "summary")

    async def calendar(self, start: date, end: date) -> list[dict[str, Any]]:
        """Events overlapping [start, end)."""
        return await self._request(
            "GET",
            "calendar",
            params={"start": start.isoformat(), "end": end.isoformat()},
        )

    async def set_stage(self, planting_id: str, stage: str) -> None:
        """Move a planting to a stage, today."""
        await self._request(
            "POST", f"plantings/{planting_id}/stage", json={"stage": stage}
        )

    async def create_task(self, data: dict[str, Any]) -> None:
        """Add an own item to the to-do list."""
        await self._request("POST", "tasks", json=data)

    async def update_task(self, uid: str, data: dict[str, Any]) -> None:
        """Tick, untick or change a to-do item."""
        await self._request("PATCH", f"tasks/{uid}", json=data)

    async def delete_task(self, uid: str) -> None:
        """Delete an own item or hide a generated task."""
        await self._request("DELETE", f"tasks/{uid}")

    async def add_journal(self, data: dict[str, Any]) -> None:
        """Write in the journal."""
        await self._request("POST", "journal", json=data)

    async def add_harvest(self, data: dict[str, Any]) -> None:
        """Log a harvest."""
        await self._request("POST", "harvests", json=data)

    async def listen(self, on_notice: Callable[[str], None]) -> None:
        """Call `on_notice` for each notice, until the connection closes."""
        try:
            async with self._session.ws_connect(
                f"{self.url}/api/ws", headers=self._headers, heartbeat=30
            ) as socket:
                async for message in socket:
                    if message.type is aiohttp.WSMsgType.TEXT:
                        on_notice(message.json().get("type", ""))
                    elif message.type is aiohttp.WSMsgType.ERROR:
                        break
        except aiohttp.WSServerHandshakeError as err:
            if err.status == 401:
                raise HomesteadAuthError from err
            raise HomesteadConnectionError(str(err)) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomesteadConnectionError(str(err)) from err
