"""Calendar of sowing, planting-out and harvest periods."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HomesteadConfigEntry
from .entity import HomesteadEntity, garden_device
from .garden import Garden

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomesteadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One calendar per garden."""
    async_add_entities([GardenCalendar(entry.runtime_data)])


class GardenCalendar(HomesteadEntity, CalendarEntity):
    """All-day events, one per period of each planting."""

    def __init__(self, garden: Garden) -> None:
        """Attach to the garden device."""
        super().__init__(
            garden, "calendar", garden.entry.entry_id, garden_device(garden)
        )

    def _events(self) -> list[CalendarEvent]:
        garden = self.garden
        events = []
        for planting_id, planting in garden.plantings.items():
            plan = garden.schedule(planting_id)
            name = garden.planting_name(planting)
            for kind, period in (
                ("sow", plan.sow),
                ("transplant", plan.transplant),
                ("harvest", plan.harvest),
            ):
                if period is None:
                    continue
                events.append(
                    CalendarEvent(
                        start=period[0],
                        end=period[1] + timedelta(days=1),
                        summary=garden.texts(f"event_{kind}", name=name),
                        location=garden.space_name(planting),
                        uid=f"{planting_id}.{kind}",
                    )
                )
        return sorted(events, key=lambda event: (event.start, event.summary))

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next event."""
        today = self.garden.today()
        return next((event for event in self._events() if event.end > today), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Events overlapping the requested range."""
        return [
            event
            for event in self._events()
            if dt_util.start_of_local_day(event.start) < end_date
            and dt_util.start_of_local_day(event.end) > start_date
        ]
