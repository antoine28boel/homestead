"""The garden as the web interface and Home Assistant see it.

Reads the database, runs the crop calendar and writes back stage changes,
completed tasks and to-do items.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import Species
from .climate import Night, frosty_nights, harm_limit
from .const import (
    DEFAULT_FIRST_FROST_NORTH,
    DEFAULT_FIRST_FROST_SOUTH,
    DEFAULT_FROST_SHIFT,
    DEFAULT_LAST_FROST_NORTH,
    DEFAULT_LAST_FROST_SOUTH,
    DONE_VISIBLE_DAYS,
    METHOD_SOW_DIRECT,
    SPACE_GREENHOUSE,
    STAGE_FINISHED,
    STAGE_GROWING,
    STAGE_HARVESTING,
    STAGE_PLANNED,
    STAGE_SOWN,
    STAGE_TRANSPLANTED,
    STAGES,
    TASK_HORIZON_DAYS,
)
from .models import ClimateProfile, MonthDay
from .orm import (
    STAGE_COLUMNS,
    GardenRow,
    PlantingRow,
    SpaceRow,
    TaskStateRow,
    TodoItemRow,
)
from .planner import (
    KIND_CROP,
    KIND_HARVEST_START,
    KIND_PLANT,
    KIND_SOW_DIRECT,
    KIND_SOW_INDOORS,
    KIND_TRANSPLANT,
    Planting,
    PlantingState,
    Schedule,
    Space,
    Task,
    next_season,
    open_windows,
    schedule,
    steps,
    tasks,
    window_period,
)
from .texts import Texts


@dataclass(frozen=True, slots=True)
class Clock:
    """Local date and time of the garden."""

    now: Callable[[], datetime]

    def today(self) -> date:
        """Local date."""
        return self.now().date()


def default_frost_dates(latitude: float) -> tuple[str, str]:
    """Rough frost dates for the hemisphere, until the gardener sets theirs."""
    if latitude < 0:
        return DEFAULT_LAST_FROST_SOUTH, DEFAULT_FIRST_FROST_SOUTH
    return DEFAULT_LAST_FROST_NORTH, DEFAULT_FIRST_FROST_NORTH


def ensure_garden(session: Session, name: str, latitude: float) -> GardenRow:
    """Create the garden row on first start."""
    garden = session.get(GardenRow, 1)
    if garden is None:
        last, first = default_frost_dates(latitude)
        garden = GardenRow(id=1, name=name, last_frost=last, first_frost=first)
        session.add(garden)
        session.commit()
    return garden


# Steps drawn as periods in the calendar rather than on their own day.
PERIOD_KINDS = (
    KIND_SOW_INDOORS,
    KIND_SOW_DIRECT,
    KIND_PLANT,
    KIND_TRANSPLANT,
    KIND_HARVEST_START,
)

# Starting steps put off while frost is forecast, and the tolerances concerned.
HELD_KINDS = {
    KIND_PLANT: ("tender", "half_hardy"),
    KIND_TRANSPLANT: ("tender", "half_hardy"),
    KIND_SOW_DIRECT: ("tender",),
}
# Stages at which a crop stands in its space.
IN_PLACE = (STAGE_TRANSPLANTED, STAGE_GROWING, STAGE_HARVESTING)

STEP_DONE = "done"
STEP_DISMISSED = "dismissed"
STEP_OPEN = "open"
STEP_PLANNED = "planned"
STEP_SKIPPED = "skipped"
"""Its moment passed without it being ticked."""


def is_generated(uid: str) -> bool:
    """Generated task uids are "<planting id>.<key>"; own items have no dot."""
    return "." in uid


class Garden:
    """Everything about the garden for one request."""

    def __init__(
        self,
        session: Session,
        catalog: dict[str, Species],
        texts: Texts,
        clock: Clock,
        forecast: list[Night] | None = None,
    ) -> None:
        """Bind to a database session."""
        self.session = session
        self.catalog = catalog
        self.texts = texts
        self.clock = clock
        self.forecast = forecast or []
        row = session.get(GardenRow, 1)
        assert row is not None, "ensure_garden runs at startup"
        self.row = row
        self.climate = ClimateProfile(
            MonthDay.parse(row.last_frost), MonthDay.parse(row.first_frost)
        )

    # Spaces and plantings

    def spaces(self, include_archived: bool = False) -> list[SpaceRow]:
        """Spaces in display order."""
        query = select(SpaceRow).order_by(SpaceRow.sort, SpaceRow.name)
        if not include_archived:
            query = query.where(SpaceRow.archived.is_(False))
        return list(self.session.scalars(query))

    @staticmethod
    def space_model(row: SpaceRow) -> Space:
        """Planner view of a space."""
        shift = row.frost_shift
        return Space(
            id=row.id,
            name=row.name,
            type=row.type,
            frost_shift=shift if shift is not None else DEFAULT_FROST_SHIFT[row.type],
            area=row.area,
        )

    def plantings(
        self,
        *,
        season: int | None = None,
        active: bool | None = None,
        species: str | None = None,
        space_id: str | None = None,
    ) -> list[PlantingRow]:
        """Plantings, filtered."""
        query = select(PlantingRow).order_by(
            PlantingRow.season.desc(), PlantingRow.created_at
        )
        if season is not None:
            query = query.where(PlantingRow.season == season)
        if active is True:
            query = query.where(PlantingRow.stage != STAGE_FINISHED)
        elif active is False:
            query = query.where(PlantingRow.stage == STAGE_FINISHED)
        if species is not None:
            query = query.where(PlantingRow.species == species)
        if space_id is not None:
            query = query.where(PlantingRow.space_id == space_id)
        return [
            row for row in self.session.scalars(query) if row.species in self.catalog
        ]

    def planting_model(self, row: PlantingRow) -> Planting:
        """Planner view of a planting."""
        space = self.session.get(SpaceRow, row.space_id) if row.space_id else None
        return Planting(
            id=row.id,
            species=self.catalog[row.species],
            variety=row.variety,
            space=self.space_model(space) if space else None,
            method=row.method,
            window=row.window,
            season=row.season,
            quantity=row.quantity,
        )

    @staticmethod
    def state(row: PlantingRow) -> PlantingState:
        """Stage and dates of a planting."""
        return PlantingState(stage=row.stage, dates=row.stage_dates())

    def schedule(self, row: PlantingRow) -> Schedule:
        """Expected periods of a planting."""
        return schedule(self.planting_model(row), self.state(row), self.climate)

    def planting_name(self, row: PlantingRow) -> str:
        """Species name followed by the variety."""
        name = self.catalog[row.species].name(self.texts.language)
        return f"{name} {row.variety}".strip() if row.variety else name

    def space_name(self, row: PlantingRow) -> str:
        """Name of the space of a planting."""
        space = self.session.get(SpaceRow, row.space_id) if row.space_id else None
        return space.name if space else self.texts("no_space")

    def set_stage(self, row: PlantingRow, stage: str, day: date | None = None) -> None:
        """Move a planting to a stage, and forget the dates of later stages."""
        index = STAGES.index(stage)
        for reached, column in STAGE_COLUMNS.items():
            if STAGES.index(reached) > index:
                setattr(row, column, None)
        if stage != STAGE_PLANNED:
            column = STAGE_COLUMNS[stage]
            setattr(row, column, day or getattr(row, column) or self.clock.today())
        row.stage = stage

    def start_options(self, species: Species, space: SpaceRow) -> list[dict[str, Any]]:
        """Each way and window to start a crop in a space, with its next season."""
        model = self.space_model(space)
        shift = model.frost_shift
        today = self.clock.today()
        options = []
        for method in species.methods:
            for index, window in enumerate(species.windows(method)):
                season = next_season(window, self.climate, shift, today)
                start, end = window_period(window, self.climate, season, shift)
                planting = Planting(
                    id="",
                    species=species,
                    variety="",
                    space=model,
                    method=method,
                    window=index,
                    season=season,
                )
                state = PlantingState()
                plan = schedule(planting, state, self.climate)
                options.append(
                    {
                        "key": f"{method}:{index}",
                        "method": method,
                        "window": index,
                        "season": season,
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "label": self.texts(
                            f"choice_{method}",
                            start=self.texts.date(start),
                            end=self.texts.date(end),
                        ),
                        "steps": [
                            self._step(task, STEP_PLANNED, task.due)
                            for task in steps(planting, state, plan)
                        ],
                    }
                )
        return options

    def sow_now(self, space: SpaceRow) -> dict[str, list[dict[str, str]]]:
        """Species that can be started now in this space, by method."""
        shift = self.space_model(space).frost_shift
        today = self.clock.today()
        result: dict[str, list[dict[str, str]]] = {}
        for species in self.catalog.values():
            for method in open_windows(species, self.climate, shift, today):
                result.setdefault(method, []).append(
                    {"id": species.id, "name": species.name(self.texts.language)}
                )
        return {
            method: sorted(found, key=lambda item: item["name"])
            for method, found in result.items()
        }

    # Tasks

    def _summary(self, row: PlantingRow, task: Task) -> str:
        values = {"name": self.planting_name(row), "space": self.space_name(row)}
        if task.kind == KIND_CROP:
            assert task.label
            return self.texts(task.kind, label=self.texts.label(task.label), **values)
        return self.texts(task.kind, **values)

    def _description(self, row: PlantingRow, task: Task) -> str | None:
        lines = []
        if task.period:
            lines.append(
                self.texts(
                    "period",
                    start=self.texts.date(task.period[0]),
                    end=self.texts.date(task.period[1]),
                )
            )
        spacing = self.catalog[row.species].spacing_cm
        if spacing and task.kind in (KIND_SOW_DIRECT, KIND_PLANT, KIND_TRANSPLANT):
            lines.append(self.texts("spacing", plant=spacing[0], row=spacing[1]))
        return "\n".join(lines) or None

    def _label(self, task: Task) -> str:
        """Name of a step, without the planting."""
        if task.kind == KIND_CROP:
            assert task.label
            return self.texts.label(task.label)
        return self.texts(f"step_{task.kind}")

    def _step(
        self, task: Task, status: str, day: date, held: Night | None = None
    ) -> dict[str, Any]:
        label = self._label(task)
        upcoming = status in (STEP_OPEN, STEP_PLANNED)
        return {
            "key": task.key,
            "kind": task.kind,
            "label": label,
            "day": day.isoformat(),
            "period": [task.period[0].isoformat(), task.period[1].isoformat()]
            if task.period and upcoming
            else None,
            "status": status,
            "action": task.action,
            "frost": self._frost_out(held) if held else None,
        }

    def _steps(
        self, row: PlantingRow, states: dict[str, TaskStateRow]
    ) -> list[tuple[Task, str, date]]:
        """Steps of a planting with their status and day."""
        planting = self.planting_model(row)
        state = self.state(row)
        plan = schedule(planting, state, self.climate)
        current = {task.key for task in tasks(planting, state, plan)}
        stage = STAGES.index(row.stage)
        sequence = steps(planting, state, plan)
        # Steps before the last stage reached that were never ticked are past.
        reached = [
            index
            for index, task in enumerate(sequence)
            if task.action and stage >= STAGES.index(task.action)
        ]
        last = reached[-1] if reached else -1
        result = []
        for index, task in enumerate(sequence):
            day = task.due
            ticked = states.get(f"{row.id}.{task.key}")
            if ticked is not None:
                status = ticked.status
                if status == STEP_DONE and not task.action:
                    day = ticked.at.date()
            elif task.action and stage >= STAGES.index(task.action):
                status = STEP_DONE
            elif task.key in current:
                status = STEP_OPEN
            elif index < last:
                status = STEP_SKIPPED
            else:
                status = STEP_PLANNED
            result.append((task, status, day))
        return result

    def planting_steps(
        self, row: PlantingRow, states: dict[str, TaskStateRow] | None = None
    ) -> list[dict[str, Any]]:
        """Every step of a planting, done, open or still to come."""
        states = self.task_states() if states is None else states
        planting = self.planting_model(row)
        return [
            self._step(
                task,
                status,
                day,
                self._held(planting, task) if status == STEP_OPEN else None,
            )
            for task, status, day in self._steps(row, states)
        ]

    # Frost

    def _frost_nights(self, planting: Planting, frost: str) -> list[Night]:
        greenhouse = bool(planting.space and planting.space.type == SPACE_GREENHOUSE)
        limit = harm_limit(frost, greenhouse)
        if limit is None:
            return []
        return frosty_nights(self.forecast, limit, self.clock.today())

    def next_frost(self) -> Night | None:
        """The first frosty night of the coming week, in the open."""
        nights = frosty_nights(self.forecast, 0.0, self.clock.today())
        return nights[0] if nights else None

    def _frost_out(self, night: Night) -> dict[str, Any]:
        return {"day": night.day.isoformat(), "low": night.low}

    def _held(self, planting: Planting, task: Task) -> Night | None:
        """The last frosty night that puts off this starting step."""
        frost = planting.species.frost
        if frost not in HELD_KINDS.get(task.kind, ()):
            return None
        nights = self._frost_nights(planting, frost)
        return nights[-1] if nights else None

    def _frost_task(
        self, row: PlantingRow, planting: Planting
    ) -> dict[str, Any] | None:
        """Protect a crop standing in the open from frost in the forecast."""
        in_place = row.stage in IN_PLACE or (
            row.stage == STAGE_SOWN and row.method == METHOD_SOW_DIRECT
        )
        if not in_place:
            return None
        nights = self._frost_nights(planting, planting.species.frost)
        if not nights:
            return None
        first = nights[0]
        coldest = min(nights, key=lambda night: night.low)
        # The evening before, as forecasts date a night either way.
        due = max(self.clock.today(), first.day - timedelta(days=1))
        return {
            "uid": f"{row.id}.frost.{first.day.isoformat()}",
            "summary": self.texts(
                "frost", name=self.planting_name(row), space=self.space_name(row)
            ),
            "due": due.isoformat(),
            "description": self.texts(
                "frost_night",
                low=self.texts.temperature(coldest.low),
                day=self.texts.date(coldest.day),
            ),
            "completed": None,
            "planting_id": row.id,
            "action": None,
            "generated": True,
            "frost": self._frost_out(coldest),
        }

    def task_states(self) -> dict[str, TaskStateRow]:
        return {row.uid: row for row in self.session.scalars(select(TaskStateRow))}

    def planting_tasks(
        self, row: PlantingRow, states: dict[str, TaskStateRow] | None = None
    ) -> list[dict[str, Any]]:
        """Open tasks of a planting, however far away."""
        states = self.task_states() if states is None else states
        planting = self.planting_model(row)
        state = self.state(row)
        result = []
        for task in tasks(planting, state, schedule(planting, state, self.climate)):
            uid = f"{row.id}.{task.key}"
            if uid in states:
                continue
            due = task.due
            description = self._description(row, task)
            held = self._held(planting, task)
            if held is not None:
                due = max(due, held.day + timedelta(days=1))
                hold = self.texts(
                    "frost_hold",
                    day=self.texts.date(held.day),
                    low=self.texts.temperature(held.low),
                    until=self.texts.date(due),
                )
                description = f"{hold}\n{description}" if description else hold
            result.append(
                {
                    "uid": uid,
                    "summary": self._summary(row, task),
                    "due": due.isoformat(),
                    "description": description,
                    "completed": None,
                    "planting_id": row.id,
                    "action": task.action,
                    "generated": True,
                    "frost": self._frost_out(held) if held else None,
                }
            )
        alert = self._frost_task(row, planting)
        if alert is not None and alert["uid"] not in states:
            result.append(alert)
        return sorted(result, key=lambda task: task["due"])

    def next_task(
        self, row: PlantingRow, states: dict[str, TaskStateRow] | None = None
    ) -> dict[str, Any] | None:
        """The earliest open task of a planting."""
        open_tasks = self.planting_tasks(row, states)
        return open_tasks[0] if open_tasks else None

    def task_list(self, horizon: int = TASK_HORIZON_DAYS) -> list[dict[str, Any]]:
        """Open tasks due within `horizon` days, recent completions, own items."""
        today = self.clock.today()
        limit = (today + timedelta(days=horizon)).isoformat()
        states = self.task_states()
        result = [
            task
            for row in self.plantings(active=True)
            for task in self.planting_tasks(row, states)
            if task["due"] <= limit
        ]
        since = self.clock.now() - timedelta(days=DONE_VISIBLE_DAYS)
        for state in states.values():
            if state.status == "done" and state.at >= since:
                result.append(
                    {
                        "uid": state.uid,
                        "summary": state.summary,
                        "due": None,
                        "description": None,
                        "completed": state.at.isoformat(),
                        "planting_id": state.uid.split(".", 1)[0],
                        "action": None,
                        "generated": True,
                    }
                )
        for item in self.session.scalars(select(TodoItemRow)):
            result.append(
                {
                    "uid": item.id,
                    "summary": item.summary,
                    "due": item.due.isoformat() if item.due else None,
                    "description": item.description,
                    "completed": item.completed_at.isoformat()
                    if item.completed_at
                    else None,
                    "planting_id": None,
                    "action": None,
                    "generated": False,
                }
            )
        return sorted(
            result,
            key=lambda task: (
                task["completed"] is not None,
                task["due"] or "9999",
                task["summary"],
            ),
        )

    def _find_task(self, uid: str) -> tuple[PlantingRow, dict[str, Any]] | None:
        planting = self.session.get(PlantingRow, uid.split(".", 1)[0])
        if planting is None or planting.species not in self.catalog:
            return None
        for task in self.planting_tasks(planting):
            if task["uid"] == uid:
                return planting, task
        return None

    def complete_task(self, uid: str) -> bool:
        """Tick a generated task. Its planting moves to the next stage."""
        found = self._find_task(uid)
        if found is None:
            return False
        planting, task = found
        self.session.add(
            TaskStateRow(
                uid=uid, status="done", summary=task["summary"], at=self.clock.now()
            )
        )
        if task["action"]:
            self.set_stage(planting, task["action"])
        return True

    def reopen_task(self, uid: str) -> bool:
        """Untick a generated task. The stage is left as it is."""
        state = self.session.get(TaskStateRow, uid)
        if state is None:
            return False
        self.session.delete(state)
        return True

    def dismiss_task(self, uid: str) -> bool:
        """Hide a generated task without changing the stage."""
        found = self._find_task(uid)
        state = self.session.get(TaskStateRow, uid)
        if state is not None:
            state.status = "dismissed"
            return True
        if found is None:
            return False
        self.session.add(TaskStateRow(uid=uid, status="dismissed", at=self.clock.now()))
        return True

    # Calendar

    def calendar(self, start: date, end: date) -> list[dict[str, Any]]:
        """All-day events overlapping [start, end), end exclusive."""
        events = []
        states = self.task_states()
        for row in self.plantings():
            plan = self.schedule(row)
            name = self.planting_name(row)
            # The jobs between the periods, each on its own day.
            for task, status, day in self._steps(row, states):
                if (
                    task.kind in PERIOD_KINDS
                    or status in (STEP_DISMISSED, STEP_SKIPPED)
                    or not start <= day < end
                ):
                    continue
                summary = self.texts("event_step", label=self._label(task), name=name)
                events.append(
                    {
                        "uid": f"{row.id}.{task.key}",
                        "summary": f"\u2713 {summary}"
                        if status == STEP_DONE
                        else summary,
                        "start": day.isoformat(),
                        "end": (day + timedelta(days=1)).isoformat(),
                        "location": self.space_name(row),
                        "description": self._description(row, task),
                        "planting_id": row.id,
                        "kind": "step",
                    }
                )
            for kind, period in (
                ("sow", plan.sow),
                ("transplant", plan.transplant),
                ("harvest", plan.harvest),
            ):
                if period is None:
                    continue
                event_end = period[1] + timedelta(days=1)
                if period[0] >= end or event_end <= start:
                    continue
                events.append(
                    {
                        "uid": f"{row.id}.{kind}",
                        "summary": self.texts(f"event_{kind}", name=name),
                        "start": period[0].isoformat(),
                        "end": event_end.isoformat(),
                        "location": self.space_name(row),
                        "description": None,
                        "planting_id": row.id,
                        "kind": kind,
                    }
                )
        return sorted(events, key=lambda event: (event["start"], event["summary"]))
