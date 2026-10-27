"""Sensors of plantings and spaces."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomesteadConfigEntry
from .entity import HomesteadEntity, planting_device, space_device
from .garden import Garden

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomesteadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Sensors for every space and every planting."""
    garden = entry.runtime_data
    for space_id in garden.spaces:
        async_add_entities(
            [SpacePlantingsSensor(garden, space_id), SowNowSensor(garden, space_id)],
            config_subentry_id=space_id,
        )
    for planting_id in garden.plantings:
        async_add_entities(
            [
                NextTaskSensor(garden, planting_id),
                NextTaskDueSensor(garden, planting_id),
                HarvestSensor(garden, planting_id),
            ],
            config_subentry_id=planting_id,
        )


class _SpaceSensor(HomesteadEntity, SensorEntity):
    def __init__(self, garden: Garden, space_id: str, key: str) -> None:
        super().__init__(
            garden, key, space_id, space_device(garden, garden.spaces[space_id])
        )
        self._space_id = space_id


class SpacePlantingsSensor(_SpaceSensor):
    """Number of plantings in progress in a space."""

    def __init__(self, garden: Garden, space_id: str) -> None:
        """Attach to the space device."""
        super().__init__(garden, space_id, "plantings")

    @property
    def native_value(self) -> int:
        """Count of unfinished plantings."""
        return len(self.garden.space_plantings(self._space_id))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Their names."""
        return {
            "plantings": [
                self.garden.planting_name(planting)
                for planting in self.garden.space_plantings(self._space_id)
            ]
        }


class SowNowSensor(_SpaceSensor):
    """Species that can be sown or planted now for this space."""

    def __init__(self, garden: Garden, space_id: str) -> None:
        """Attach to the space device."""
        super().__init__(garden, space_id, "sow_now")

    @property
    def native_value(self) -> int:
        """Number of species."""
        return len({name for names in self._lists.values() for name in names})

    @property
    def _lists(self) -> dict[str, list[str]]:
        return self.garden.sow_now(self._space_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Species by method: sow_indoors, sow_direct, plant."""
        return self._lists


class _PlantingSensor(HomesteadEntity, SensorEntity):
    def __init__(self, garden: Garden, planting_id: str, key: str) -> None:
        super().__init__(
            garden,
            key,
            planting_id,
            planting_device(garden, garden.plantings[planting_id]),
        )
        self._planting_id = planting_id


class NextTaskSensor(_PlantingSensor):
    """What to do next for a planting."""

    def __init__(self, garden: Garden, planting_id: str) -> None:
        """Attach to the planting device."""
        super().__init__(garden, planting_id, "next_task")

    @property
    def native_value(self) -> str | None:
        """Summary of the next task."""
        task = self.garden.next_task(self._planting_id)
        return task.summary[:255] if task else None


class NextTaskDueSensor(_PlantingSensor):
    """When the next task of a planting is due."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, garden: Garden, planting_id: str) -> None:
        """Attach to the planting device."""
        super().__init__(garden, planting_id, "next_task_due")

    @property
    def native_value(self) -> date | None:
        """Due date of the next task."""
        task = self.garden.next_task(self._planting_id)
        return task.due if task else None


class HarvestSensor(_PlantingSensor):
    """Expected start of harvest."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, garden: Garden, planting_id: str) -> None:
        """Attach to the planting device."""
        super().__init__(garden, planting_id, "harvest")

    @property
    def native_value(self) -> date | None:
        """First day of harvest, unless the planting is finished."""
        if not self.garden.is_active(self._planting_id):
            return None
        return self.garden.schedule(self._planting_id).harvest[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expected end of harvest."""
        return {"end": self.garden.schedule(self._planting_id).harvest[1].isoformat()}
