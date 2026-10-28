"""Where the plants of a planting go: in a grid, in rows, staggered or freely.

Distances are in metres, in the frame of the planting's region: origin at
its top-left corner, x to the right, y downwards.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math

LAYOUT_GRID = "grid"
LAYOUT_ROWS = "rows"
LAYOUT_STAGGERED = "staggered"
LAYOUT_FREE = "free"
LAYOUTS = (LAYOUT_GRID, LAYOUT_ROWS, LAYOUT_STAGGERED, LAYOUT_FREE)

DIRECTION_ACROSS = "h"
"""Rows run along the width of the region."""
DIRECTION_DOWN = "v"
"""Rows run along the height of the region."""
DIRECTIONS = (DIRECTION_ACROSS, DIRECTION_DOWN)

# Beyond this, plants are not drawn one by one (radishes, carrots…): the
# region is filled instead.
MAX_POSITIONS = 1500
# Spacing used when neither the planting nor its species gives one.
DEFAULT_SPACING = 0.3


@dataclass(frozen=True, slots=True)
class Placement:
    """Plants of a planting, and how many there are."""

    count: int
    positions: list[tuple[float, float]]
    """Empty when dense."""
    rows: int
    dense: bool


def _centred(length: float, step: float) -> list[float]:
    """Points `step` apart, centred on a segment; at least one."""
    count = max(1, math.floor(length / step + 1e-9))
    first = (length - (count - 1) * step) / 2
    return [first + index * step for index in range(count)]


def _round(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(round(x, 3), round(y, 3)) for x, y in points]


def place(
    layout: str,
    width: float,
    height: float,
    spacing: float | None,
    row_spacing: float | None = None,
    direction: str = DIRECTION_ACROSS,
    points: Sequence[tuple[float, float]] = (),
) -> Placement:
    """Positions of the plants in a region of `width` by `height` metres.

    `spacing` separates plants in a row, `row_spacing` the rows. A grid uses
    `spacing` both ways; staggered rows are offset by half a spacing and set
    closer, so that every plant is `spacing` from its neighbours.
    """
    if layout == LAYOUT_FREE:
        inside = [(x, y) for x, y in points if 0 <= x <= width and 0 <= y <= height]
        return Placement(len(inside), _round(inside), 1, False)
    spacing = spacing if spacing and spacing > 0 else DEFAULT_SPACING
    if layout == LAYOUT_ROWS:
        across = row_spacing if row_spacing and row_spacing > 0 else spacing
    elif layout == LAYOUT_STAGGERED:
        across = spacing * math.sqrt(3) / 2
    else:
        across = spacing
    along_length, across_length = (
        (width, height) if direction == DIRECTION_ACROSS else (height, width)
    )
    rows = _centred(across_length, across)
    plants = _centred(along_length, spacing)
    staggered = layout == LAYOUT_STAGGERED and len(plants) >= 2
    count = 0
    for index in range(len(rows)):
        count += len(plants) - (1 if staggered and index % 2 else 0)
    if count > MAX_POSITIONS:
        return Placement(count, [], len(rows), True)
    result: list[tuple[float, float]] = []
    for index, row in enumerate(rows):
        shifted = staggered and index % 2
        for along in plants[:-1] if shifted else plants:
            along += spacing / 2 if shifted else 0
            result.append(
                (along, row) if direction == DIRECTION_ACROSS else (row, along)
            )
    return Placement(count, _round(result), len(rows), False)
