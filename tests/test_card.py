"""Tests for the garden plan card."""

from __future__ import annotations

from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.homestead.card import CARD_FILE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .test_init import _push


def test_card_file() -> None:
    """The card ships with the integration."""
    assert "homestead-plan-card" in CARD_FILE.read_text(encoding="utf-8")


async def test_plan_subscription(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded_entry: MockConfigEntry,
    mock_client: MagicMock,
    summary: dict,
) -> None:
    """The card gets the plan at once, then on every change."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "homestead/plan/subscribe"})
    response = await client.receive_json()
    assert response["success"]

    event = (await client.receive_json())["event"]
    assert event["entry_id"] == loaded_entry.entry_id
    assert event["garden"] == "Jardin"
    assert event["today"] == "2027-03-20"
    assert event["latitude"] == hass.config.latitude
    assert [space["id"] for space in event["plan"]["spaces"]] == ["greenhouse", "plot"]
    registry = er.async_get(hass)
    assert event["entities"]["plot"] == registry.async_get_entity_id(
        "sensor", "homestead", "plot_plantings"
    )
    assert event["entities"]["tomato1"] == registry.async_get_entity_id(
        "select", "homestead", "tomato1_stage"
    )

    summary["plan"]["items"] = []
    await _push(hass, loaded_entry, mock_client, summary)
    event = (await client.receive_json())["event"]
    assert event["plan"]["items"] == []


async def test_plan_subscription_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded_entry: MockConfigEntry,
) -> None:
    """Another garden, or none, is an error."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "homestead/plan/subscribe", "entry_id": "elsewhere"}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "not_found"

    await client.send_json_auto_id(
        {"type": "homestead/plan/subscribe", "entry_id": loaded_entry.entry_id}
    )
    assert (await client.receive_json())["success"]
