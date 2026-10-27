"""Fixtures for the Homestead tests."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homestead.const import CONF_FIRST_FROST, CONF_LAST_FROST, DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A garden with Belgian frost dates."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Jardin",
        data={CONF_NAME: "Jardin"},
        options={CONF_LAST_FROST: "05-15", CONF_FIRST_FROST: "10-20"},
    )
    entry.add_to_hass(hass)
    return entry
