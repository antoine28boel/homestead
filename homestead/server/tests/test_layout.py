"""Tests for where plants go in their region."""

from __future__ import annotations

import math

from homestead_server.layout import (
    DIRECTION_DOWN,
    LAYOUT_FREE,
    LAYOUT_GRID,
    LAYOUT_ROWS,
    LAYOUT_STAGGERED,
    MAX_POSITIONS,
    place,
)


def test_rows() -> None:
    """Garlic, 10 cm apart in rows 25 cm apart, in a strip of 1 m by 0.5 m."""
    placement = place(LAYOUT_ROWS, 1.0, 0.5, 0.10, 0.25)
    assert placement.rows == 2
    assert placement.count == 20
    assert placement.positions[0] == (0.05, 0.125)
    assert placement.positions[-1] == (0.95, 0.375)
    assert not placement.dense


def test_rows_down() -> None:
    """Rows can run along the height of the region instead."""
    placement = place(LAYOUT_ROWS, 1.0, 0.5, 0.10, 0.25, DIRECTION_DOWN)
    assert placement.rows == 4
    assert placement.count == 20
    assert {x for x, _ in placement.positions} == {0.125, 0.375, 0.625, 0.875}


def test_grid() -> None:
    """A square of 1.2 m with plants every 30 cm holds 4 by 4 plants."""
    placement = place(LAYOUT_GRID, 1.2, 1.2, 0.30, 0.70)
    assert placement.count == 16
    assert placement.positions[0] == (0.15, 0.15)


def test_staggered() -> None:
    """Every other row is shifted by half a spacing and has one plant less."""
    placement = place(LAYOUT_STAGGERED, 1.0, 1.0, 0.25)
    rows: dict[float, list[float]] = {}
    for x, y in placement.positions:
        rows.setdefault(y, []).append(x)
    lines = [rows[y] for y in sorted(rows)]
    assert len(lines[0]) == 4
    assert len(lines[1]) == 3
    assert lines[1][0] == lines[0][0] + 0.125
    gap = sorted(rows)[1] - sorted(rows)[0]
    assert math.isclose(gap, 0.25 * math.sqrt(3) / 2, abs_tol=0.002)
    assert placement.count == len(placement.positions)


def test_small_region() -> None:
    """A region smaller than the spacing still holds one plant, centred."""
    placement = place(LAYOUT_GRID, 0.2, 0.2, 1.0)
    assert placement.positions == [(0.1, 0.1)]


def test_dense() -> None:
    """Radishes every 3 cm in rows 15 cm apart are counted, not drawn."""
    placement = place(LAYOUT_ROWS, 8.0, 4.0, 0.03, 0.15)
    assert placement.dense
    assert placement.positions == []
    assert placement.count == 266 * 26
    assert placement.count > MAX_POSITIONS


def test_free() -> None:
    """Free points outside the region are dropped."""
    placement = place(LAYOUT_FREE, 1.0, 1.0, None, points=[(0.2, 0.3), (1.5, 0.1)])
    assert placement.positions == [(0.2, 0.3)]
    assert placement.count == 1


def test_default_spacing() -> None:
    """Without a spacing, plants are 30 cm apart."""
    assert place(LAYOUT_GRID, 0.6, 0.3, None).count == 2
