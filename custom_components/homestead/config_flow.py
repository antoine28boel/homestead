"""Config flow for the Homestead integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import DateSelector, TextSelector
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FIRST_FROST,
    CONF_LAST_FROST,
    DEFAULT_FIRST_FROST_NORTH,
    DEFAULT_FIRST_FROST_SOUTH,
    DEFAULT_LAST_FROST_NORTH,
    DEFAULT_LAST_FROST_SOUTH,
    DOMAIN,
)
from .models import MonthDay


def _default_frost_dates(hass: HomeAssistant) -> dict[str, str]:
    """Pre-fill the frost dates according to the hemisphere of the home."""
    if hass.config.latitude < 0:
        return {
            CONF_LAST_FROST: DEFAULT_LAST_FROST_SOUTH,
            CONF_FIRST_FROST: DEFAULT_FIRST_FROST_SOUTH,
        }
    return {
        CONF_LAST_FROST: DEFAULT_LAST_FROST_NORTH,
        CONF_FIRST_FROST: DEFAULT_FIRST_FROST_NORTH,
    }


def _climate_schema(values: dict[str, str]) -> dict[vol.Marker, Any]:
    """Frost date fields, shown as dates of the current year."""
    year = dt_util.now().year
    return {
        vol.Required(
            key, default=MonthDay.parse(values[key]).in_year(year).isoformat()
        ): DateSelector()
        for key in (CONF_LAST_FROST, CONF_FIRST_FROST)
    }


def _validate_climate(
    user_input: dict[str, Any], errors: dict[str, str]
) -> dict[str, str]:
    """Convert the chosen dates to "MM-DD" and check that they differ."""
    last_frost = MonthDay.parse(user_input[CONF_LAST_FROST])
    first_frost = MonthDay.parse(user_input[CONF_FIRST_FROST])
    if last_frost == first_frost:
        errors["base"] = "same_frost_dates"
    return {CONF_LAST_FROST: str(last_frost), CONF_FIRST_FROST: str(first_frost)}


class HomesteadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a garden. Several gardens can coexist (a second home…)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Name the garden and give its frost dates."""
        errors: dict[str, str] = {}
        values = _default_frost_dates(self.hass)

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            self._async_abort_entries_match({CONF_NAME: name})
            values = _validate_climate(user_input, errors)
            if not errors:
                return self.async_create_entry(
                    title=name, data={CONF_NAME: name}, options=values
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=(user_input or {}).get(CONF_NAME, "")
                ): TextSelector(),
                **_climate_schema(values),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HomesteadOptionsFlow:
        """Return the options flow."""
        return HomesteadOptionsFlow()


class HomesteadOptionsFlow(OptionsFlowWithReload):
    """Change the frost dates of a garden."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the frost dates."""
        errors: dict[str, str] = {}
        values = dict(self.config_entry.options)

        if user_input is not None:
            values = _validate_climate(user_input, errors)
            if not errors:
                return self.async_create_entry(data=values)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(_climate_schema(values)),
            errors=errors,
        )
