"""Fixtures for the Homestead integration tests."""

from __future__ import annotations

from collections.abc import Generator
import copy
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homestead.const import DOMAIN
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant

INSTANCE_ID = "4f1c0a7e"
URL = "http://homestead.local:8099"
TOKEN = "secret-token"

INFO = {
    "version": "0.3.0",
    "instance_id": INSTANCE_ID,
    "app_mode": False,
    "language": "fr",
    "garden": "Jardin",
}

TOMATO = {
    "id": "tomato1",
    "season": 2027,
    "species": "tomato",
    "species_name": "Tomate",
    "variety": "Cœur de bœuf",
    "name": "Tomate Cœur de bœuf",
    "space_id": "plot",
    "space_name": "Potager",
    "method": "sow_indoors",
    "window": 0,
    "quantity": 6,
    "stage": "sown",
    "dates": {"sown": "2027-03-20"},
    "notes": "",
    "schedule": {
        "sow": ["2027-03-20", "2027-04-03"],
        "transplant": ["2027-05-22", "2027-06-05"],
        "harvest": ["2027-07-20", "2027-09-30"],
    },
    "next_task": {
        "uid": "tomato1.transplant",
        "summary": "Repiquer : Tomate Cœur de bœuf → Potager",
        "due": "2027-05-22",
        "description": None,
        "completed": None,
        "planting_id": "tomato1",
        "action": "transplanted",
        "generated": True,
    },
    "harvested": {"kg": 1.5},
}

SUMMARY: dict[str, Any] = {
    "version": "0.3.0",
    "instance_id": INSTANCE_ID,
    "today": "2027-03-20",
    "garden": {"name": "Jardin", "last_frost": "05-15", "first_frost": "10-15"},
    "spaces": [
        {"id": "greenhouse", "name": "Serre", "type": "greenhouse", "archived": False},
        {"id": "plot", "name": "Potager", "type": "bed", "archived": False},
    ],
    "plantings": [TOMATO],
    "tasks": [
        {
            "uid": "tomato1.task.stake",
            "summary": "Tuteurer : Tomate Cœur de bœuf (Potager)",
            "due": "2027-03-25",
            "description": None,
            "completed": None,
            "planting_id": "tomato1",
            "action": None,
            "generated": True,
        },
        {
            "uid": "own1",
            "summary": "Acheter du terreau",
            "due": None,
            "description": "Sacs de 40 L",
            "completed": None,
            "planting_id": None,
            "action": None,
            "generated": False,
        },
        {
            "uid": "tomato1.sow",
            "summary": "Semer sous abri : Tomate Cœur de bœuf",
            "due": None,
            "description": None,
            "completed": "2027-03-20T08:00:00+00:00",
            "planting_id": "tomato1",
            "action": None,
            "generated": True,
        },
    ],
    "events": [
        {
            "uid": "tomato1.sow",
            "summary": "Semis : Tomate Cœur de bœuf",
            "start": "2027-03-20",
            "end": "2027-04-04",
            "location": "Potager",
            "planting_id": "tomato1",
            "kind": "sow",
        }
    ],
    "sow_now": {
        "plot": {"sow_indoors": [{"id": "tomato", "name": "Tomate"}]},
        "greenhouse": {},
    },
    "stages": ["planned", "sown", "transplanted", "growing", "harvesting", "finished"],
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def summary() -> dict[str, Any]:
    """A fresh copy of the server's summary."""
    return copy.deepcopy(SUMMARY)


@pytest.fixture
def mock_client(summary: dict[str, Any]) -> Generator[MagicMock]:
    """The server, as the integration's client sees it."""
    client = MagicMock()
    client.info = AsyncMock(return_value=dict(INFO))
    client.summary = AsyncMock(return_value=summary)
    client.listen = AsyncMock(return_value=None)
    for name in (
        "calendar",
        "set_stage",
        "create_task",
        "update_task",
        "delete_task",
        "add_journal",
        "add_harvest",
    ):
        setattr(client, name, AsyncMock(return_value=None))
    with (
        patch("custom_components.homestead.HomesteadClient", return_value=client),
        patch(
            "custom_components.homestead.config_flow.HomesteadClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A garden set up by hand."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Jardin",
        unique_id=INSTANCE_ID,
        data={CONF_URL: URL, CONF_TOKEN: TOKEN},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> MockConfigEntry:
    """The garden, set up."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
