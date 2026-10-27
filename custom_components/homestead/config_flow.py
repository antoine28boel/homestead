"""Connect Home Assistant to a Homestead server."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import HomesteadAuthError, HomesteadClient, HomesteadError
from .const import DOMAIN

TOKEN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class HomesteadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Found by the Supervisor when the app runs, or set up by hand."""

    VERSION = 1

    def __init__(self) -> None:
        """Nothing found yet."""
        self._url: str | None = None
        self._token: str | None = None
        self._garden: str | None = None

    async def _connect(self, url: str, token: str) -> dict[str, Any]:
        client = HomesteadClient(async_get_clientsession(self.hass), url, token)
        return await client.info()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Address and token of a stand-alone server."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            token = user_input[CONF_TOKEN]
            try:
                info = await self._connect(url, token)
            except HomesteadAuthError:
                errors["base"] = "invalid_auth"
            except HomesteadError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info["instance_id"])
                self._abort_if_unique_id_configured(
                    updates={CONF_URL: url, CONF_TOKEN: token}
                )
                return self.async_create_entry(
                    title=info["garden"], data={CONF_URL: url, CONF_TOKEN: token}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_URL): str,
                        vol.Required(CONF_TOKEN): TOKEN_SELECTOR,
                    }
                ),
                user_input or {CONF_URL: "http://"},
            ),
            errors=errors,
        )

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """The Homestead app announced itself."""
        config = discovery_info.config
        url = f"http://{config['host']}:{config['port']}"
        token = config["token"]
        try:
            info = await self._connect(url, token)
        except HomesteadError:
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(info["instance_id"])
        self._abort_if_unique_id_configured(updates={CONF_URL: url, CONF_TOKEN: token})
        self._url, self._token, self._garden = url, token, info["garden"]
        self.context["title_placeholders"] = {"name": info["garden"]}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask before adding the discovered garden."""
        assert self._url and self._token and self._garden
        if user_input is None:
            return self.async_show_form(
                step_id="hassio_confirm",
                description_placeholders={"name": self._garden},
            )
        return self.async_create_entry(
            title=self._garden, data={CONF_URL: self._url, CONF_TOKEN: self._token}
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """The server refused the token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the new token."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await self._connect(entry.data[CONF_URL], user_input[CONF_TOKEN])
            except HomesteadAuthError:
                errors["base"] = "invalid_auth"
            except HomesteadError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info["instance_id"])
                self._abort_if_unique_id_mismatch(reason="wrong_server")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): TOKEN_SELECTOR}),
            description_placeholders={"url": entry.data[CONF_URL]},
            errors=errors,
        )
