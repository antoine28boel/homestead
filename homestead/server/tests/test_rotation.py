"""Tests for rotation and neighbours."""

from __future__ import annotations

from datetime import date

import pytest

from homestead_server.catalog import load_catalog
from homestead_server.rotation import (
    RELATION_AVOID,
    RELATION_COMPANION,
    Region,
    nearby,
    overlap,
    relation,
    rotation_clash,
    same_ground,
)

CATALOG = load_catalog()


def test_regions() -> None:
    """Gaps and overlaps between two rectangles of a space."""
    a = Region(0, 0, 1, 1)
    assert a.gap(Region(1, 0, 1, 1)) == 0
    assert not a.overlaps(Region(1, 0, 1, 1))
    assert a.overlaps(Region(0.5, 0.5, 1, 1))
    assert a.gap(Region(4, 5, 1, 1)) == pytest.approx(5)
    # A crop without a region takes the whole space.
    assert same_ground(None, a) and nearby(a, None)
    assert nearby(a, Region(1.8, 0, 1, 1))
    assert not nearby(a, Region(2.5, 0, 1, 1))


def test_relation_either_side() -> None:
    """Either species of the pair may name the other."""
    tomato, basil, potato = CATALOG["tomato"], CATALOG["basil"], CATALOG["potato"]
    assert relation(tomato, basil) == relation(basil, tomato) == RELATION_COMPANION
    assert relation(potato, tomato) == relation(tomato, potato) == RELATION_AVOID
    assert relation(tomato, CATALOG["spinach"]) is None


def test_rotation_clash() -> None:
    """A family comes back after its number of years, not before."""
    tomato, potato = CATALOG["tomato"], CATALOG["potato"]
    assert tomato.rotation_years == 4
    assert rotation_clash(potato, 2027, tomato, 2026)
    assert rotation_clash(potato, 2029, tomato, 2026)
    assert not rotation_clash(potato, 2030, tomato, 2026)
    # The same season is for neighbours, not rotation.
    assert not rotation_clash(potato, 2026, tomato, 2026)
    assert not rotation_clash(potato, 2027, CATALOG["carrot"], 2026)


def test_overlap() -> None:
    """Periods include both ends."""
    may, june = (
        (date(2027, 5, 1), date(2027, 5, 31)),
        (date(2027, 6, 1), date(2027, 6, 30)),
    )
    assert not overlap(may, june)
    assert overlap(may, (date(2027, 5, 31), date(2027, 6, 2)))
