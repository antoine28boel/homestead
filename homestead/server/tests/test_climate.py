"""Tests for frost dates and frost in the forecast."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from homestead_server import ha
from homestead_server.climate import Night, frost_dates, frosty_nights, harm_limit
from homestead_server.config import Settings
from homestead_server.models import MonthDay
from homestead_server.texts import Texts


def _years(
    lasts: list[date | None], firsts: list[date | None]
) -> list[tuple[date, float | None]]:
    """Daily minimums: mild every day but the frosts given."""
    frosts = {day for day in lasts + firsts if day}
    days = []
    for year in sorted({day.year for day in frosts} | {2000 + len(lasts) - 1}):
        day = date(year, 1, 1)
        while day.year == year:
            days.append((day, -1.0 if day in frosts else 5.0))
            day += timedelta(days=1)
    return days


def test_frost_dates_one_year_in_ten() -> None:
    """The safe dates leave one year in ten on the wrong side."""
    lasts = [date(2000 + n, 4, 1 + n) for n in range(10)]
    firsts = [date(2000 + n, 11, 20 - n) for n in range(10)]
    found = frost_dates(_years(lasts, firsts))
    assert found is not None
    assert found.years == 10
    assert found.last == MonthDay(4, 9)
    assert found.first == MonthDay(11, 12)
    assert found.last_median == MonthDay(4, 5)
    assert found.first_median == MonthDay(11, 16)


def test_frost_dates_south() -> None:
    """South of the equator, spring frosts fall in the second half."""
    lasts = [date(2000 + n, 9, 10) for n in range(4)]
    firsts = [date(2000 + n, 5, 20) for n in range(4)]
    found = frost_dates(_years(lasts, firsts), south=True)
    assert found is not None
    assert (found.last, found.first) == (MonthDay(9, 10), MonthDay(5, 20))


def test_frost_free() -> None:
    """Where most years have no frost, there are no dates to give."""
    lasts: list[date | None] = [date(2000, 2, 1), None, None, None]
    assert frost_dates(_years(lasts, [date(2000, 12, 1)])) is None


def test_harm_and_nights() -> None:
    """Tender crops fear a light frost; a greenhouse buys a few degrees."""
    assert harm_limit("tender", greenhouse=False) == 1.0
    assert harm_limit("half_hardy", greenhouse=True) == -5.0
    assert harm_limit("hardy", greenhouse=False) is None
    today = date(2027, 4, 20)
    forecast = [
        Night(date(2027, 4, 19), -3.0),
        Night(date(2027, 4, 21), 0.5),
        Night(date(2027, 4, 23), 4.0),
        Night(date(2027, 4, 28), -1.0),
    ]
    assert frosty_nights(forecast, 1.0, today) == [forecast[1]]


def test_temperature_text() -> None:
    """Temperatures are written the way the language does."""
    assert Texts("fr").temperature(-2.5) == "−2,5"
    assert Texts("en").temperature(3.0) == "3"


def test_fetch_forecast(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Daily lows come from Home Assistant's weather.get_forecasts."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content
        return httpx.Response(
            200,
            json={
                "changed_states": [],
                "service_response": {
                    "weather.home": {
                        "forecast": [
                            {"datetime": "2027-04-20T00:00:00+02:00", "templow": -2},
                            {"datetime": "2027-04-21", "templow": None},
                        ]
                    }
                },
            },
        )

    client = httpx.AsyncClient
    monkeypatch.setattr(
        ha.httpx,
        "AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs),
    )
    settings = Settings(tmp_path, ha_url="http://ha.test", ha_token="secret")
    nights = asyncio.run(ha.fetch_forecast(settings, "weather.home"))
    assert nights == [Night(date(2027, 4, 20), -2.0)]
    assert seen["url"].endswith("/api/services/weather/get_forecasts?return_response")
    assert b'"type":"daily"' in seen["body"].replace(b" ", b"")
    assert asyncio.run(ha.fetch_forecast(Settings(tmp_path), "weather.home")) is None
