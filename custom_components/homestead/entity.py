"""Base entities and devices of the Homestead integration."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomesteadConfigEntry, HomesteadCoordinator


def garden_device(coordinator: HomesteadCoordinator) -> DeviceInfo:
    """The garden itself, which holds the to-do list and the calendar."""
    data = coordinator.data
    return DeviceInfo(
        identifiers={(DOMAIN, data["instance_id"])},
        name=data["garden"]["name"],
        manufacturer="Homestead",
        sw_version=data["version"],
        entry_type=DeviceEntryType.SERVICE,
    )


def _registered(coordinator: HomesteadCoordinator, key: str | None) -> str | None:
    """Registry id of the garden's or a space's device."""
    if key is None:
        return None
    device = dr.async_get(coordinator.hass).async_get_device_by_identifier(
        (DOMAIN, key), coordinator.config_entry.entry_id
    )
    return device.id if device else None


def space_device(
    coordinator: HomesteadCoordinator, space: dict[str, Any]
) -> DeviceInfo:
    """A bed, a greenhouse… The garden's device must be registered."""
    garden_id = _registered(coordinator, coordinator.data["instance_id"])
    assert garden_id
    return DeviceInfo(
        identifiers={(DOMAIN, space["id"])},
        name=space["name"],
        manufacturer="Homestead",
        via_device_id=garden_id,
    )


def planting_device(
    coordinator: HomesteadCoordinator, planting: dict[str, Any]
) -> DeviceInfo:
    """A crop in a space, for one season; under the garden if its space is gone."""
    parent = _registered(coordinator, planting["space_id"]) or _registered(
        coordinator, coordinator.data["instance_id"]
    )
    assert parent
    return DeviceInfo(
        identifiers={(DOMAIN, planting["id"])},
        name=planting["name"],
        manufacturer="Homestead",
        model=planting["species_name"],
        via_device_id=parent,
    )


@callback
def async_sync_devices(entry: HomesteadConfigEntry) -> None:
    """Register the garden and its spaces; let finished plantings go.

    Runs before entities are added, so they can name their parent device.
    """
    coordinator = entry.runtime_data
    registry = dr.async_get(coordinator.hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id, **garden_device(coordinator)
    )
    for space in coordinator.data["spaces"]:
        registry.async_get_or_create(
            config_entry_id=entry.entry_id, **space_device(coordinator, space)
        )
    keep = coordinator.device_keys()
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if not any(
            key in keep for domain, key in device.identifiers if domain == DOMAIN
        ):
            registry.async_remove_device(device.id)


class HomesteadEntity(CoordinatorEntity[HomesteadCoordinator]):
    """An entity fed by the server's summary."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomesteadCoordinator,
        key: str,
        device_key: str,
        device_info: DeviceInfo,
    ) -> None:
        """Name the entity after its translation key."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_key}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info


class PlantingEntity(HomesteadEntity):
    """An entity of an active planting."""

    def __init__(
        self, coordinator: HomesteadCoordinator, planting: dict[str, Any], key: str
    ) -> None:
        """Attach to the planting's device."""
        super().__init__(
            coordinator, key, planting["id"], planting_device(coordinator, planting)
        )
        self._planting_id = planting["id"]

    @property
    def planting(self) -> dict[str, Any]:
        """Current data of the planting."""
        planting = self.coordinator.planting(self._planting_id)
        assert planting is not None
        return planting

    @property
    def available(self) -> bool:
        """Unavailable once the planting is finished or deleted."""
        return (
            super().available
            and self.coordinator.planting(self._planting_id) is not None
        )


class SpaceEntity(HomesteadEntity):
    """An entity of a space."""

    def __init__(
        self, coordinator: HomesteadCoordinator, space: dict[str, Any], key: str
    ) -> None:
        """Attach to the space's device."""
        super().__init__(
            coordinator, key, space["id"], space_device(coordinator, space)
        )
        self._space_id = space["id"]

    @property
    def available(self) -> bool:
        """Unavailable once the space is gone."""
        return super().available and self.coordinator.space(self._space_id) is not None


def async_add_for_each(
    entry: HomesteadConfigEntry,
    collection: str,
    make: Callable[[HomesteadCoordinator, dict[str, Any]], Iterable[Entity]],
    async_add_entities: Callable[[list[Entity]], None],
) -> None:
    """Add entities for each space or planting, now and as new ones appear."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new() -> None:
        items = coordinator.data[collection]
        known.intersection_update(item["id"] for item in items)
        new = [item for item in items if item["id"] not in known]
        if not new:
            return
        known.update(item["id"] for item in new)
        async_add_entities(
            [entity for item in new for entity in make(coordinator, item)]
        )

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))
