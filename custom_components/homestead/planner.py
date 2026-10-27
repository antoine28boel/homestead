"""Crop calendar arithmetic, independent of Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .catalog import Species, Window
from .const import (
    AFTER_SOWING,
    AFTER_TRANSPLANT,
    METHOD_PLANT,
    METHOD_SOW_DIRECT,
    METHOD_SOW_INDOORS,
    REF_FIRST_FROST,
    STAGE_FINISHED,
    STAGE_GROWING,
    STAGE_HARVESTING,
    STAGE_PLANNED,
    STAGE_SOWN,
    STAGE_TRANSPLANTED,
    STAGES,
)
from .models import ClimateProfile

type Period = tuple[date, date]

# Task kinds, also used as translation keys.
KIND_SOW_INDOORS = "sow_indoors"
KIND_SOW_DIRECT = "sow_direct"
KIND_PLANT = "plant"
KIND_TRANSPLANT = "transplant"
KIND_HARVEST_START = "harvest_start"
KIND_HARVEST_END = "harvest_end"
KIND_CROP = "crop"


@dataclass(frozen=True, slots=True)
class Space:
    """A bed, a greenhouse… where plantings grow."""

    id: str
    name: str
    type: str
    frost_shift: int
    """Weeks gained on frost, in spring and in autumn."""
    area: float | None = None


@dataclass(frozen=True, slots=True)
class Planting:
    """One crop in one space, for one season."""

    id: str
    species: Species
    variety: str
    space: Space | None
    method: str
    window: int
    season: int
    quantity: int | None = None


@dataclass(slots=True)
class PlantingState:
    """What has happened to a planting so far."""

    stage: str = STAGE_PLANNED
    dates: dict[str, date] = field(default_factory=dict)
    """Day each stage was reached."""


@dataclass(frozen=True, slots=True)
class Schedule:
    """Expected periods of a planting."""

    sow: Period | None
    transplant: Period | None
    harvest: Period


@dataclass(frozen=True, slots=True)
class Task:
    """Something to do for a planting."""

    key: str
    kind: str
    due: date
    action: str | None = None
    """Stage reached when the task is done."""
    label: dict[str, str] | None = None
    """Label of a catalogue task."""
    period: Period | None = None


def season_frosts(climate: ClimateProfile, year: int, shift: int) -> Period:
    """Last frost of spring and first frost of autumn of a growing season.

    The season is named after the year of its spring. South of the equator,
    its autumn frost falls in the following year.
    """
    last = climate.last_frost.in_year(year)
    first = climate.first_frost.in_year(year)
    if first <= last:
        first = climate.first_frost.in_year(year + 1)
    weeks = timedelta(weeks=shift)
    return last - weeks, first + weeks


def window_period(
    window: Window, climate: ClimateProfile, year: int, shift: int
) -> Period:
    """Dates of a window in a season, for a space that gains `shift` weeks."""
    last, first = season_frosts(climate, year, shift)
    ref = first if window.ref == REF_FIRST_FROST else last
    return ref + timedelta(weeks=window.start), ref + timedelta(weeks=window.end)


def next_season(
    window: Window, climate: ClimateProfile, shift: int, today: date
) -> int:
    """The first season in which this window has not ended yet."""
    for year in (today.year - 1, today.year, today.year + 1):
        if window_period(window, climate, year, shift)[1] >= today:
            return year
    return today.year + 1


def _pick(windows: tuple[Window, ...], index: int) -> Window | None:
    if not windows:
        return None
    return windows[min(index, len(windows) - 1)]


def schedule(
    planting: Planting, state: PlantingState, climate: ClimateProfile
) -> Schedule:
    """Sowing, transplanting and harvest periods of a planting."""
    species = planting.species
    shift = planting.space.frost_shift if planting.space else 0
    chosen = _pick(species.windows(planting.method), planting.window)
    assert chosen is not None  # the config flow only offers existing windows

    def period(window: Window | None) -> Period | None:
        if window is None:
            return None
        return window_period(window, climate, planting.season, shift)

    sow: Period | None = None
    transplant: Period | None = None
    if planting.method == METHOD_SOW_INDOORS:
        sow = period(chosen)
        transplant = period(_pick(species.transplant, planting.window))
    elif planting.method == METHOD_SOW_DIRECT:
        sow = period(chosen)
    else:
        transplant = period(chosen)

    # Every planting has a sowing or a transplanting date, actual or expected.
    sown = state.dates.get(STAGE_SOWN) or (sow[0] if sow else None)
    transplanted = state.dates.get(STAGE_TRANSPLANTED) or (
        transplant[0] if transplant else None
    )
    nursery = timedelta(days=species.nursery_days)
    if species.harvest.after == AFTER_TRANSPLANT:
        ref = transplanted or sown + nursery  # type: ignore[operator]
    else:
        # A bought plant was sown in the nursery some weeks earlier.
        ref = sown or transplanted - nursery  # type: ignore[operator]

    days = chosen.harvest_days or species.harvest.days
    start = state.dates.get(STAGE_HARVESTING) or ref + timedelta(days=days[0])
    end = ref + timedelta(days=days[1], weeks=species.harvest.weeks)
    return Schedule(sow=sow, transplant=transplant, harvest=(start, max(start, end)))


def _reached(state: PlantingState, stage: str) -> bool:
    return STAGES.index(state.stage) >= STAGES.index(stage)


def tasks(planting: Planting, state: PlantingState, plan: Schedule) -> list[Task]:
    """Every task of a planting at its current stage, done or not."""
    if state.stage == STAGE_FINISHED:
        return []
    result: list[Task] = []
    method = planting.method

    if state.stage == STAGE_PLANNED:
        if method == METHOD_PLANT:
            assert plan.transplant
            result.append(
                Task(
                    "plant",
                    KIND_PLANT,
                    plan.transplant[0],
                    STAGE_TRANSPLANTED,
                    period=plan.transplant,
                )
            )
        else:
            assert plan.sow
            kind = KIND_SOW_INDOORS if method == METHOD_SOW_INDOORS else KIND_SOW_DIRECT
            result.append(Task("sow", kind, plan.sow[0], STAGE_SOWN, period=plan.sow))
        return result

    waiting_transplant = method == METHOD_SOW_INDOORS and not _reached(
        state, STAGE_TRANSPLANTED
    )
    if waiting_transplant and plan.transplant:
        result.append(
            Task(
                "transplant",
                KIND_TRANSPLANT,
                plan.transplant[0],
                STAGE_TRANSPLANTED,
                period=plan.transplant,
            )
        )

    refs = {
        AFTER_SOWING: state.dates.get(STAGE_SOWN),
        AFTER_TRANSPLANT: state.dates.get(STAGE_TRANSPLANTED),
    }
    for crop_task in planting.species.tasks:
        if (ref := refs[crop_task.after]) is not None:
            result.append(
                Task(
                    f"task.{crop_task.id}",
                    KIND_CROP,
                    ref + timedelta(days=crop_task.days),
                    label=crop_task.label,
                )
            )

    if state.stage == STAGE_HARVESTING:
        result.append(Task("finish", KIND_HARVEST_END, plan.harvest[1], STAGE_FINISHED))
    elif not waiting_transplant and state.stage in (
        STAGE_SOWN,
        STAGE_TRANSPLANTED,
        STAGE_GROWING,
    ):
        result.append(
            Task(
                "harvest",
                KIND_HARVEST_START,
                plan.harvest[0],
                STAGE_HARVESTING,
                period=plan.harvest,
            )
        )
    return result


def open_windows(
    species: Species, climate: ClimateProfile, shift: int, today: date
) -> list[str]:
    """Methods whose window includes today, for a space gaining `shift` weeks."""
    methods = []
    for method in species.methods:
        for window in species.windows(method):
            if any(
                start <= today <= end
                for start, end in (
                    window_period(window, climate, year, shift)
                    for year in (today.year - 1, today.year, today.year + 1)
                )
            ):
                methods.append(method)
                break
    return methods
