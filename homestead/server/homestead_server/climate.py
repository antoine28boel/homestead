"""Frost: average dates from past weather, and frost in the forecast."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
import math
from typing import Any

import httpx

from .models import MonthDay

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HISTORY_YEARS = 30
# A night at or below this, in the shelter two metres up, is a frost.
FROST_C = 0.0
# Frost dates gardeners can rely on: frost later in spring (or earlier in
# autumn) in only one year out of ten.
SAFE_SHARE = 0.9
# Coordinates sent to the weather archive are rounded to about 10 km.
COORDINATE_DECIMALS = 1

# Forecast minimum that harms a crop in the open, by frost tolerance.
# Hardy crops are left alone.
FROST_HARM_C = {"tender": 1.0, "half_hardy": -2.0}
# An unheated greenhouse keeps the night a few degrees warmer.
GREENHOUSE_GAIN_C = 3.0
FORECAST_DAYS = 7


class ClimateError(Exception):
    """The weather archive could not be read."""


@dataclass(frozen=True, slots=True)
class FrostDates:
    """Frost dates of a place, from its past weather."""

    last: MonthDay
    """Last frost of spring, later only one year out of ten."""
    first: MonthDay
    """First frost of autumn, earlier only one year out of ten."""
    last_median: MonthDay
    first_median: MonthDay
    years: int


@dataclass(frozen=True, slots=True)
class Night:
    """Forecast minimum of a day."""

    day: date
    low: float


def _day_of_year(day: date) -> int:
    # Counted in a common year, so that February 29 does not shift the rest.
    return date(
        2001, day.month, min(day.day, 28) if day.month == 2 else day.day
    ).toordinal()


def _month_day(ordinal: int) -> MonthDay:
    day = date.fromordinal(ordinal)
    return MonthDay(day.month, day.day)


def _rank(values: list[float], share: float) -> float:
    """The value that `share` of the values do not exceed."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]


def _rank_down(values: list[float], share: float) -> float:
    """The value that `share` of the values are not below."""
    return -_rank([-value for value in values], share)


def frost_dates(
    minimums: Iterable[tuple[date, float | None]], south: bool = False
) -> FrostDates | None:
    """Frost dates from daily minimums over whole years.

    Spring and autumn are the halves of the year around midsummer. A year
    without frost in spring counts as an early last frost, one without frost
    in autumn as a late first frost. None when most years have no frost.
    """
    last: dict[int, float] = {}
    first: dict[int, float] = {}
    years: set[int] = set()
    for day, low in minimums:
        years.add(day.year)
        if low is None or low > FROST_C:
            continue
        spring = day.month >= 7 if south else day.month <= 7
        ordinal = _day_of_year(day)
        if spring:
            last[day.year] = max(last.get(day.year, -math.inf), ordinal)
        else:
            first[day.year] = min(first.get(day.year, math.inf), ordinal)
    if len(last) * 2 <= len(years) or len(first) * 2 <= len(years):
        return None
    lasts = [last.get(year, -math.inf) for year in years]
    firsts = [first.get(year, math.inf) for year in years]
    return FrostDates(
        last=_month_day(int(_rank(lasts, SAFE_SHARE))),
        first=_month_day(int(_rank_down(firsts, SAFE_SHARE))),
        last_median=_month_day(int(_rank(lasts, 0.5))),
        first_median=_month_day(int(_rank_down(firsts, 0.5))),
        years=len(years),
    )


async def fetch_minimums(
    latitude: float,
    longitude: float,
    elevation: float | None,
    end_year: int,
    time_zone: str,
) -> list[tuple[date, float | None]]:
    """Daily minimums of the last whole years, from the Open-Meteo archive."""
    params: dict[str, Any] = {
        "latitude": round(latitude, COORDINATE_DECIMALS),
        "longitude": round(longitude, COORDINATE_DECIMALS),
        "start_date": f"{end_year - HISTORY_YEARS + 1}-01-01",
        "end_date": f"{end_year}-12-31",
        "daily": "temperature_2m_min",
        "timezone": time_zone,
    }
    # Home Assistant says 0 when the elevation was never set.
    if elevation:
        params["elevation"] = round(elevation)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(ARCHIVE_URL, params=params)
            response.raise_for_status()
            daily = response.json()["daily"]
        return [
            (date.fromisoformat(day), low)
            for day, low in zip(daily["time"], daily["temperature_2m_min"], strict=True)
        ]
    except (httpx.HTTPError, KeyError, ValueError) as err:
        raise ClimateError(str(err)) from err


def harm_limit(frost: str, greenhouse: bool) -> float | None:
    """Forecast minimum at or below which a crop needs protection."""
    limit = FROST_HARM_C.get(frost)
    if limit is None:
        return None
    return limit - GREENHOUSE_GAIN_C if greenhouse else limit


def frosty_nights(forecast: list[Night], limit: float, today: date) -> list[Night]:
    """Nights of the coming week at or below the limit."""
    end = today + timedelta(days=FORECAST_DAYS)
    return [
        night for night in forecast if today <= night.day < end and night.low <= limit
    ]
