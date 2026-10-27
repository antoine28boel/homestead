"""Calendar of sowing, planting-out and harvest periods."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import HomesteadError
from .const import DOMAIN
from .coordinator import HomesteadConfigEntry, HomesteadCoordinator
from .entity import HomesteadEntity, garden_device

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomesteadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One calendar per garden."""
    async_add_entities([GardenCalendar(entry.runtime_data)])


def _event(event: dict[str, Any]) -> CalendarEvent:
    return CalendarEvent(
        start=date.fromisoformat(event["start"]),
        end=date.fromisoformat(event["end"]),
        summary=event["summary"],
        location=event["location"],
        uid=event["uid"],
    )


class GardenCalendar(HomesteadEntity, CalendarEntity):
    """All-day events, one per period of each planting."""

    def __init__(self, coordinator: HomesteadCoordinator) -> None:
        """Attach to the garden device."""
        super().__init__(
            coordinator,
            "calendar",
            coordinator.data["instance_id"],
            garden_device(coordinator),
        )

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next event."""
        today = self.coordinator.data["today"]
        return next(
            (
                _event(event)
                for event in self.coordinator.data["events"]
                if event["end"] > today
            ),
            None,
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Events overlapping the requested range."""
        try:
            events = await self.coordinator.client.calendar(
                start_date.date(), end_date.date() + timedelta(days=1)
            )
        except HomesteadError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="server_error",
                translation_placeholders={"error": str(err)},
            ) from err
        return [_event(event) for event in events]
