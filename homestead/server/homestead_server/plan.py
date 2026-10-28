"""The garden plan: what is drawn where, and where each plant goes.

Everything is in metres. Spaces and other objects are rectangles placed by
their top-left corner and turned around their centre. A planting occupies a
region of its space, in the space's own frame.
"""

from __future__ import annotations

import json
import math
from typing import Any

from .const import (
    DEFAULT_PLAN_SIZE,
    METHOD_SOW_INDOORS,
    SPACE_BED,
    SPACE_CONTAINER,
    SPACE_GREENHOUSE,
    SPACE_RAISED_BED,
    STAGE_PLANNED,
    STAGE_SOWN,
)
from .garden import Garden
from .layout import LAYOUT_GRID, LAYOUT_ROWS, place
from .orm import GardenRow, PlanItemRow, PlantingRow, SpaceRow, TaskStateRow

DEFAULT_LAYOUT = {
    SPACE_BED: LAYOUT_ROWS,
    SPACE_RAISED_BED: LAYOUT_GRID,
    SPACE_GREENHOUSE: LAYOUT_ROWS,
    SPACE_CONTAINER: LAYOUT_GRID,
}
# Room left around the objects of a plan without a set size.
MARGIN = 1.0


def _corners(
    x: float, y: float, width: float, height: float, rotation: float
) -> list[tuple[float, float]]:
    centre_x, centre_y = x + width / 2, y + height / 2
    angle = math.radians(rotation)
    cos, sin = math.cos(angle), math.sin(angle)
    return [
        (
            centre_x + dx * cos - dy * sin,
            centre_y + dx * sin + dy * cos,
        )
        for dx, dy in (
            (-width / 2, -height / 2),
            (width / 2, -height / 2),
            (width / 2, height / 2),
            (-width / 2, height / 2),
        )
    ]


def background_size(row: GardenRow) -> tuple[float, float] | None:
    """Size of the background in metres, once calibrated."""
    if not (
        row.background
        and row.background_scale
        and row.background_width
        and row.background_height
    ):
        return None
    return (
        round(row.background_width * row.background_scale, 2),
        round(row.background_height * row.background_scale, 2),
    )


def plan_size(
    row: GardenRow, spaces: list[SpaceRow], items: list[PlanItemRow]
) -> tuple[float, float]:
    """The set size, or the background's, or enough for every object."""
    if row.plan_width and row.plan_height:
        return row.plan_width, row.plan_height
    if size := background_size(row):
        return size
    width, height = DEFAULT_PLAN_SIZE
    for shape in [*spaces, *items]:
        if shape.width is None or shape.x is None:
            continue
        for x, y in _corners(
            shape.x, shape.y, shape.width, shape.height, shape.rotation or 0
        ):
            width, height = max(width, x + MARGIN), max(height, y + MARGIN)
    return round(width, 2), round(height, 2)


def space_area(row: SpaceRow) -> float | None:
    """Surface given by the gardener, or drawn."""
    if row.area is not None:
        return row.area
    if row.placed:
        if row.shape == "round":
            return round(math.pi * row.width * row.height / 4, 2)
        return round(row.width * row.height, 2)
    return None


def in_ground(row: PlantingRow) -> bool:
    """Whether the plants are in their space (not planned, not in the nursery)."""
    if row.stage == STAGE_PLANNED:
        return False
    return not (row.method == METHOD_SOW_INDOORS and row.stage == STAGE_SOWN)


def _regions(
    space: SpaceRow, plantings: list[PlantingRow]
) -> dict[str, tuple[float, float, float, float]]:
    """Region of each planting; those without one share the rest of the space.

    The space is cut into equal strips across its longer side, in the order
    the plantings were created.
    """
    regions: dict[str, tuple[float, float, float, float]] = {}
    free = []
    for row in plantings:
        if None in (row.region_x, row.region_y, row.region_width, row.region_height):
            free.append(row)
            continue
        x = min(max(row.region_x, 0), space.width)
        y = min(max(row.region_y, 0), space.height)
        regions[row.id] = (
            x,
            y,
            max(min(row.region_width, space.width - x), 0.01),
            max(min(row.region_height, space.height - y), 0.01),
        )
    for index, row in enumerate(free):
        if space.width >= space.height:
            step = space.width / len(free)
            regions[row.id] = (index * step, 0, step, space.height)
        else:
            step = space.height / len(free)
            regions[row.id] = (0, index * step, space.width, step)
    return {
        key: tuple(round(value, 3) for value in region)
        for key, region in regions.items()
    }


