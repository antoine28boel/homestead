"""Tests for the crop calendar arithmetic."""

from __future__ import annotations

from datetime import date

import pytest

from homestead_server.catalog import Species, load_catalog
from homestead_server.models import ClimateProfile, MonthDay
from homestead_server.planner import (
    Planting,
    PlantingState,
    Space,
    next_season,
    open_windows,
    schedule,
    season_frosts,
    tasks,
    window_period,
)

BELGIUM = ClimateProfile(MonthDay(5, 15), MonthDay(10, 20))
AUSTRALIA = ClimateProfile(MonthDay(10, 15), MonthDay(4, 15))
PLOT = Space("plot", "Potager", "bed", 0)
GREENHOUSE = Space("greenhouse", "Serre", "greenhouse", 4)


@pytest.fixture(scope="module")
def catalog() -> dict[str, Species]:
    """The bundled catalogue."""
    return load_catalog()


def _planting(
    catalog: dict[str, Species],
    species: str,
    method: str,
    space: Space = PLOT,
    season: int = 2027,
    window: int = 0,
) -> Planting:
    return Planting(
        id="p",
        species=catalog[species],
        variety="",
        space=space,
        method=method,
        window=window,
        season=season,
    )


def test_season_frosts() -> None:
    """Southern seasons end in the following year; shelters widen them."""
    assert season_frosts(BELGIUM, 2027, 0) == (date(2027, 5, 15), date(2027, 10, 20))
    assert season_frosts(BELGIUM, 2027, 4) == (date(2027, 4, 17), date(2027, 11, 17))
    assert season_frosts(AUSTRALIA, 2026, 0) == (date(2026, 10, 15), date(2027, 4, 15))


def test_window_period(catalog: dict[str, Species]) -> None:
    """Tomatoes are sown 8 to 6 weeks before the last frost."""
    window = catalog["tomato"].sow_indoors[0]
    assert window_period(window, BELGIUM, 2027, 0) == (
        date(2027, 3, 20),
        date(2027, 4, 3),
    )
    assert window_period(window, BELGIUM, 2027, 4) == (
        date(2027, 2, 20),
        date(2027, 3, 6),
    )


def test_next_season(catalog: dict[str, Species]) -> None:
    """At the end of October, garlic goes in now and tomatoes wait for 2027."""
    today = date(2026, 10, 27)
    garlic = catalog["garlic"].transplant[0]
    tomato = catalog["tomato"].sow_indoors[0]
    assert next_season(garlic, BELGIUM, 0, today) == 2026
    assert next_season(tomato, BELGIUM, 0, today) == 2027


def test_schedule_tomato(catalog: dict[str, Species]) -> None:
    """Expected periods of open-ground tomatoes."""
    plan = schedule(
        _planting(catalog, "tomato", "sow_indoors"), PlantingState(), BELGIUM
    )
    assert plan.sow == (date(2027, 3, 20), date(2027, 4, 3))
    assert plan.transplant == (date(2027, 5, 22), date(2027, 6, 5))
    assert plan.harvest == (date(2027, 7, 21), date(2027, 10, 24))


def test_schedule_follows_actual_dates(catalog: dict[str, Species]) -> None:
    """Harvest moves with the real transplanting date."""
    state = PlantingState(
        stage="transplanted",
        dates={"sown": date(2027, 3, 22), "transplanted": date(2027, 6, 1)},
    )
    plan = schedule(_planting(catalog, "tomato", "sow_indoors"), state, BELGIUM)
    assert plan.harvest[0] == date(2027, 7, 31)


def test_schedule_autumn_garlic(catalog: dict[str, Species]) -> None:
    """Autumn garlic has its own days to harvest."""
    planting = _planting(catalog, "garlic", "plant", season=2026)
    plan = schedule(planting, PlantingState(), BELGIUM)
    assert plan.transplant == (date(2026, 10, 20), date(2026, 11, 24))
    assert plan.harvest[0] == date(2027, 6, 7)


def test_schedule_bought_lettuce(catalog: dict[str, Species]) -> None:
    """A bought plant was sown in the nursery some weeks before planting."""
    planting = _planting(catalog, "lettuce", "plant")
    plan = schedule(planting, PlantingState(), BELGIUM)
    assert plan.sow is None
    # Planted from 3 April, sown 4 weeks earlier, harvested 55 days after sowing.
    assert plan.transplant[0] == date(2027, 4, 3)
    assert plan.harvest[0] == date(2027, 4, 30)


def test_tasks_through_the_season(catalog: dict[str, Species]) -> None:
    """Each stage brings its own tasks."""
    planting = _planting(catalog, "tomato", "sow_indoors")

    def keys(state: PlantingState) -> dict[str, tuple[date, str | None]]:
        plan = schedule(planting, state, BELGIUM)
        return {
            task.key: (task.due, task.action) for task in tasks(planting, state, plan)
        }

    assert keys(PlantingState()) == {"sow": (date(2027, 3, 20), "sown")}

    sown = PlantingState("sown", {"sown": date(2027, 3, 22)})
    assert keys(sown) == {"transplant": (date(2027, 5, 22), "transplanted")}

    transplanted = PlantingState(
        "transplanted", {"sown": date(2027, 3, 22), "transplanted": date(2027, 5, 25)}
    )
    assert keys(transplanted) == {
        "task.stake": (date(2027, 6, 1), None),
        "task.side_shoots": (date(2027, 6, 15), None),
        "harvest": (date(2027, 7, 24), "harvesting"),
    }

    harvesting = PlantingState(
        "harvesting",
        {
            "sown": date(2027, 3, 22),
            "transplanted": date(2027, 5, 25),
            "harvesting": date(2027, 7, 20),
        },
    )
    assert keys(harvesting)["finish"][1] == "finished"
    assert "harvest" not in keys(harvesting)

    assert keys(PlantingState("finished")) == {}


def test_tasks_direct_sowing(catalog: dict[str, Species]) -> None:
    """Direct sowings skip the transplant task."""
    planting = _planting(catalog, "carrot", "sow_direct")
    state = PlantingState("sown", {"sown": date(2027, 4, 20)})
    plan = schedule(planting, state, BELGIUM)
    assert {task.key for task in tasks(planting, state, plan)} == {
        "task.thin",
        "harvest",
    }


def test_open_windows(catalog: dict[str, Species]) -> None:
    """What can be started on a given day."""
    today = date(2027, 4, 20)
    assert open_windows(catalog["carrot"], BELGIUM, 0, today) == ["sow_direct"]
    assert open_windows(catalog["tomato"], BELGIUM, 0, today) == []
    # Four weeks ahead in the greenhouse, tomatoes can be planted out.
    assert open_windows(catalog["tomato"], BELGIUM, 4, date(2027, 4, 28)) == ["plant"]
