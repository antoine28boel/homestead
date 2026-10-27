"""Fixtures for the Homestead tests."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homestead.const import (
    CONF_AREA,
    CONF_FIRST_FROST,
    CONF_FROST_SHIFT,
    CONF_LAST_FROST,
    CONF_METHOD,
    CONF_QUANTITY,
    CONF_SEASON,
    CONF_SPACE,
    CONF_SPACE_TYPE,
    CONF_SPECIES,
    CONF_VARIETY,
    CONF_WINDOW,
    DOMAIN,
    SUBENTRY_PLANTING,
    SUBENTRY_SPACE,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

GREENHOUSE_ID = "01GREENHOUSE"
PLOT_ID = "01PLOT"
TOMATO_ID = "01TOMATO"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture(autouse=True)
async def brussels(hass: HomeAssistant) -> None:
    """Run the tests in a Belgian garden."""
    await hass.config.async_set_time_zone("Europe/Brussels")


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A garden with Belgian frost dates and nothing in it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Jardin",
        data={CONF_NAME: "Jardin"},
        options={CONF_LAST_FROST: "05-15", CONF_FIRST_FROST: "10-20"},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def garden_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A greenhouse and a vegetable plot, with tomatoes planned for 2027."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Jardin",
        data={CONF_NAME: "Jardin"},
        options={CONF_LAST_FROST: "05-15", CONF_FIRST_FROST: "10-20"},
        subentries_data=[
            ConfigSubentryData(
                subentry_id=GREENHOUSE_ID,
                subentry_type=SUBENTRY_SPACE,
                title="Serre",
                unique_id=None,
                data={
                    CONF_NAME: "Serre",
                    CONF_SPACE_TYPE: "greenhouse",
                    CONF_FROST_SHIFT: None,
                    CONF_AREA: None,
                },
            ),
            ConfigSubentryData(
                subentry_id=PLOT_ID,
                subentry_type=SUBENTRY_SPACE,
                title="Potager",
                unique_id=None,
                data={
                    CONF_NAME: "Potager",
                    CONF_SPACE_TYPE: "bed",
                    CONF_FROST_SHIFT: None,
                    CONF_AREA: 32.0,
                },
            ),
            ConfigSubentryData(
                subentry_id=TOMATO_ID,
                subentry_type=SUBENTRY_PLANTING,
                title="Tomato",
                unique_id=None,
                data={
                    CONF_SPACE: GREENHOUSE_ID,
                    CONF_SPECIES: "tomato",
                    CONF_VARIETY: "",
                    CONF_METHOD: "sow_indoors",
                    CONF_WINDOW: 0,
                    CONF_SEASON: 2027,
                    CONF_QUANTITY: 6,
                },
            ),
        ],
    )
    entry.add_to_hass(hass)
    return entry