def _points(raw: str | None) -> list[tuple[float, float]]:
    if not raw:
        return []
    try:
        return [(float(x), float(y)) for x, y in json.loads(raw)]
    except (ValueError, TypeError):
        return []


def planting_on_plan(
    garden: Garden,
    row: PlantingRow,
    space: SpaceRow,
    region: tuple[float, float, float, float],
    states: dict[str, TaskStateRow],
) -> dict[str, Any]:
    """A planting with its region and the position of every plant."""
    species = garden.catalog[row.species]
    plant_cm, row_cm = species.spacing_cm or (None, None)
    spacing = row.spacing or plant_cm
    row_spacing = row.row_spacing or row_cm
    layout = row.layout or DEFAULT_LAYOUT.get(space.type, LAYOUT_ROWS)
    x, y, width, height = region
    placement = place(
        layout,
        width,
        height,
        spacing / 100 if spacing else None,
        row_spacing / 100 if row_spacing else None,
        row.direction,
        _points(row.points),
    )
    today = garden.clock.today().isoformat()
    open_tasks = garden.planting_tasks(row, states)
    return {
        "id": row.id,
        "name": garden.planting_name(row),
        "species": row.species,
        "family": species.family,
        "season": row.season,
        "method": row.method,
        "stage": row.stage,
        "in_ground": in_ground(row),
        "space_id": space.id,
        "layout": layout,
        "layout_set": row.layout is not None,
        "region": {"x": x, "y": y, "width": width, "height": height},
        "region_set": row.region_x is not None,
        "spacing": spacing,
        "row_spacing": row_spacing,
        "direction": row.direction,
        "count": placement.count,
        "rows": placement.rows,
        "dense": placement.dense,
        "positions": placement.positions,
        "quantity": row.quantity,
        "tasks_due": sum(task["due"] <= today for task in open_tasks),
        "next_task": open_tasks[0] if open_tasks else None,
    }


def space_on_plan(row: SpaceRow) -> dict[str, Any]:
    """Where a space is drawn."""
    return {
        "x": row.x,
        "y": row.y,
        "width": row.width,
        "height": row.height,
        "rotation": row.rotation,
        "shape": row.shape,
    }


def item_out(row: PlanItemRow) -> dict[str, Any]:
    """An object of the plan that is not grown."""
    return {
        "id": row.id,
        "kind": row.kind,
        "label": row.label,
        "x": row.x,
        "y": row.y,
        "width": row.width,
        "height": row.height,
        "rotation": row.rotation,
        "sort": row.sort,
    }


def background_out(row: GardenRow) -> dict[str, Any] | None:
    """The aerial view or drone photo under the plan."""
    if not row.background:
        return None
    return {
        "url": f"api/plan/background/{row.background}",
        "width": row.background_width,
        "height": row.background_height,
        "scale": row.background_scale,
        "opacity": row.background_opacity,
    }


def plan_out(
    garden: Garden, items: list[PlanItemRow], *, with_background: bool = True
) -> dict[str, Any]:
    """The whole plan, with the plants of every active planting."""
    spaces = garden.spaces()
    width, height = plan_size(garden.row, spaces, items)
    states = garden.task_states()
    by_space: dict[str, list[PlantingRow]] = {}
    for row in sorted(garden.plantings(active=True), key=lambda row: row.created_at):
        if row.space_id:
            by_space.setdefault(row.space_id, []).append(row)
    plantings = []
    for space in spaces:
        if not space.placed or space.id not in by_space:
            continue
        regions = _regions(space, by_space[space.id])
        plantings.extend(
            planting_on_plan(garden, row, space, regions[row.id], states)
            for row in by_space[space.id]
        )
    return {
        "width": width,
        "height": height,
        "size_set": bool(garden.row.plan_width and garden.row.plan_height),
        "background": background_out(garden.row) if with_background else None,
        "spaces": [
            {
                "id": space.id,
                "name": space.name,
                "type": space.type,
                "placed": space.placed,
                **space_on_plan(space),
            }
            for space in spaces
        ],
        "items": [item_out(item) for item in items],
        "plantings": plantings,
    }
