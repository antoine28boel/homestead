"""Tests for adding spaces and plantings from the garden's page."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homestead.const import (
    CONF_AREA,
    CONF_FROST_SHIFT,
    CONF_METHOD,
    CONF_QUANTITY,
    CONF_SEASON,
    CONF_SPACE,
    CONF_SPACE_TYPE,
    CONF_SPECIES,
    CONF_START,
    CONF_VARIETY,
    CONF_WINDOW,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .conftest import GREENHOUSE_ID, PLOT_ID, TOMATO_ID


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_add_space(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A raised bed gets its sensors after the garden reloads."""
    await _setup(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "space"), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: " Carré ", CONF_SPACE_TYPE: "raised_bed", CONF_AREA: 1.2},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    (subentry,) = mock_config_entry.subentries.values()
    assert subentry.title == "Carré"
    assert subentry.data == {
        CONF_NAME: "Carré",
        CONF_SPACE_TYPE: "raised_bed",
        CONF_FROST_SHIFT: None,
        CONF_AREA: 1.2,
    }
    garden = mock_config_entry.runtime_data
    assert garden.spaces[subentry.subentry_id].frost_shift == 1
    assert er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{subentry.subentry_id}_sow_now"
    )


async def test_space_name_taken(
    hass: HomeAssistant, garden_entry: MockConfigEntry
) -> None:
    """Two spaces cannot share a name."""
    await _setup(hass, garden_entry)
    result = await hass.config_entries.subentries.async_init(
        (garden_entry.entry_id, "space"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "serre", CONF_SPACE_TYPE: "greenhouse"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_NAME: "name_taken"}


async def test_reconfigure_space(
    hass: HomeAssistant, garden_entry: MockConfigEntry
) -> None:
    """A space can be renamed and its frost shift set."""
    await _setup(hass, garden_entry)
    result = await hass.config_entries.subentries.async_init(
        (garden_entry.entry_id, "space"),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": PLOT_ID},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: "Grand potager", CONF_SPACE_TYPE: "bed", CONF_FROST_SHIFT: 2},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert garden_entry.subentries[PLOT_ID].title == "Grand potager"
    assert garden_entry.runtime_data.spaces[PLOT_ID].frost_shift == 2


async def test_planting_needs_a_space(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Spaces come first."""
    await _setup(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "planting"), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_spaces"


async def test_add_planting(
    hass: HomeAssistant, garden_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """At the end of October, autumn garlic is for this season."""
    freezer.move_to("2026-10-27 12:00:00+01:00")
    await _setup(hass, garden_entry)

    result = await hass.config_entries.subentries.async_init(
        (garden_entry.entry_id, "planting"), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_SPACE: PLOT_ID, CONF_SPECIES: "garlic"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "details"
    options = result["data_schema"].schema[CONF_START].config["options"]
    assert options == [
        {"value": "plant:0", "label": "Plant out, 2026-10-20 – 2026-11-24"},
        {"value": "plant:1", "label": "Plant out, 2027-03-06 – 2027-04-03"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_START: "plant:0", CONF_VARIETY: " Messidrome ", CONF_QUANTITY: 40},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    garlic = next(
        subentry
        for subentry in garden_entry.subentries.values()
        if subentry.data.get(CONF_SPECIES) == "garlic"
    )
    assert garlic.title == "Garlic Messidrome"
    assert garlic.data == {
        CONF_SPACE: PLOT_ID,
        CONF_SPECIES: "garlic",
        CONF_VARIETY: "Messidrome",
        CONF_METHOD: "plant",
        CONF_WINDOW: 0,
        CONF_SEASON: 2026,
        CONF_QUANTITY: 40,
    }
    # Planting garlic is due now, so it is in the to-do list.
    tasks = garden_entry.runtime_data.tasks()
    assert [task.summary for task in tasks] == [
        "Plant out: Garlic Messidrome (Potager)"
    ]


async def test_reconfigure_planting(
    hass: HomeAssistant, garden_entry: MockConfigEntry
) -> None:
    """A planting can move to another space and get a variety."""
    await _setup(hass, garden_entry)
    result = await hass.config_entries.subentries.async_init(
        (garden_entry.entry_id, "planting"),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": TOMATO_ID},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_SPACE: PLOT_ID, CONF_VARIETY: "Moneymaker"}
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    subentry = garden_entry.subentries[TOMATO_ID]
    assert subentry.title == "Tomato Moneymaker"
    assert subentry.data[CONF_SPACE] == PLOT_ID
    assert subentry.data[CONF_SEASON] == 2027
    assert garden_entry.runtime_data.plantings[TOMATO_ID].space.id == PLOT_ID
    assert GREENHOUSE_ID in garden_entry.runtime_data.spaces


async def test_remove_planting(
    hass: HomeAssistant, garden_entry: MockConfigEntry
) -> None:
    """Removing a planting removes its entities."""
    await _setup(hass, garden_entry)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("select", DOMAIN, f"{TOMATO_ID}_stage")

    hass.config_entries.async_remove_subentry(garden_entry, TOMATO_ID)
    await hass.async_block_till_done()
    assert not registry.async_get_entity_id("select", DOMAIN, f"{TOMATO_ID}_stage")
    assert garden_entry.runtime_data.plantings == {}
