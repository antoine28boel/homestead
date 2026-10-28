"""Homestead: the garden app's companion in Home Assistant."""

from __future__ import annotations

from homeassistant.const import CONF_TOKEN, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import HomesteadClient
from .card import async_setup_card
from .const import DOMAIN
from .coordinator import HomesteadConfigEntry, HomesteadCoordinator
from .entity import async_sync_devices
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.CALENDAR,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.TODO,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions and the plan card."""
    async_setup_services(hass)
    await async_setup_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HomesteadConfigEntry) -> bool:
    """Connect to a Homestead server."""
    client = HomesteadClient(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN]
    )
    coordinator = HomesteadCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async_sync_devices(entry)
    entry.async_on_unload(
        coordinator.async_add_listener(lambda: async_sync_devices(entry))
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_create_background_task(
        hass, coordinator.async_listen(), f"{DOMAIN} notices"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomesteadConfigEntry) -> bool:
    """Disconnect."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: HomesteadConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Devices of things the server no longer has can be removed by hand."""
    keep = entry.runtime_data.device_keys()
    return not any(
        key in keep for domain, key in device.identifiers if domain == DOMAIN
    )
