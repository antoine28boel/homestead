"""Rotation and neighbours: what to know before putting a crop somewhere.

A crop is checked against the others of its space:
- rotation: the same family grown there in the last years;
- neighbours: a companion or a species to avoid, there at the same time.

When both crops have a region drawn in the space, only regions that overlap
count for rotation, and only regions close to each other for neighbours.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math

from .catalog import Species

NEIGHBOUR_GAP_M = 1.0
"""Regions further apart than this are not neighbours."""

RELATION_AVOID = "avoid"
RELATION_COMPANION = "companion"


@dataclass(frozen=True, slots=True)
class Region:
    """A rectangle in a space, in metres from its top-left corner."""

    x: float
    y: float
    width: float
    height: float

    def gap(self, other: Region) -> float:
        """Distance between the two rectangles; 0 when they touch or overlap."""
        dx = max(other.x - (self.x + self.width), self.x - (other.x + other.width), 0)
        dy = max(other.y - (self.y + self.height), self.y - (other.y + other.height), 0)
        return math.hypot(dx, dy)

    def overlaps(self, other: Region) -> bool:
        """Whether the two rectangles share some ground."""
        across = min(self.x + self.width, other.x + other.width) - max(self.x, other.x)
        down = min(self.y + self.height, other.y + other.height) - max(self.y, other.y)
        return across > 0 and down > 0


def same_ground(a: Region | None, b: Region | None) -> bool:
    """Whether two crops of a space grow on the same ground.

    A crop without a region takes the whole space.
    """
    return a is None or b is None or a.overlaps(b)


def nearby(a: Region | None, b: Region | None) -> bool:
    """Whether two crops of a space grow close to each other."""
    return a is None or b is None or a.gap(b) <= NEIGHBOUR_GAP_M


def relation(a: Species, b: Species) -> str | None:
    """How two species get on, whichever side of the catalogue says so."""
    if b.id in a.avoid or a.id in b.avoid:
        return RELATION_AVOID
    if b.id in a.companions or a.id in b.companions:
        return RELATION_COMPANION
    return None


def rotation_clash(
    species: Species, season: int, other: Species, other_season: int
) -> bool:
    """Whether `other` grew too recently where `species` is about to go."""
    return (
        species.family == other.family
        and 0 < season - other_season < species.rotation_years
    )


def overlap(a: tuple[date, date], b: tuple[date, date]) -> bool:
    """Whether two periods, ends included, share a day."""
    return a[0] <= b[1] and b[0] <= a[1]
