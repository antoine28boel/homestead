"""Data models for the Homestead integration."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Any

from .const import CONF_FIRST_FROST, CONF_LAST_FROST

# A non-leap reference year, so that season lengths do not depend on the
# current year.
_REFERENCE_YEAR = 2001


@dataclass(frozen=True, slots=True)
class MonthDay:
    """A day of the year without a year, such as an average frost date."""

    month: int
    day: int

    def __post_init__(self) -> None:
        """Reject days that do not exist in any year."""
        # 2000 is a leap year, so February 29 is accepted.
        date(2000, self.month, self.day)

    @classmethod
    def parse(cls, value: str) -> MonthDay:
        """Parse "MM-DD" or an ISO date "YYYY-MM-DD" (the year is ignored)."""
        parts = value.strip().split("-")
        if len(parts) == 3:
            parts = parts[1:]
        if len(parts) != 2:
            raise ValueError(f"Invalid month-day: {value!r}")
        return cls(int(parts[0]), int(parts[1]))

    def in_year(self, year: int) -> date:
        """Return this day in the given year (February 29 becomes the 28th)."""
        if (self.month, self.day) == (2, 29) and not calendar.isleap(year):
            return date(year, 2, 28)
        return date(year, self.month, self.day)

    def __str__(self) -> str:
        """Return the "MM-DD" form used in config entries."""
        return f"{self.month:02d}-{self.day:02d}"


@dataclass(frozen=True, slots=True)
class ClimateProfile:
    """Average frost dates of a garden, the reference for every crop calendar."""

    last_frost: MonthDay
    """Average last frost of spring."""
    first_frost: MonthDay
    """Average first frost of autumn."""

    @classmethod
    def from_options(cls, options: dict[str, Any]) -> ClimateProfile:
        """Build the profile from config entry options."""
        return cls(
            last_frost=MonthDay.parse(options[CONF_LAST_FROST]),
            first_frost=MonthDay.parse(options[CONF_FIRST_FROST]),
        )

    @property
    def frost_free_days(self) -> int:
        """Length of the frost-free season, which may span New Year."""
        last = self.last_frost.in_year(_REFERENCE_YEAR)
        first = self.first_frost.in_year(_REFERENCE_YEAR)
        days = (first - last).days
        return days if days > 0 else days + 365
