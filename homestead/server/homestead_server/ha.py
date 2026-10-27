"""Talks to Home Assistant: its settings, and announcing the app to it."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Settings

_LOGGER = logging.getLogger(__name__)

SUPERVISOR = "http://supervisor"
DISCOVERY_SERVICE = "homestead"

# Used when Home Assistant cannot be reached, or the server runs alone.
FALLBACK_CONFIG: dict[str, Any] = {
    "language": "en",
    "time_zone": "UTC",
    "latitude": 45.0,
    "location_name": "Homestead",
}


def _core(settings: Settings) -> tuple[str, str] | None:
    """Base URL of Home Assistant's API and the token for it."""
    if settings.supervisor_token:
        return f"{SUPERVISOR}/core/api", settings.supervisor_token
    if settings.ha_url and settings.ha_token:
        return f"{settings.ha_url}/api", settings.ha_token
    return None


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
