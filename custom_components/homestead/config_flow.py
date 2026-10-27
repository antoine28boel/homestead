"""Config flow for the Homestead integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    DateSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import dt as dt_util

from .const import (
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
    CONF_START,
    CONF_VARIETY,
    CONF_WINDOW,
    DEFAULT_FIRST_FROST_NORTH,
    DEFAULT_FIRST_FROST_SOUTH,
    DEFAULT_FROST_SHIFT,
    DEFAULT_LAST_FROST_NORTH,
    DEFAULT_LAST_FROST_SOUTH,
    DOMAIN,
    SPACE_BED,
    SUBENTRY_PLANTING,
    SUBENTRY_SPACE,
)
from .garden import planting_name
from .models import MonthDay
from .planner import next_season, window_period

if TYPE_CHECKING:
    from .garden import Garden


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

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Spaces and plantings are added from the garden's page."""
        return {
            SUBENTRY_SPACE: SpaceSubentryFlow,
            SUBENTRY_PLANTING: PlantingSubentryFlow,
        }


class HomesteadOptionsFlow(OptionsFlow):
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


def _space_schema(defaults: dict[str, Any]) -> vol.Schema:
    def suggested(key: str) -> dict[str, Any]:
        value = defaults.get(key)
        return {} if value is None else {"suggested_value": value}

    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): (
                TextSelector()
            ),
            vol.Required(
                CONF_SPACE_TYPE, default=defaults.get(CONF_SPACE_TYPE, SPACE_BED)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=list(DEFAULT_FROST_SHIFT),
                    translation_key=CONF_SPACE_TYPE,
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(CONF_FROST_SHIFT, description=suggested(CONF_FROST_SHIFT)): (
                NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=12, step=1, mode=NumberSelectorMode.BOX
                    )
                )
            ),
            vol.Optional(CONF_AREA, description=suggested(CONF_AREA)): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=100000, step=0.1, mode=NumberSelectorMode.BOX
                )
            ),
        }
    )


