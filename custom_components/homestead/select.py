"""Stage of each planting."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import HomesteadError
from .const import DOMAIN, STAGES
from .coordinator import HomesteadConfigEntry, HomesteadCoordinator
from .entity import PlantingEntity, async_add_for_each

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomesteadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One stage selector per active planting."""

    def make(coordinator: HomesteadCoordinator, planting: dict[str, Any]) -> list:
        return [StageSelect(coordinator, planting)]

    async_add_for_each(entry, "plantings", make, async_add_entities)


class StageSelect(PlantingEntity, SelectEntity):
    """Planned, sown, planted out… Changing it records today's date."""

    _attr_options = STAGES

    def __init__(
        self, coordinator: HomesteadCoordinator, planting: dict[str, Any]
    ) -> None:
        """Attach to the planting device."""
        super().__init__(coordinator, planting, "stage")

    @property
    def current_option(self) -> str:
        """Current stage."""
        return self.planting["stage"]

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Day each stage was reached."""
        return self.planting["dates"]

    async def async_select_option(self, option: str) -> None:
        """Move the planting to another stage."""
        try:
            await self.coordinator.client.set_stage(self._planting_id, option)
        except HomesteadError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="server_error",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
