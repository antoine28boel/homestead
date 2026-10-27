"""Stage of each planting."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomesteadConfigEntry
from .const import STAGES
from .entity import HomesteadEntity, planting_device
from .garden import Garden

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomesteadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One stage selector per planting."""
    garden = entry.runtime_data
    for planting_id in garden.plantings:
        async_add_entities(
            [StageSelect(garden, planting_id)], config_subentry_id=planting_id
        )


class StageSelect(HomesteadEntity, SelectEntity):
    """Planned, sown, transplanted… Changing it records today's date."""

    _attr_options = STAGES

    def __init__(self, garden: Garden, planting_id: str) -> None:
        """Attach to the planting device."""
        planting = garden.plantings[planting_id]
        super().__init__(
            garden, "stage", planting_id, planting_device(garden, planting)
        )
        self._planting_id = planting_id

    @property
    def current_option(self) -> str:
        """Current stage."""
        return self.garden.state(self._planting_id).stage

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Day each stage was reached."""
        return {
            stage: day.isoformat()
            for stage, day in self.garden.state(self._planting_id).dates.items()
        }

    async def async_select_option(self, option: str) -> None:
        """Move the planting to another stage."""
        await self.garden.async_set_stage(self._planting_id, option)