class SpaceSubentryFlow(ConfigSubentryFlow):
    """Add or change a bed, a greenhouse…"""

    def _taken(self, name: str, own_id: str | None = None) -> bool:
        return any(
            subentry.subentry_type == SUBENTRY_SPACE
            and subentry.subentry_id != own_id
            and subentry.data[CONF_NAME].casefold() == name.casefold()
            for subentry in self._get_entry().subentries.values()
        )

    @staticmethod
    def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
        shift = user_input.get(CONF_FROST_SHIFT)
        return {
            CONF_NAME: user_input[CONF_NAME].strip(),
            CONF_SPACE_TYPE: user_input[CONF_SPACE_TYPE],
            CONF_FROST_SHIFT: int(shift) if shift is not None else None,
            CONF_AREA: user_input.get(CONF_AREA),
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Describe a new space."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = self._clean(user_input)
            if self._taken(data[CONF_NAME]):
                errors[CONF_NAME] = "name_taken"
            else:
                return self.async_create_entry(title=data[CONF_NAME], data=data)
        return self.async_show_form(
            step_id="user", data_schema=_space_schema(user_input or {}), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change a space."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = self._clean(user_input)
            if self._taken(data[CONF_NAME], subentry.subentry_id):
                errors[CONF_NAME] = "name_taken"
            else:
                return self.async_update_and_abort(
                    self._get_entry(), subentry, title=data[CONF_NAME], data=data
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_space_schema(user_input or dict(subentry.data)),
            errors=errors,
        )


class PlantingSubentryFlow(ConfigSubentryFlow):
    """Add a crop to a space, for one season."""

    def __init__(self) -> None:
        """Remember the choices of the first step."""
        self._first: dict[str, Any] = {}

    def _garden(self) -> Garden | None:
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return None
        return entry.runtime_data

    def _space_options(self, garden: Garden) -> list[SelectOptionDict]:
        return [
            SelectOptionDict(value=space.id, label=space.name)
            for space in sorted(garden.spaces.values(), key=lambda space: space.name)
        ]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose the space and the species."""
        if (garden := self._garden()) is None:
            return self.async_abort(reason="not_loaded")
        if not garden.spaces:
            return self.async_abort(reason="no_spaces")

        if user_input is not None:
            self._first = user_input
            return await self.async_step_details()

        language = garden.texts.language
        species_options = sorted(
            (
                SelectOptionDict(value=species.id, label=species.name(language))
                for species in garden.catalog.values()
            ),
            key=lambda option: option["label"].casefold(),
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SPACE): SelectSelector(
                    SelectSelectorConfig(
                        options=self._space_options(garden),
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_SPECIES): SelectSelector(
                    SelectSelectorConfig(
                        options=species_options, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    def _start_options(self, garden: Garden) -> dict[str, tuple[str, int, int, str]]:
        """Each way and window to start the crop, with its next season."""
        species = garden.catalog[self._first[CONF_SPECIES]]
        space = garden.spaces[self._first[CONF_SPACE]]
        today = garden.today()
        options: dict[str, tuple[str, int, int, str]] = {}
        for method in species.methods:
            for index, window in enumerate(species.windows(method)):
                season = next_season(window, garden.climate, space.frost_shift, today)
                start, end = window_period(
                    window, garden.climate, season, space.frost_shift
                )
                label = garden.texts(
                    f"choice_{method}",
                    start=garden.texts.date(start),
                    end=garden.texts.date(end),
                )
                options[f"{method}:{index}"] = (method, index, season, label)
        return options

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose how and when to start it, and the variety."""
        garden = self._garden()
        assert garden is not None
        options = self._start_options(garden)

        if user_input is not None:
            method, window, season, _label = options[user_input[CONF_START]]
            species = garden.catalog[self._first[CONF_SPECIES]]
            variety = (user_input.get(CONF_VARIETY) or "").strip()
            quantity = user_input.get(CONF_QUANTITY)
            return self.async_create_entry(
                title=planting_name(species, variety, garden.texts.language),
                data={
                    CONF_SPACE: self._first[CONF_SPACE],
                    CONF_SPECIES: species.id,
                    CONF_VARIETY: variety,
                    CONF_METHOD: method,
                    CONF_WINDOW: window,
                    CONF_SEASON: season,
                    CONF_QUANTITY: int(quantity) if quantity else None,
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_START, default=next(iter(options))): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=key, label=option[3])
                            for key, option in options.items()
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(CONF_VARIETY): TextSelector(),
                vol.Optional(CONF_QUANTITY): NumberSelector(
                    NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        species = garden.catalog[self._first[CONF_SPECIES]]
        return self.async_show_form(
            step_id="details",
            data_schema=schema,
            description_placeholders={
                "species": species.name(garden.texts.language),
                "space": garden.spaces[self._first[CONF_SPACE]].name,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change the space, the variety or the quantity."""
        if (garden := self._garden()) is None:
            return self.async_abort(reason="not_loaded")
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            species = garden.catalog[subentry.data[CONF_SPECIES]]
            variety = (user_input.get(CONF_VARIETY) or "").strip()
            quantity = user_input.get(CONF_QUANTITY)
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=planting_name(species, variety, garden.texts.language),
                data_updates={
                    CONF_SPACE: user_input[CONF_SPACE],
                    CONF_VARIETY: variety,
                    CONF_QUANTITY: int(quantity) if quantity else None,
                },
            )

        data = subentry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_SPACE, default=data[CONF_SPACE]): SelectSelector(
                    SelectSelectorConfig(
                        options=self._space_options(garden),
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_VARIETY,
                    description={"suggested_value": data.get(CONF_VARIETY) or None},
                ): TextSelector(),
                vol.Optional(
                    CONF_QUANTITY,
                    description={"suggested_value": data.get(CONF_QUANTITY)},
                ): NumberSelector(
                    NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema)
