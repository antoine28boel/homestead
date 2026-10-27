"""Sensors of plantings and spaces."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HomesteadConfigEntry, HomesteadCoordinator
from .entity import PlantingEntity, SpaceEntity, async_add_for_each

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomesteadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Sensors for every space and every active planting."""

    def for_space(coordinator: HomesteadCoordinator, space: dict[str, Any]) -> list:
        return [
            SpacePlantingsSensor(coordinator, space),
            SowNowSensor(coordinator, space),
        ]

    def for_planting(
        coordinator: HomesteadCoordinator, planting: dict[str, Any]
    ) -> list:
        return [
            NextTaskSensor(coordinator, planting),
            NextTaskDueSensor(coordinator, planting),
            HarvestSensor(coordinator, planting),
            HarvestedSensor(coordinator, planting),
        ]

    async_add_for_each(entry, "spaces", for_space, async_add_entities)
    async_add_for_each(entry, "plantings", for_planting, async_add_entities)


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


class SpacePlantingsSensor(SpaceEntity, SensorEntity):
    """Number of plantings in progress in a space."""

    def __init__(
        self, coordinator: HomesteadCoordinator, space: dict[str, Any]
    ) -> None:
        """Attach to the space device."""
        super().__init__(coordinator, space, "plantings")

    @property
    def _names(self) -> list[str]:
        return [
            planting["name"]
            for planting in self.coordinator.data["plantings"]
            if planting["space_id"] == self._space_id
        ]

    @property
    def native_value(self) -> int:
        """Count of unfinished plantings."""
        return len(self._names)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Their names."""
        return {"plantings": self._names}


class SowNowSensor(SpaceEntity, SensorEntity):
    """Crops that can be started in this space now."""

    def __init__(
        self, coordinator: HomesteadCoordinator, space: dict[str, Any]
    ) -> None:
        """Attach to the space device."""
        super().__init__(coordinator, space, "sow_now")

    @property
    def _lists(self) -> dict[str, list[str]]:
        methods = self.coordinator.data["sow_now"].get(self._space_id, {})
        return {
            method: [item["name"] for item in species]
            for method, species in methods.items()
        }

    @property
    def native_value(self) -> int:
        """Number of crops."""
        return len({name for names in self._lists.values() for name in names})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Crops by method: sow_indoors, sow_direct, plant."""
        return self._lists


class NextTaskSensor(PlantingEntity, SensorEntity):
    """What to do next for a planting."""

    def __init__(
        self, coordinator: HomesteadCoordinator, planting: dict[str, Any]
    ) -> None:
        """Attach to the planting device."""
        super().__init__(coordinator, planting, "next_task")

    @property
    def native_value(self) -> str | None:
        """Summary of the next task."""
        task = self.planting["next_task"]
        return task["summary"][:255] if task else None


class NextTaskDueSensor(PlantingEntity, SensorEntity):
    """When the next task of a planting is due."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(
        self, coordinator: HomesteadCoordinator, planting: dict[str, Any]
    ) -> None:
        """Attach to the planting device."""
        super().__init__(coordinator, planting, "next_task_due")

    @property
    def native_value(self) -> date | None:
        """Due date of the next task."""
        task = self.planting["next_task"]
        return _day(task["due"]) if task else None


class HarvestSensor(PlantingEntity, SensorEntity):
    """Expected start of harvest."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(
        self, coordinator: HomesteadCoordinator, planting: dict[str, Any]
    ) -> None:
        """Attach to the planting device."""
        super().__init__(coordinator, planting, "harvest")

    @property
    def native_value(self) -> date | None:
        """First day of harvest."""
        return _day(self.planting["schedule"]["harvest"][0])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expected end of harvest."""
        return {"end": self.planting["schedule"]["harvest"][1]}


class HarvestedSensor(PlantingEntity, SensorEntity):
    """Weight harvested so far."""

    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self, coordinator: HomesteadCoordinator, planting: dict[str, Any]
    ) -> None:
        """Attach to the planting device."""
        super().__init__(coordinator, planting, "harvested")

    @property
    def native_value(self) -> float:
        """Kilograms harvested."""
        return self.planting["harvested"].get("kg", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Pieces counted, for crops counted rather than weighed."""
        return {"pieces": self.planting["harvested"].get("pieces", 0)}
