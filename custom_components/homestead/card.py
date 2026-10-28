"""The garden plan card for dashboards, and the plan it draws."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import HomesteadCoordinator

CARD_FILE = Path(__file__).parent / "card" / "homestead-plan-card.js"
CARD_URL = f"/{DOMAIN}/homestead-plan-card.js"


async def async_setup_card(hass: HomeAssistant) -> None:
    """Serve the card and load it on every dashboard."""
    websocket_api.async_register_command(hass, ws_subscribe_plan)
    if hass.http is None or "frontend" not in hass.config.components:
        return
    # Imported here: the frontend is optional (tests, minimal setups).
    from homeassistant.components.frontend import (
        add_extra_js_url,
    )
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=False)]
    )
    version = (await async_get_integration(hass, DOMAIN)).version
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")


def plan_message(
    hass: HomeAssistant, coordinator: HomesteadCoordinator
) -> dict[str, Any]:
    """What the card needs: the plan, the season, and entities to open on tap."""
    data = coordinator.data
    registry = er.async_get(hass)
    entities = {}
    for space in data["spaces"]:
        if entity_id := registry.async_get_entity_id(
            "sensor", DOMAIN, f"{space['id']}_plantings"
        ):
            entities[space["id"]] = entity_id
    for planting in data["plantings"]:
        if entity_id := registry.async_get_entity_id(
            "select", DOMAIN, f"{planting['id']}_stage"
        ):
            entities[planting["id"]] = entity_id
    return {
        "entry_id": coordinator.config_entry.entry_id,
        "garden": data["garden"]["name"],
        "today": data["today"],
        "latitude": hass.config.latitude,
        "plan": data.get("plan"),
        "entities": entities,
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/plan/subscribe",
        vol.Optional("entry_id"): str,
    }
)
@callback
def ws_subscribe_plan(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Send the plan now, then again whenever the garden changes."""
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
        and msg.get("entry_id") in (None, entry.entry_id)
    ]
    if not entries:
        connection.send_error(msg["id"], "not_found", "No Homestead garden loaded")
        return
    coordinator: HomesteadCoordinator = entries[0].runtime_data

    @callback
    def forward() -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], plan_message(hass, coordinator))
        )

    connection.subscriptions[msg["id"]] = coordinator.async_add_listener(forward)
    connection.send_result(msg["id"])
    forward()
