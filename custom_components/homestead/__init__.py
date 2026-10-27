"""The Homestead integration: garden, greenhouse, orchard and coop."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

from .catalog import Species, load_catalog
from .const import DOMAIN
from .garden import Garden

PLATFORMS: list[Platform] = [
    Platform.CALENDAR,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.TODO,
]

CATALOG_KEY: HassKey[dict[str, Species]] = HassKey(f"{DOMAIN}_catalog")

type HomesteadConfigEntry = ConfigEntry[Garden]


async def async_get_catalog(hass: HomeAssistant) -> dict[str, Species]:
    """The species catalogue, read once."""
    if CATALOG_KEY not in hass.data:
        hass.data[CATALOG_KEY] = await hass.async_add_executor_job(load_catalog)
    return hass.data[CATALOG_KEY]


async def async_setup_entry(hass: HomeAssistant, entry: HomesteadConfigEntry) -> bool:
    """Set up a garden from a config entry."""
    garden = Garden(hass, entry, await async_get_catalog(hass))
    await garden.async_load()
    entry.runtime_data = garden
    entry.async_on_unload(garden.async_start())
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: HomesteadConfigEntry) -> None:
    """Spaces, plantings or frost dates changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HomesteadConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: HomesteadConfigEntry) -> None:
    """Delete the stored state of a removed garden."""
    garden = Garden(hass, entry, await async_get_catalog(hass))
    await garden.async_remove()
