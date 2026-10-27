"""The Homestead integration: garden, greenhouse, orchard and coop."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .models import ClimateProfile

# Entities arrive in phase 1 (todo list, calendar, sensors).
PLATFORMS: list[Platform] = []


@dataclass(slots=True)
class HomesteadData:
    """Runtime data of one garden."""

    climate: ClimateProfile


type HomesteadConfigEntry = ConfigEntry[HomesteadData]


async def async_setup_entry(hass: HomeAssistant, entry: HomesteadConfigEntry) -> bool:
    """Set up a garden from a config entry."""
    entry.runtime_data = HomesteadData(
        climate=ClimateProfile.from_options(dict(entry.options))
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomesteadConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
