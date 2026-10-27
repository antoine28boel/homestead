"""Base entity and devices of the Homestead integration."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .garden import Garden
from .planner import Planting, Space


def garden_device(garden: Garden) -> DeviceInfo:
    """The garden itself, which holds the to-do list and the calendar."""
    return DeviceInfo(
        identifiers={(DOMAIN, garden.entry.entry_id)},
        name=garden.entry.title,
        entry_type=DeviceEntryType.SERVICE,
    )


def space_device(garden: Garden, space: Space) -> DeviceInfo:
    """A bed, a greenhouse…"""
    return DeviceInfo(
        identifiers={(DOMAIN, space.id)},
        name=space.name,
        via_device=(DOMAIN, garden.entry.entry_id),
    )


def planting_device(garden: Garden, planting: Planting) -> DeviceInfo:
    """A crop in a space."""
    return DeviceInfo(
        identifiers={(DOMAIN, planting.id)},
        name=garden.planting_name(planting),
        model=planting.species.name(garden.texts.language),
        via_device=(
            DOMAIN,
            planting.space.id if planting.space else garden.entry.entry_id,
        ),
    )


class HomesteadEntity(Entity):
    """An entity that follows the state of its garden."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, garden: Garden, key: str, device_id: str, device_info: DeviceInfo
    ) -> None:
        """Name the entity after its translation key."""
        self.garden = garden
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        """Follow the garden."""
        await super().async_added_to_hass()
        self.async_on_remove(self.garden.async_add_listener(self._handle_garden))

    @callback
    def _handle_garden(self) -> None:
        self.async_write_ha_state()
