"""Tests for setting up Homestead."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homestead.api import HomesteadAuthError, HomesteadConnectionError
from custom_components.homestead.const import DOMAIN
from homeassistant.config_entries import SOURCE_HASSIO, SOURCE_USER
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .conftest import INSTANCE_ID, TOKEN, URL

DISCOVERY = HassioServiceInfo(
    config={"host": "a0d7b954-homestead", "port": 8099, "token": "app-token"},
    name="Homestead",
    slug="a0d7b954_homestead",
    uuid="1234",
)


async def test_user_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """A stand-alone server is added by address and token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: f"{URL}/", CONF_TOKEN: TOKEN}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jardin"
    assert result["data"] == {CONF_URL: URL, CONF_TOKEN: TOKEN}
    assert result["result"].unique_id == INSTANCE_ID


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (HomesteadAuthError(), "invalid_auth"),
        (HomesteadConnectionError("down"), "cannot_connect"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, mock_client: MagicMock, error: Exception, reason: str
) -> None:
    """Errors are shown, and the form can be sent again."""
    mock_client.info.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_TOKEN: TOKEN}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_client.info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_TOKEN: TOKEN}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_same_server(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The same server at a new address updates the existing entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "http://10.0.0.5:8099", CONF_TOKEN: TOKEN}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_URL] == "http://10.0.0.5:8099"


async def test_hassio_discovery(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """The app announces itself; the user confirms."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"name": "Jardin"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_URL: "http://a0d7b954-homestead:8099",
        CONF_TOKEN: "app-token",
    }


async def test_hassio_discovery_updates_entry(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A known server announcing itself again updates its address and token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {
        CONF_URL: "http://a0d7b954-homestead:8099",
        CONF_TOKEN: "app-token",
    }


async def test_hassio_discovery_unreachable(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """An app that cannot be reached is not offered."""
    mock_client.info.side_effect = HomesteadConnectionError("down")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_reauth(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A refused token can be replaced."""
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    mock_client.info.side_effect = HomesteadAuthError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN] == "new-token"
    await hass.async_block_till_done()


async def test_reauth_other_server(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A token of another server is refused."""
    mock_client.info.return_value = {"instance_id": "other", "garden": "Autre"}
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_server"
    assert mock_config_entry.data[CONF_TOKEN] == TOKEN
