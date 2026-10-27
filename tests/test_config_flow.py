"""Tests for the Homestead config and options flows."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homestead.const import CONF_FIRST_FROST, CONF_LAST_FROST, DOMAIN
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def _defaults(result) -> dict[str, str]:
    """Default values of a form, by field name."""
    return {
        str(key): key.default()
        for key in result["data_schema"].schema
        if callable(getattr(key, "default", None))
    }


async def test_user_flow(hass: HomeAssistant) -> None:
    """A garden is created with its frost dates stored as MM-DD."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: " Jardin ",
            CONF_LAST_FROST: "2026-05-13",
            CONF_FIRST_FROST: "2026-10-20",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jardin"
    assert result["data"] == {CONF_NAME: "Jardin"}
    assert result["options"] == {CONF_LAST_FROST: "05-13", CONF_FIRST_FROST: "10-20"}


async def test_defaults_northern_hemisphere(hass: HomeAssistant) -> None:
    """The form is pre-filled with northern frost dates."""
    hass.config.latitude = 50.4
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    defaults = _defaults(result)
    assert defaults[CONF_LAST_FROST].endswith("-05-15")
    assert defaults[CONF_FIRST_FROST].endswith("-10-15")


async def test_defaults_southern_hemisphere(hass: HomeAssistant) -> None:
    """South of the equator, spring frost comes in October."""
    hass.config.latitude = -33.9
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    defaults = _defaults(result)
    assert defaults[CONF_LAST_FROST].endswith("-10-15")
    assert defaults[CONF_FIRST_FROST].endswith("-04-15")


async def test_same_frost_dates(hass: HomeAssistant) -> None:
    """Identical dates are refused, and the form can then be corrected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Jardin",
            CONF_LAST_FROST: "2026-05-15",
            CONF_FIRST_FROST: "2027-05-15",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "same_frost_dates"}
    assert _defaults(result)[CONF_NAME] == "Jardin"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Jardin",
            CONF_LAST_FROST: "2026-05-15",
            CONF_FIRST_FROST: "2026-10-15",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_name(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Two gardens cannot have the same name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Jardin",
            CONF_LAST_FROST: "2026-05-15",
            CONF_FIRST_FROST: "2026-10-15",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_second_garden(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A second garden with another name is allowed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Maison de campagne",
            CONF_LAST_FROST: "2026-05-25",
            CONF_FIRST_FROST: "2026-10-01",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Frost dates can be changed, and the garden picks them up."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert _defaults(result)[CONF_LAST_FROST].endswith("-05-15")

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_LAST_FROST: "2026-05-01", CONF_FIRST_FROST: "2026-10-01"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert mock_config_entry.options == {
        CONF_LAST_FROST: "05-01",
        CONF_FIRST_FROST: "10-01",
    }
    assert str(mock_config_entry.runtime_data.climate.last_frost) == "05-01"


async def test_options_flow_same_dates(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The options flow refuses identical dates too."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_LAST_FROST: "2026-05-01", CONF_FIRST_FROST: "2026-05-01"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "same_frost_dates"}
