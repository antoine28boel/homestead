"""Actions: log a harvest or a journal entry from an automation or a dashboard."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .api import HomesteadError
from .const import DOMAIN, HARVEST_UNITS, JOURNAL_KINDS
from .coordinator import HomesteadCoordinator

ATTR_DEVICE = "device_id"
ATTR_QUANTITY = "quantity"
ATTR_UNIT = "unit"
ATTR_DAY = "day"
ATTR_NOTE = "note"
ATTR_KIND = "kind"
ATTR_AMOUNT = "amount"

SERVICE_LOG_HARVEST = "log_harvest"
SERVICE_LOG_JOURNAL = "log_journal"

LOG_HARVEST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE): cv.string,
        vol.Required(ATTR_QUANTITY): vol.All(
            vol.Coerce(float), vol.Range(min=0, min_included=False)
        ),
        vol.Optional(ATTR_UNIT, default="kg"): vol.In(HARVEST_UNITS),
        vol.Optional(ATTR_DAY): cv.date,
        vol.Optional(ATTR_NOTE, default=""): cv.string,
    }
)
LOG_JOURNAL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE): cv.string,
        vol.Optional(ATTR_KIND, default="observation"): vol.In(JOURNAL_KINDS),
        vol.Optional(ATTR_AMOUNT): vol.Coerce(float),
        vol.Optional(ATTR_UNIT): cv.string,
        vol.Optional(ATTR_DAY): cv.date,
        vol.Optional(ATTR_NOTE, default=""): cv.string,
    }
)


def _target(
    hass: HomeAssistant, device_id: str
) -> tuple[HomesteadCoordinator, str, str]:
    """The coordinator and the planting or space behind a device."""
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        keys = [key for domain, key in device.identifiers if domain == DOMAIN]
        entry = hass.config_entries.async_get_entry(device.config_entry_id)
        if (
            entry is not None
            and entry.domain == DOMAIN
            and entry.state is ConfigEntryState.LOADED
        ):
            coordinator: HomesteadCoordinator = entry.runtime_data
            for key in keys:
                if coordinator.planting(key):
                    return coordinator, "planting_id", key
                if coordinator.space(key):
                    return coordinator, "space_id", key
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="unknown_device",
    )


async def _send(
    coordinator: HomesteadCoordinator, method: str, data: dict[str, Any]
) -> None:
    try:
        await getattr(coordinator.client, method)(data)
    except HomesteadError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="server_error",
            translation_placeholders={"error": str(err)},
        ) from err
    await coordinator.async_request_refresh()


def _day(call: ServiceCall) -> str | None:
    day = call.data.get(ATTR_DAY)
    return day.isoformat() if day else None


async def _log_harvest(call: ServiceCall) -> None:
    coordinator, kind, key = _target(call.hass, call.data[ATTR_DEVICE])
    if kind != "planting_id":
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="harvest_needs_planting",
        )
    await _send(
        coordinator,
        "add_harvest",
        {
            "planting_id": key,
            "quantity": call.data[ATTR_QUANTITY],
            "unit": call.data[ATTR_UNIT],
            "day": _day(call),
            "note": call.data[ATTR_NOTE],
        },
    )


async def _log_journal(call: ServiceCall) -> None:
    coordinator, kind, key = _target(call.hass, call.data[ATTR_DEVICE])
    await _send(
        coordinator,
        "add_journal",
        {
            kind: key,
            "kind": call.data[ATTR_KIND],
            "amount": call.data.get(ATTR_AMOUNT),
            "unit": call.data.get(ATTR_UNIT),
            "day": _day(call),
            "note": call.data[ATTR_NOTE],
        },
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions."""
    hass.services.async_register(
        DOMAIN, SERVICE_LOG_HARVEST, _log_harvest, schema=LOG_HARVEST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_LOG_JOURNAL, _log_journal, schema=LOG_JOURNAL_SCHEMA
    )
