"""Keeps Home Assistant in step with the Homestead server."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HomesteadAuthError, HomesteadClient, HomesteadError
from .const import DOMAIN, FALLBACK_INTERVAL, RECONNECT_MAX, RECONNECT_MIN

_LOGGER = logging.getLogger(__name__)

type HomesteadConfigEntry = ConfigEntry[HomesteadCoordinator]


class HomesteadCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The server's summary, refreshed whenever the server reports a change."""

    config_entry: HomesteadConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HomesteadConfigEntry,
        client: HomesteadClient,
    ) -> None:
        """Poll rarely: changes are pushed."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=FALLBACK_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.summary()
        except HomesteadAuthError as err:
            raise ConfigEntryAuthFailed from err
        except HomesteadError as err:
            raise UpdateFailed(str(err)) from err

    async def async_listen(self) -> None:
        """Follow the server's notices, reconnecting when needed."""
        delay = RECONNECT_MIN
        while True:
            try:
                await self.client.listen(self._handle_notice)
                delay = RECONNECT_MIN
            except HomesteadAuthError:
                self.config_entry.async_start_reauth(self.hass)
                return
            except HomesteadError as err:
                _LOGGER.debug("Notices from Homestead interrupted: %s", err)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

    @callback
    def _handle_notice(self, kind: str) -> None:
        """Something changed (or we just reconnected): fetch the summary."""
        self.config_entry.async_create_background_task(
            self.hass, self.async_request_refresh(), f"{DOMAIN} refresh"
        )

    def planting(self, planting_id: str) -> dict[str, Any] | None:
        """An active planting."""
        return next(
            (item for item in self.data["plantings"] if item["id"] == planting_id),
            None,
        )

    def space(self, space_id: str) -> dict[str, Any] | None:
        """A space."""
        return next(
            (item for item in self.data["spaces"] if item["id"] == space_id), None
        )

    def device_keys(self) -> set[str]:
        """Identifiers of the devices that should exist now."""
        return {
            self.data["instance_id"],
            *(space["id"] for space in self.data["spaces"]),
            *(planting["id"] for planting in self.data["plantings"]),
        }
