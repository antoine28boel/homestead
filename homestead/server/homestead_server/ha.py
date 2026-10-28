"""Talks to Home Assistant: its settings, its weather, and announcing the app."""

from __future__ import annotations

from datetime import date
import logging
from typing import Any

import httpx

from .climate import Night
from .config import Settings

_LOGGER = logging.getLogger(__name__)

SUPERVISOR = "http://supervisor"
DISCOVERY_SERVICE = "homestead"

# Used when Home Assistant cannot be reached, or the server runs alone.
FALLBACK_CONFIG: dict[str, Any] = {
    "language": "en",
    "time_zone": "UTC",
    "latitude": 45.0,
    "longitude": None,
    "elevation": None,
    "location_name": "Homestead",
}


def _core(settings: Settings) -> tuple[str, str] | None:
    """Base URL of Home Assistant's API and the token for it."""
    if settings.supervisor_token:
        return f"{SUPERVISOR}/core/api", settings.supervisor_token
    if settings.ha_url and settings.ha_token:
        return f"{settings.ha_url}/api", settings.ha_token
    return None


def connected(settings: Settings) -> bool:
    """Whether Home Assistant can be asked."""
    return _core(settings) is not None


def _fallback(settings: Settings) -> dict[str, Any]:
    config = dict(FALLBACK_CONFIG)
    if settings.language:
        config["language"] = settings.language
    if settings.time_zone:
        config["time_zone"] = settings.time_zone
    return config


async def fetch_config(settings: Settings) -> dict[str, Any]:
    """Language, time zone and latitude of Home Assistant."""
    fallback = _fallback(settings)
    core = _core(settings)
    if core is None:
        return fallback
    url, token = core
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{url}/config", headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as err:
        _LOGGER.warning("Cannot read Home Assistant's settings: %s", err)
        return fallback
    return fallback | {
        key: data[key] for key in FALLBACK_CONFIG if data.get(key) is not None
    }


async def announce(settings: Settings, api_token: str) -> bool:
    """Offer the companion integration to Home Assistant (app mode only)."""
    if not settings.supervisor_token:
        return False
    headers = {"Authorization": f"Bearer {settings.supervisor_token}"}
    try:
        async with httpx.AsyncClient(timeout=10, headers=headers) as client:
            info = await client.get(f"{SUPERVISOR}/addons/self/info")
            info.raise_for_status()
            host = info.json()["data"]["hostname"]
            response = await client.post(
                f"{SUPERVISOR}/discovery",
                json={
                    "service": DISCOVERY_SERVICE,
                    "config": {
                        "host": host,
                        "port": settings.port,
                        "token": api_token,
                    },
                },
            )
            response.raise_for_status()
    except (httpx.HTTPError, KeyError, ValueError) as err:
        _LOGGER.warning("Cannot announce Homestead to Home Assistant: %s", err)
        return False
    return True


async def weather_entities(settings: Settings) -> list[dict[str, str]]:
    """Weather entities of Home Assistant, with their names."""
    core = _core(settings)
    if core is None:
        return []
    url, token = core
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{url}/states", headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            states = response.json()
    except (httpx.HTTPError, ValueError) as err:
        _LOGGER.warning("Cannot list weather entities: %s", err)
        return []
    return sorted(
        (
            {
                "entity_id": state["entity_id"],
                "name": state["attributes"].get("friendly_name") or state["entity_id"],
            }
            for state in states
            if state["entity_id"].startswith("weather.")
        ),
        key=lambda entity: entity["name"],
    )


async def fetch_forecast(settings: Settings, entity_id: str) -> list[Night] | None:
    """Daily minimums forecast by a weather entity; None when unavailable."""
    core = _core(settings)
    if core is None:
        return None
    url, token = core
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{url}/services/weather/get_forecasts?return_response",
                headers={"Authorization": f"Bearer {token}"},
                json={"entity_id": entity_id, "type": "daily"},
            )
            response.raise_for_status()
            days = response.json()["service_response"][entity_id]["forecast"]
        return [
            Night(date.fromisoformat(day["datetime"][:10]), float(day["templow"]))
            for day in days
            if day.get("templow") is not None
        ]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as err:
        _LOGGER.warning("Cannot read the forecast of %s: %s", entity_id, err)
        return None
