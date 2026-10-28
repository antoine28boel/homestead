"""Tests for the entities and actions of Homestead."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homestead.api import HomesteadAuthError, HomesteadConnectionError
from custom_components.homestead.const import DOMAIN
from homeassistant.components.todo import TodoItemStatus
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import INSTANCE_ID, TOMATO


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id, unique_id
    return entity_id


def _device(hass: HomeAssistant, key: str) -> dr.DeviceEntry | None:
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    return dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, key), entry.entry_id
    )


async def _push(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock, summary: dict
) -> None:
    """The server reports a change and the summary is fetched again."""
    mock_client.summary.return_value = summary
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_entities(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """The garden, its spaces and its plantings become devices with entities."""
    assert loaded_entry.state is ConfigEntryState.LOADED

    todo = hass.states.get(_entity_id(hass, "todo", f"{INSTANCE_ID}_tasks"))
    assert todo.state == "2"

    calendar = hass.states.get(_entity_id(hass, "calendar", f"{INSTANCE_ID}_calendar"))
    assert calendar.attributes["message"] == "Semis : Tomate Cœur de bœuf"
    assert calendar.attributes["location"] == "Potager"

    frost = hass.states.get(_entity_id(hass, "sensor", f"{INSTANCE_ID}_next_frost"))
    assert frost.state == "2027-03-22"
    assert frost.attributes["temperature"] == -1.5

    stage = hass.states.get(_entity_id(hass, "select", "tomato1_stage"))
    assert stage.state == "sown"
    assert stage.attributes["sown"] == "2027-03-20"

    assert hass.states.get(_entity_id(hass, "sensor", "tomato1_next_task")).state == (
        "Repiquer : Tomate Cœur de bœuf → Potager"
    )
    assert (
        hass.states.get(_entity_id(hass, "sensor", "tomato1_next_task_due")).state
        == "2027-05-22"
    )
    harvest = hass.states.get(_entity_id(hass, "sensor", "tomato1_harvest"))
    assert harvest.state == "2027-07-20"
    assert harvest.attributes["end"] == "2027-09-30"
    assert (
        hass.states.get(_entity_id(hass, "sensor", "tomato1_harvested")).state == "1.5"
    )

    plantings = hass.states.get(_entity_id(hass, "sensor", "plot_plantings"))
    assert plantings.state == "1"
    assert plantings.attributes["plantings"] == ["Tomate Cœur de bœuf"]
    sow_now = hass.states.get(_entity_id(hass, "sensor", "plot_sow_now"))
    assert sow_now.state == "1"
    assert sow_now.attributes["sow_indoors"] == ["Tomate"]
    assert (
        hass.states.get(_entity_id(hass, "sensor", "greenhouse_sow_now")).state == "0"
    )

    tomato = _device(hass, "tomato1")
    plot = _device(hass, "plot")
    garden = _device(hass, INSTANCE_ID)
    assert tomato.via_device_id == plot.id
    assert plot.via_device_id == garden.id
    assert tomato.model == "Tomate"


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (HomesteadConnectionError("down"), ConfigEntryState.SETUP_RETRY),
        (HomesteadAuthError(), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """An unreachable server is retried; a refused token asks for a new one."""
    mock_client.summary.side_effect = error
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is state
    reauth = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert bool(reauth) is isinstance(error, HomesteadAuthError)


async def test_new_and_finished_plantings(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    mock_client: MagicMock,
    summary: dict[str, Any],
) -> None:
    """New plantings get entities; finished ones leave."""
    lettuce = {**TOMATO, "id": "lettuce1", "name": "Laitue", "species_name": "Laitue"}
    summary["plantings"] = [*summary["plantings"], lettuce]
    await _push(hass, loaded_entry, mock_client, summary)
    assert hass.states.get(_entity_id(hass, "select", "lettuce1_stage")).state == "sown"
    assert hass.states.get(_entity_id(hass, "sensor", "plot_plantings")).state == "2"

    summary["plantings"] = [lettuce]
    await _push(hass, loaded_entry, mock_client, summary)
    assert _device(hass, "tomato1") is None
    assert (
        er.async_get(hass).async_get_entity_id("select", DOMAIN, "tomato1_stage")
        is None
    )
    assert _device(hass, "lettuce1") is not None


async def test_select_stage(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Choosing a stage sends it to the server."""
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": _entity_id(hass, "select", "tomato1_stage"),
            "option": "transplanted",
        },
        blocking=True,
    )
    mock_client.set_stage.assert_awaited_once_with("tomato1", "transplanted")


