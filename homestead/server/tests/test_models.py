"""Tests for the Homestead data models."""

from __future__ import annotations

from datetime import date

import pytest

from homestead_server.models import ClimateProfile, MonthDay


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("05-15", MonthDay(5, 15)),
        ("2026-10-03", MonthDay(10, 3)),
        ("02-29", MonthDay(2, 29)),
    ],
)
def test_parse(value: str, expected: MonthDay) -> None:
    """Both MM-DD and ISO dates are accepted."""
    assert MonthDay.parse(value) == expected


@pytest.mark.parametrize("value", ["15", "2026-05", "02-30", "13-01", "1-2-3-4"])
def test_parse_invalid(value: str) -> None:
    """Days that do not exist are refused."""
    with pytest.raises(ValueError):
        MonthDay.parse(value)


def test_str() -> None:
    """The string form is zero-padded MM-DD."""
    assert str(MonthDay(5, 3)) == "05-03"


def test_february_29() -> None:
    """February 29 falls back to the 28th in non-leap years."""
    assert MonthDay(2, 29).in_year(2028) == date(2028, 2, 29)
    assert MonthDay(2, 29).in_year(2027) == date(2027, 2, 28)


def test_frost_free_days_north() -> None:
    """A season within one calendar year."""
    profile = ClimateProfile(MonthDay(5, 15), MonthDay(10, 20))
    assert profile.frost_free_days == 158


def test_frost_free_days_south() -> None:
    """A season that spans New Year."""
    profile = ClimateProfile(MonthDay(10, 15), MonthDay(4, 15))
    assert profile.frost_free_days == 182
