"""Tests for the entities of a garden: tasks, stages, calendar, sensors."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homestead.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import GREENHOUSE_ID, PLOT_ID, TOMATO_ID

# Greenhouse tomatoes are sown from 20 February (four weeks ahead of open ground).
SOWING_DAY = "2027-02-20 09:00:00+01:00"


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id, unique_id
    return entity_id


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _todo_items(hass: HomeAssistant, entity_id: str) -> list[dict]:
    result = await hass.services.async_call(
        "todo",
        "get_items",
        {"status": ["needs_action", "completed"]},
        target={"entity_id": entity_id},
        blocking=True,
        return_response=True,
    )
    return result[entity_id]["items"]


async def test_entities(
    hass: HomeAssistant, garden_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Every space and planting has its entities."""
    freezer.move_to(SOWING_DAY)
    await _setup(hass, garden_entry)

    stage = _entity_id(hass, "select", f"{TOMATO_ID}_stage")
    assert hass.states.get(stage).state == "planned"

    next_task = _entity_id(hass, "sensor", f"{TOMATO_ID}_next_task")
    assert hass.states.get(next_task).state == "Sow under cover: Tomato"
    due = _entity_id(hass, "sensor", f"{TOMATO_ID}_next_task_due")
    assert hass.states.get(due).state == "2027-02-20"
    harvest = _entity_id(hass, "sensor", f"{TOMATO_ID}_harvest")
    assert hass.states.get(harvest).state == "2027-06-23"

    plantings = _entity_id(hass, "sensor", f"{GREENHOUSE_ID}_plantings")
    assert hass.states.get(plantings).state == "1"
    assert hass.states.get(plantings).attributes["plantings"] == ["Tomato"]
    assert (
        hass.states.get(_entity_id(hass, "sensor", f"{PLOT_ID}_plantings")).state == "0"
    )

    sow_now = hass.states.get(_entity_id(hass, "sensor", f"{GREENHOUSE_ID}_sow_now"))
    assert "Tomato" in sow_now.attributes["sow_indoors"]
    assert int(sow_now.state) > 0

    devices = {
        device.name: device
        for device in dr.async_entries_for_config_entry(
            dr.async_get(hass), garden_entry.entry_id
        )
    }
    assert set(devices) == {"Jardin", "Serre", "Potager", "Tomato"}
    assert devices["Tomato"].via_device_id == devices["Serre"].id


async def test_complete_task_moves_stage(
    hass: HomeAssistant, garden_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Ticking "sow" marks the planting as sown today."""
    freezer.move_to(SOWING_DAY)
    await _setup(hass, garden_entry)
    todo = _entity_id(hass, "todo", f"{garden_entry.entry_id}_tasks")
    assert hass.states.get(todo).state == "1"

    items = await _todo_items(hass, todo)
    assert [item["summary"] for item in items] == ["Sow under cover: Tomato"]
    assert items[0]["due"] == "2027-02-20"
    assert items[0]["description"] == "Window: 2027-02-20 – 2027-03-06."

    await hass.services.async_call(
        "todo",
        "update_item",
        {"item": items[0]["uid"], "status": "completed"},
        target={"entity_id": todo},
        blocking=True,
    )
    await hass.async_block_till_done()

    stage = hass.states.get(_entity_id(hass, "select", f"{TOMATO_ID}_stage"))
    assert stage.state == "sown"
    assert stage.attributes["sown"] == "2027-02-20"
    # Transplanting (24 April) is beyond the horizon, the done task remains.
    assert hass.states.get(todo).state == "0"
    items = await _todo_items(hass, todo)
    assert [(item["summary"], item["status"]) for item in items] == [
        ("Sow under cover: Tomato", "completed")
    ]
    next_task = _entity_id(hass, "sensor", f"{TOMATO_ID}_next_task")
    assert hass.states.get(next_task).state == "Transplant: Tomato → Serre"


async def test_state_survives_reload(
    hass: HomeAssistant, garden_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Stages are stored."""
    freezer.move_to(SOWING_DAY)
    await _setup(hass, garden_entry)
    stage = _entity_id(hass, "select", f"{TOMATO_ID}_stage")
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": stage, "option": "transplanted"},
        blocking=True,
    )
    assert await hass.config_entries.async_reload(garden_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(stage).state == "transplanted"
    assert hass.states.get(stage).attributes["transplanted"] == "2027-02-20"


async def test_own_items_and_dismiss(
    hass: HomeAssistant, garden_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Own items can be added and ticked; generated tasks can be removed."""
    freezer.move_to(SOWING_DAY)
    await _setup(hass, garden_entry)
    todo = _entity_id(hass, "todo", f"{garden_entry.entry_id}_tasks")

    await hass.services.async_call(
        "todo",
        "add_item",
        {"item": "Buy compost", "due_date": "2027-02-25"},
        target={"entity_id": todo},
        blocking=True,
    )
    assert hass.states.get(todo).state == "2"
    await hass.services.async_call(
        "todo",
        "update_item",
        {"item": "Buy compost", "status": "completed"},
        target={"entity_id": todo},
        blocking=True,
    )
    assert hass.states.get(todo).state == "1"

    await hass.services.async_call(
        "todo",
        "remove_item",
        {"item": "Sow under cover: Tomato"},
        target={"entity_id": todo},
        blocking=True,
    )
    summaries = [item["summary"] for item in await _todo_items(hass, todo)]
    assert summaries == ["Buy compost"]
    # Removing a task does not change the stage.
    assert hass.states.get(_entity_id(hass, "select", f"{TOMATO_ID}_stage")).state == (
        "planned"
    )


async def test_calendar(
    hass: HomeAssistant, garden_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Sowing, planting-out and harvest periods are calendar events."""
    freezer.move_to("2026-10-27 12:00:00+01:00")
    await _setup(hass, garden_entry)
    calendar = _entity_id(hass, "calendar", f"{garden_entry.entry_id}_calendar")

    state = hass.states.get(calendar)
    assert state.attributes["message"] == "Sowing: Tomato"
    assert state.attributes["start_time"] == "2027-02-20 00:00:00"

    result = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "start_date_time": "2027-01-01 00:00:00",
            "end_date_time": "2028-01-01 00:00:00",
        },
        target={"entity_id": calendar},
        blocking=True,
        return_response=True,
    )
    events = result[calendar]["events"]
    assert [(event["summary"], event["start"], event["end"]) for event in events] == [
        ("Sowing: Tomato", "2027-02-20", "2027-03-07"),
        ("Planting out: Tomato", "2027-04-24", "2027-05-09"),
        ("Harvest: Tomato", "2027-06-23", "2027-09-27"),
    ]
    assert events[0]["location"] == "Serre"


async def test_french(
    hass: HomeAssistant, garden_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Tasks are written in the language of Home Assistant."""
    hass.config.language = "fr"
    freezer.move_to(SOWING_DAY)
    await _setup(hass, garden_entry)
    todo = _entity_id(hass, "todo", f"{garden_entry.entry_id}_tasks")
    items = await _todo_items(hass, todo)
    assert items[0]["summary"] == "Semer sous abri : Tomate"
    assert items[0]["description"] == "Période : du 20/02/2027 au 06/03/2027."