async def test_todo_items(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Ticking, adding, changing and removing items go to the server."""
    entity_id = _entity_id(hass, "todo", f"{INSTANCE_ID}_tasks")

    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": entity_id, "item": "tomato1.task.stake", "status": "completed"},
        blocking=True,
    )
    mock_client.update_task.assert_awaited_with(
        "tomato1.task.stake", {"completed": True}
    )

    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": entity_id, "item": "own1", "rename": "Acheter du compost"},
        blocking=True,
    )
    mock_client.update_task.assert_awaited_with(
        "own1",
        {
            "summary": "Acheter du compost",
            "due": None,
            "description": "Sacs de 40 L",
            "completed": False,
        },
    )

    await hass.services.async_call(
        "todo",
        "add_item",
        {"entity_id": entity_id, "item": "Pailler", "due_date": "2027-03-30"},
        blocking=True,
    )
    mock_client.create_task.assert_awaited_once_with(
        {"summary": "Pailler", "due": "2027-03-30", "description": None}
    )

    await hass.services.async_call(
        "todo",
        "remove_item",
        {"entity_id": entity_id, "item": ["own1", "tomato1.task.stake"]},
        blocking=True,
    )
    assert [call.args for call in mock_client.delete_task.await_args_list] == [
        ("own1",),
        ("tomato1.task.stake",),
    ]

    items = await hass.services.async_call(
        "todo",
        "get_items",
        {"entity_id": entity_id, "status": [TodoItemStatus.COMPLETED]},
        blocking=True,
        return_response=True,
    )
    assert [item["summary"] for item in items[entity_id]["items"]] == [
        "Semer sous abri : Tomate Cœur de bœuf"
    ]


async def test_calendar_events(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Calendar ranges are asked from the server."""
    mock_client.calendar.return_value = [
        {
            "uid": "tomato1.harvest",
            "summary": "Récolte : Tomate",
            "start": "2027-07-20",
            "end": "2027-10-01",
            "location": "Potager",
            "planting_id": "tomato1",
            "kind": "harvest",
        }
    ]
    entity_id = _entity_id(hass, "calendar", f"{INSTANCE_ID}_calendar")
    events = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": entity_id,
            "start_date_time": "2027-07-01 00:00:00",
            "end_date_time": "2027-08-01 00:00:00",
        },
        blocking=True,
        return_response=True,
    )
    assert events[entity_id]["events"][0]["summary"] == "Récolte : Tomate"
    start, end = mock_client.calendar.await_args.args
    assert start == date(2027, 7, 1)
    assert end == date(2027, 8, 2)


async def test_log_actions(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Harvests go to a planting; journal entries to a planting or a space."""
    tomato = _device(hass, "tomato1")
    plot = _device(hass, "plot")
    garden = _device(hass, INSTANCE_ID)

    await hass.services.async_call(
        DOMAIN,
        "log_harvest",
        {"device_id": tomato.id, "quantity": 2.4},
        blocking=True,
    )
    mock_client.add_harvest.assert_awaited_once_with(
        {
            "planting_id": "tomato1",
            "quantity": 2.4,
            "unit": "kg",
            "day": None,
            "note": "",
        }
    )

    await hass.services.async_call(
        DOMAIN,
        "log_journal",
        {
            "device_id": plot.id,
            "kind": "watering",
            "amount": 20,
            "unit": "L",
            "day": "2027-03-21",
        },
        blocking=True,
    )
    mock_client.add_journal.assert_awaited_once_with(
        {
            "space_id": "plot",
            "kind": "watering",
            "amount": 20.0,
            "unit": "L",
            "day": "2027-03-21",
            "note": "",
        }
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "log_harvest",
            {"device_id": plot.id, "quantity": 1},
            blocking=True,
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "log_journal",
            {"device_id": garden.id},
            blocking=True,
        )


async def test_unload(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """The entry unloads cleanly."""
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED
