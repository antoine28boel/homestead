"""A garden at runtime: its spaces, plantings, stored state and tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .catalog import Species
from .const import (
    CONF_AREA,
    CONF_FROST_SHIFT,
    CONF_METHOD,
    CONF_QUANTITY,
    CONF_SEASON,
    CONF_SPACE,
    CONF_SPACE_TYPE,
    CONF_SPECIES,
    CONF_VARIETY,
    CONF_WINDOW,
    DEFAULT_FROST_SHIFT,
    DOMAIN,
    DONE_VISIBLE_DAYS,
    STAGE_FINISHED,
    STAGE_PLANNED,
    STAGES,
    SUBENTRY_PLANTING,
    SUBENTRY_SPACE,
    TASK_HORIZON_DAYS,
)
from .models import ClimateProfile
from .planner import (
    KIND_CROP,
    KIND_PLANT,
    KIND_SOW_DIRECT,
    KIND_TRANSPLANT,
    Planting,
    PlantingState,
    Schedule,
    Space,
    Task,
    open_windows,
    schedule,
    tasks,
)
from .texts import Texts

STORAGE_VERSION = 1


@dataclass(frozen=True, slots=True)
class GardenTask:
    """A task as shown in the to-do list."""

    uid: str
    summary: str
    due: date | None
    description: str | None = None
    completed: datetime | None = None
    planting_id: str | None = None
    action: str | None = None


def planting_name(species: Species, variety: str, language: str) -> str:
    """Species name followed by the variety, such as "Tomato Moneymaker"."""
    name = species.name(language)
    return f"{name} {variety}".strip() if variety else name


def space_from_data(subentry_id: str, data: dict[str, Any]) -> Space:
    """Build a space from its subentry data."""
    shift = data.get(CONF_FROST_SHIFT)
    return Space(
        id=subentry_id,
        name=data["name"],
        type=data[CONF_SPACE_TYPE],
        frost_shift=int(
            shift if shift is not None else DEFAULT_FROST_SHIFT[data[CONF_SPACE_TYPE]]
        ),
        area=data.get(CONF_AREA),
    )


class Garden:
    """Everything a config entry knows about one garden."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        catalog: dict[str, Species],
    ) -> None:
        """Read spaces and plantings from the subentries."""
        self.hass = hass
        self.entry = entry
        self.catalog = catalog
        self.climate = ClimateProfile.from_options(dict(entry.options))
        self.texts = Texts(hass.config.language)
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._data: dict[str, Any] = {"plantings": {}, "done": {}, "items": []}
        self._listeners: list[CALLBACK_TYPE] = []

        self.spaces: dict[str, Space] = {
            subentry.subentry_id: space_from_data(
                subentry.subentry_id, dict(subentry.data)
            )
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_SPACE
        }
        self.plantings: dict[str, Planting] = {}
        for subentry in entry.subentries.values():
            if subentry.subentry_type != SUBENTRY_PLANTING:
                continue
            data = subentry.data
            if (species := catalog.get(data[CONF_SPECIES])) is None:
                continue  # removed from the catalogue
            self.plantings[subentry.subentry_id] = Planting(
                id=subentry.subentry_id,
                species=species,
                variety=data.get(CONF_VARIETY) or "",
                space=self.spaces.get(data[CONF_SPACE]),
                method=data[CONF_METHOD],
                window=data[CONF_WINDOW],
                season=data[CONF_SEASON],
                quantity=data.get(CONF_QUANTITY),
            )

    # Lifecycle

    async def async_load(self) -> None:
        """Load the stored state and forget removed plantings."""
        if stored := await self._store.async_load():
            self._data = stored
        self._data["plantings"] = {
            planting_id: state
            for planting_id, state in self._data["plantings"].items()
            if planting_id in self.plantings
        }
        self._data["done"] = {
            uid: done
            for uid, done in self._data["done"].items()
            if uid.split(".", 1)[0] in self.plantings
        }

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Refresh every entity just after midnight. Returns the stop callback."""
        return async_track_time_change(
            self.hass, self._async_new_day, hour=0, minute=0, second=5
        )

    @callback
    def _async_new_day(self, _now: datetime) -> None:
        self._notify()

    async def async_remove(self) -> None:
        """Delete the stored state of a removed garden."""
        await self._store.async_remove()

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Call `listener` whenever something changes."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    async def _async_changed(self) -> None:
        await self._store.async_save(self._data)
        self._notify()

    # Plantings

    @staticmethod
    def today() -> date:
        """Local date."""
        return dt_util.now().date()

    def planting_name(self, planting: Planting) -> str:
        """Display name of a planting."""
        return planting_name(planting.species, planting.variety, self.texts.language)

    def space_name(self, planting: Planting) -> str:
        """Name of the space of a planting."""
        return planting.space.name if planting.space else self.texts("no_space")

    def state(self, planting_id: str) -> PlantingState:
        """Stage and dates of a planting."""
        raw = self._data["plantings"].get(planting_id)
        if raw is None:
            return PlantingState()
        return PlantingState(
            stage=raw["stage"],
            dates={
                stage: date.fromisoformat(day) for stage, day in raw["dates"].items()
            },
        )

    def schedule(self, planting_id: str) -> Schedule:
        """Periods of a planting."""
        return schedule(
            self.plantings[planting_id], self.state(planting_id), self.climate
        )

    def is_active(self, planting_id: str) -> bool:
        """Whether a planting is not finished."""
        return self.state(planting_id).stage != STAGE_FINISHED

    async def async_set_stage(
        self, planting_id: str, stage: str, day: date | None = None
    ) -> None:
        """Move a planting to a stage, and forget the dates of later stages."""
        state = self.state(planting_id)
        index = STAGES.index(stage)
        dates = {
            reached: when
            for reached, when in state.dates.items()
            if STAGES.index(reached) < index
        }
        if stage != STAGE_PLANNED:
            dates[stage] = day or state.dates.get(stage) or self.today()
        self._data["plantings"][planting_id] = {
            "stage": stage,
            "dates": {reached: when.isoformat() for reached, when in dates.items()},
        }
        await self._async_changed()

    # Tasks

    def _planting_tasks(self, planting_id: str) -> list[Task]:
        planting = self.plantings[planting_id]
        state = self.state(planting_id)
        return tasks(planting, state, schedule(planting, state, self.climate))

    def _summary(self, planting: Planting, task: Task) -> str:
        values = {
            "name": self.planting_name(planting),
            "space": self.space_name(planting),
        }
        if task.kind == KIND_CROP:
            assert task.label
            return self.texts(task.kind, label=self.texts.label(task.label), **values)
        return self.texts(task.kind, **values)

    def _description(self, planting: Planting, task: Task) -> str | None:
        lines = []
        if task.period:
            lines.append(
                self.texts(
                    "period",
                    start=self.texts.date(task.period[0]),
                    end=self.texts.date(task.period[1]),
                )
            )
        spacing = planting.species.spacing_cm
        if spacing and task.kind in (KIND_SOW_DIRECT, KIND_PLANT, KIND_TRANSPLANT):
            lines.append(self.texts("spacing", plant=spacing[0], row=spacing[1]))
        return "\n".join(lines) or None

    def next_task(self, planting_id: str) -> GardenTask | None:
        """The earliest open task of a planting, however far away."""
        open_tasks = [
            task
            for task in self.tasks(horizon=None)
            if task.planting_id == planting_id and task.completed is None
        ]
        return min(open_tasks, key=lambda task: task.due or date.max, default=None)

    def tasks(self, horizon: int | None = TASK_HORIZON_DAYS) -> list[GardenTask]:
        """Open tasks due within `horizon` days, recent completions, own items."""
        today = self.today()
        done = self._data["done"]
        result: list[GardenTask] = []
        for planting_id, planting in self.plantings.items():
            for task in self._planting_tasks(planting_id):
                uid = f"{planting_id}.{task.key}"
                if uid in done:
                    continue
                if horizon is not None and task.due > today + timedelta(days=horizon):
                    continue
                result.append(
                    GardenTask(
                        uid=uid,
                        summary=self._summary(planting, task),
                        due=task.due,
                        description=self._description(planting, task),
                        planting_id=planting_id,
                        action=task.action,
                    )
                )
        if horizon is None:
            return result

        since = dt_util.now() - timedelta(days=DONE_VISIBLE_DAYS)
        for uid, record in done.items():
            if record.get("dismissed"):
                continue
            completed = datetime.fromisoformat(record["completed"])
            if completed >= since:
                result.append(
                    GardenTask(
                        uid=uid,
                        summary=record["summary"],
                        due=None,
                        completed=completed,
                        planting_id=uid.split(".", 1)[0],
                    )
                )
        for item in self._data["items"]:
            result.append(
                GardenTask(
                    uid=item["uid"],
                    summary=item["summary"],
                    due=date.fromisoformat(item["due"]) if item.get("due") else None,
                    description=item.get("description"),
                    completed=datetime.fromisoformat(item["completed"])
                    if item.get("completed")
                    else None,
                )
            )
        return result

    def _find(self, uid: str) -> GardenTask | None:
        return next(
            (task for task in self.tasks(horizon=None) if task.uid == uid), None
        )

    async def async_complete_task(self, uid: str) -> None:
        """Tick a generated task. Its planting moves to the next stage."""
        task = self._find(uid)
        if task is None:
            return
        self._data["done"][uid] = {
            "summary": task.summary,
            "completed": dt_util.now().isoformat(),
        }
        if task.action and task.planting_id:
            await self.async_set_stage(task.planting_id, task.action)
        else:
            await self._async_changed()

    async def async_reopen_task(self, uid: str) -> None:
        """Untick a generated task. The stage is left as it is."""
        if self._data["done"].pop(uid, None) is not None:
            await self._async_changed()

    async def async_dismiss_tasks(self, uids: list[str]) -> None:
        """Hide generated tasks, or delete own items."""
        items = self._data["items"]
        self._data["items"] = [item for item in items if item["uid"] not in uids]
        for uid in uids:
            if uid.split(".", 1)[0] in self.plantings:
                self._data["done"][uid] = {
                    "summary": "",
                    "completed": dt_util.now().isoformat(),
                    "dismissed": True,
                }
        await self._async_changed()

    def is_generated(self, uid: str) -> bool:
        """Whether a to-do item comes from a planting."""
        return uid.split(".", 1)[0] in self.plantings

    async def async_add_item(
        self, summary: str, due: date | None, description: str | None
    ) -> None:
        """Add an own item to the to-do list."""
        self._data["items"].append(
            {
                "uid": uuid.uuid4().hex,
                "summary": summary,
                "due": due.isoformat() if due else None,
                "description": description,
                "completed": None,
            }
        )
        await self._async_changed()

    async def async_update_item(
        self,
        uid: str,
        summary: str,
        due: date | None,
        description: str | None,
        completed: bool,
    ) -> None:
        """Change an own item of the to-do list."""
        for item in self._data["items"]:
            if item["uid"] == uid:
                was_completed = item.get("completed")
                item.update(
                    summary=summary,
                    due=due.isoformat() if due else None,
                    description=description,
                    completed=(was_completed or dt_util.now().isoformat())
                    if completed
                    else None,
                )
        await self._async_changed()

    # Spaces

    def space_plantings(self, space_id: str) -> list[Planting]:
        """Active plantings of a space."""
        return [
            planting
            for planting in self.plantings.values()
            if planting.space
            and planting.space.id == space_id
            and self.is_active(planting.id)
        ]

    def sow_now(self, space_id: str) -> dict[str, list[str]]:
        """Species that can be started now for this space, by method."""
        space = self.spaces[space_id]
        today = self.today()
        result: dict[str, list[str]] = {}
        for species in self.catalog.values():
            for method in open_windows(species, self.climate, space.frost_shift, today):
                result.setdefault(method, []).append(species.name(self.texts.language))
        return {method: sorted(names) for method, names in result.items()}
