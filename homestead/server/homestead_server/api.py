"""The web server: REST API, WebSocket notices and the web interface."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator, MutableMapping
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime, time, timedelta
from http.cookies import SimpleCookie
import json
import logging
from pathlib import Path
import secrets
from typing import Annotated, Any
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
)
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import __version__
from .catalog import Species, load_catalog
from .config import INGRESS_IP, Settings
from .const import (
    BACKGROUND_TYPES,
    DEFAULT_FROST_SHIFT,
    HARVEST_UNITS,
    JOURNAL_KINDS,
    MAX_BACKGROUND_BYTES,
    PLAN_ITEM_KINDS,
    SHAPES,
    STAGE_HARVESTING,
    STAGE_PLANNED,
    STAGES,
    TASK_HORIZON_DAYS,
)
from .db import make_engine, make_sessions, migrate
from .events import Events
from .garden import Clock, Garden, ensure_garden, is_generated
from .ha import announce, fetch_config
from .layout import DIRECTIONS, LAYOUTS
from .models import MonthDay
from .orm import (
    GardenRow,
    HarvestRow,
    JournalRow,
    PlanItemRow,
    PlantingRow,
    SpaceRow,
    TaskStateRow,
    TodoItemRow,
)
from .plan import item_out, plan_out, space_area
from .planner import next_season
from .texts import Texts

_LOGGER = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
TOKEN_COOKIE = "homestead_token"
# Reachable without a token: health checks and the token login page.
OPEN_PATHS = ("/api/health", "/login")
# Calendar events sent with the summary, for the calendar's current event.
SUMMARY_EVENT_DAYS = 400

ASGIApp = Callable[
    [MutableMapping[str, Any], Callable[[], Awaitable[Any]], Callable[..., Any]],
    Awaitable[None],
]


class TokenGuard:
    """Lets through ingress requests, or requests carrying the API token.

    As a Home Assistant app, the Supervisor authenticates ingress users and
    proxies them from a fixed address; anything else (the companion
    integration) needs the token. A stand-alone server is open unless told
    otherwise.
    """

    def __init__(self, app: ASGIApp, settings: Settings, token: str) -> None:
        """Wrap the application."""
        self.app = app
        self.settings = settings
        self.token = token

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[Any]],
        send: Callable[..., Any],
    ) -> None:
        """Check the request, then pass it on or refuse it."""
        if scope["type"] not in ("http", "websocket") or self.allowed(scope):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await receive()
            await send({"type": "websocket.close", "code": 4401})
            return
        response = JSONResponse({"detail": "Unauthorized"}, status_code=401)
        await response(scope, receive, send)

    def allowed(self, scope: MutableMapping[str, Any]) -> bool:
        """Whether this request may go through."""
        if scope["path"] in OPEN_PATHS:
            return True
        if self.settings.app_mode:
            client = scope.get("client")
            if client and client[0] == INGRESS_IP:
                return True
        # A token, when given, must be right, even where none is required:
        # the integration can then tell a wrong token from a right one.
        if given := self.given_token(scope):
            return secrets.compare_digest(given, self.token)
        return not self.settings.app_mode and not self.settings.require_token

    @staticmethod
    def given_token(scope: MutableMapping[str, Any]) -> str:
        """The token of the request, from its header or its cookie."""
        headers = {
            key.decode("latin-1"): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        given = headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not given and "cookie" in headers:
            cookie = SimpleCookie(headers["cookie"]).get(TOKEN_COOKIE)
            given = cookie.value if cookie else ""
        return given


# Request inputs


def _one_of(value: str | None, allowed: tuple[str, ...] | list[str]) -> str | None:
    if value is not None and value not in allowed:
        raise ValueError(f"must be one of {', '.join(allowed)}")
    return value


def _month_day(value: str | None) -> str | None:
    return None if value is None else str(MonthDay.parse(value))


class GardenIn(BaseModel):
    """Garden settings."""

    name: str | None = Field(None, min_length=1, max_length=100)
    last_frost: str | None = None
    first_frost: str | None = None

    _frost = field_validator("last_frost", "first_frost")(_month_day)


class SpaceIn(BaseModel):
    """A new space, or changes to one."""

    name: str | None = Field(None, min_length=1, max_length=100)
    type: str | None = None
    frost_shift: int | None = Field(None, ge=-8, le=16)
    area: float | None = Field(None, ge=0)
    sort: int | None = None
    archived: bool | None = None
    x: float | None = Field(None, ge=-1000, le=1000)
    y: float | None = Field(None, ge=-1000, le=1000)
    width: float | None = Field(None, gt=0, le=1000)
    height: float | None = Field(None, gt=0, le=1000)
    rotation: float | None = Field(None, ge=-360, le=360)
    shape: str | None = None

    @field_validator("type")
    @classmethod
    def _type(cls, value: str | None) -> str | None:
        return _one_of(value, tuple(DEFAULT_FROST_SHIFT))

    @field_validator("shape")
    @classmethod
    def _shape(cls, value: str | None) -> str | None:
        return _one_of(value, SHAPES)


# Fields that a null clears, rather than leaves unchanged.
SPACE_CLEARABLE = ("frost_shift", "x", "y", "width", "height")
PLACEMENT_FIELDS = (
    "layout",
    "region_x",
    "region_y",
    "region_width",
    "region_height",
    "spacing",
    "row_spacing",
    "points",
)


class PlantingIn(BaseModel):
    """A new planting, or changes to one."""

    species: str | None = None
    space_id: str | None = None
    method: str | None = None
    window: int | None = Field(None, ge=0)
    season: int | None = Field(None, ge=1900, le=2200)
    variety: str | None = Field(None, max_length=100)
    quantity: int | None = Field(None, ge=1)
    notes: str | None = None
    layout: str | None = None
    region_x: float | None = Field(None, ge=0, le=1000)
    region_y: float | None = Field(None, ge=0, le=1000)
    region_width: float | None = Field(None, gt=0, le=1000)
    region_height: float | None = Field(None, gt=0, le=1000)
    spacing: float | None = Field(None, gt=0, le=1000)
    """Centimetres."""
    row_spacing: float | None = Field(None, gt=0, le=1000)
    direction: str | None = None
    points: list[tuple[float, float]] | None = Field(None, max_length=1000)

    @field_validator("layout")
    @classmethod
    def _layout(cls, value: str | None) -> str | None:
        return _one_of(value, LAYOUTS)

    @field_validator("direction")
    @classmethod
    def _direction(cls, value: str | None) -> str | None:
        return _one_of(value, DIRECTIONS)


class PlanIn(BaseModel):
    """Plan settings. A null size follows the background or the objects."""

    width: float | None = Field(None, gt=0, le=2000)
    height: float | None = Field(None, gt=0, le=2000)
    background_scale: float | None = Field(None, gt=0, le=100)
    """Metres per pixel of the background."""
    background_opacity: float | None = Field(None, ge=0, le=1)


class PlanItemIn(BaseModel):
    """A new object of the plan, or changes to one."""

    kind: str | None = None
    label: str | None = Field(None, max_length=100)
    x: float | None = Field(None, ge=-1000, le=1000)
    y: float | None = Field(None, ge=-1000, le=1000)
    width: float | None = Field(None, gt=0, le=1000)
    height: float | None = Field(None, gt=0, le=1000)
    rotation: float | None = Field(None, ge=-360, le=360)
    sort: int | None = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str | None) -> str | None:
        return _one_of(value, PLAN_ITEM_KINDS)


class StageIn(BaseModel):
    """Move a planting to a stage."""

    stage: str
    day: date | None = None

    @field_validator("stage")
    @classmethod
    def _stage(cls, value: str) -> str:
        _one_of(value, STAGES)
        return value


class JournalIn(BaseModel):
    """Something done or seen."""

    planting_id: str | None = None
    space_id: str | None = None
    kind: str = "observation"
    day: date | None = None
    note: str = ""
    amount: float | None = None
    unit: str | None = Field(None, max_length=20)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        _one_of(value, JOURNAL_KINDS)
        return value


class HarvestIn(BaseModel):
    """A harvest."""

    planting_id: str
    day: date | None = None
    quantity: float = Field(gt=0)
    unit: str = "kg"
    note: str = ""

    @field_validator("unit")
    @classmethod
    def _unit(cls, value: str) -> str:
        _one_of(value, HARVEST_UNITS)
        return value


class TaskIn(BaseModel):
    """An item of the to-do list, or changes to one."""

    summary: str | None = Field(None, min_length=1, max_length=255)
    due: date | None = None
    description: str | None = None
    completed: bool | None = None


# Dependencies


def _session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


SessionDep = Annotated[Session, Depends(_session)]


def _garden(request: Request, session: SessionDep) -> Garden:
    state = request.app.state
    return Garden(session, state.catalog, state.texts, state.clock)


GardenDep = Annotated[Garden, Depends(_garden)]


def _save(request: Request, session: Session) -> None:
    """Commit, then tell clients."""
    session.commit()
    request.app.state.events.notify()


def _get[T](session: Session, model: type[T], ident: str) -> T:
    row = session.get(model, ident)
    if row is None:
        raise HTTPException(404, f"{model.__name__.removesuffix('Row')} not found")
    return row


def _species(garden: Garden, species_id: str) -> Species:
    species = garden.catalog.get(species_id)
    if species is None:
        raise HTTPException(422, f"Unknown species: {species_id}")
    return species


# Outputs


def garden_out(row: GardenRow) -> dict[str, Any]:
    """Garden settings."""
    return {
        "name": row.name,
        "last_frost": row.last_frost,
        "first_frost": row.first_frost,
    }


def space_out(row: SpaceRow) -> dict[str, Any]:
    """A space."""
    return {
        "id": row.id,
        "name": row.name,
        "type": row.type,
        "frost_shift": row.frost_shift,
        "effective_frost_shift": Garden.space_model(row).frost_shift,
        "area": row.area,
        "surface": space_area(row),
        "sort": row.sort,
        "archived": row.archived,
        "placed": row.placed,
    }


def species_out(species: Species, language: str) -> dict[str, Any]:
    """A crop of the catalogue."""
    return {
        "id": species.id,
        "name": species.name(language),
        "family": species.family,
        "frost": species.frost,
        "methods": species.methods,
        "spacing_cm": species.spacing_cm,
        "germination_days": species.germination_days,
    }


def _period(period: tuple[date, date] | None) -> list[str] | None:
    return [period[0].isoformat(), period[1].isoformat()] if period else None


def _totals(harvests: list[HarvestRow]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for harvest in harvests:
        totals[harvest.unit] = round(totals.get(harvest.unit, 0) + harvest.quantity, 3)
    return totals


def planting_out(
    garden: Garden,
    row: PlantingRow,
    states: dict[str, TaskStateRow] | None = None,
) -> dict[str, Any]:
    """A planting with its schedule and next task."""
    plan = garden.schedule(row)
    return {
        "id": row.id,
        "season": row.season,
        "species": row.species,
        "species_name": garden.catalog[row.species].name(garden.texts.language),
        "variety": row.variety,
        "name": garden.planting_name(row),
        "space_id": row.space_id,
        "space_name": garden.space_name(row),
        "method": row.method,
        "window": row.window,
        "quantity": row.quantity,
        "stage": row.stage,
        "dates": {stage: day.isoformat() for stage, day in row.stage_dates().items()},
        "notes": row.notes,
        "schedule": {
            "sow": _period(plan.sow),
            "transplant": _period(plan.transplant),
            "harvest": _period(plan.harvest),
        },
        "next_task": garden.next_task(row, states),
        "harvested": _totals(row.harvests),
    }


def journal_out(row: JournalRow) -> dict[str, Any]:
    """A journal entry."""
    return {
        "id": row.id,
        "planting_id": row.planting_id,
        "space_id": row.space_id,
        "kind": row.kind,
        "day": row.day.isoformat(),
        "note": row.note,
        "amount": row.amount,
        "unit": row.unit,
    }


def harvest_out(row: HarvestRow) -> dict[str, Any]:
    """A harvest."""
    return {
        "id": row.id,
        "planting_id": row.planting_id,
        "day": row.day.isoformat(),
        "quantity": row.quantity,
        "unit": row.unit,
        "note": row.note,
    }


# Routes

api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}


@api.get("/info")
def info(request: Request, garden: GardenDep) -> dict[str, Any]:
    """Version and settings, for the web interface and the integration."""
    state = request.app.state
    return {
        "version": __version__,
        "instance_id": state.instance_id,
        "app_mode": state.settings.app_mode,
        "language": state.texts.language,
        "time_zone": state.ha_config["time_zone"],
        "today": garden.clock.today().isoformat(),
        "garden": garden.row.name,
        "species": len(garden.catalog),
        "stages": STAGES,
        "space_types": list(DEFAULT_FROST_SHIFT),
        "journal_kinds": JOURNAL_KINDS,
        "harvest_units": HARVEST_UNITS,
        "plan_item_kinds": PLAN_ITEM_KINDS,
        "layouts": LAYOUTS,
    }


@api.get("/garden")
def get_garden(garden: GardenDep) -> dict[str, Any]:
    """Garden settings."""
    return garden_out(garden.row)


@api.put("/garden")
def put_garden(
    body: GardenIn, request: Request, session: SessionDep, garden: GardenDep
) -> dict[str, Any]:
    """Change the garden settings."""
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(garden.row, key, value)
    _save(request, session)
    return garden_out(garden.row)


@api.get("/catalog")
def catalog(garden: GardenDep) -> list[dict[str, Any]]:
    """Every crop of the catalogue."""
    language = garden.texts.language
    return sorted(
        (species_out(species, language) for species in garden.catalog.values()),
        key=lambda species: species["name"],
    )


@api.get("/catalog/{species_id}/starts")
def starts(
    species_id: str, space_id: str, session: SessionDep, garden: GardenDep
) -> list[dict[str, Any]]:
    """Ways and windows to start a crop in a space."""
    species = garden.catalog.get(species_id)
    if species is None:
        raise HTTPException(404, "Species not found")
    return garden.start_options(species, _get(session, SpaceRow, space_id))


@api.get("/spaces")
def spaces(garden: GardenDep, archived: bool = False) -> list[dict[str, Any]]:
    """Spaces in display order."""
    return [space_out(row) for row in garden.spaces(include_archived=archived)]


@api.post("/spaces", status_code=201)
def create_space(
    body: SpaceIn, request: Request, session: SessionDep
) -> dict[str, Any]:
    """Add a space."""
    if not body.name or not body.type:
        raise HTTPException(422, "name and type are required")
    row = SpaceRow(**body.model_dump(exclude_none=True))
    session.add(row)
    _save(request, session)
    return space_out(row)


@api.patch("/spaces/{space_id}")
def update_space(
    space_id: str, body: SpaceIn, request: Request, session: SessionDep
) -> dict[str, Any]:
    """Change a space. A null frost_shift goes back to the type's default."""
    row = _get(session, SpaceRow, space_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is None and key not in SPACE_CLEARABLE:
            continue
        setattr(row, key, value)
    _save(request, session)
    return space_out(row)


@api.delete("/spaces/{space_id}")
def delete_space(space_id: str, request: Request, session: SessionDep) -> Response:
    """Remove a space. One that has plantings is archived to keep the history."""
    row = _get(session, SpaceRow, space_id)
    used = session.scalar(select(func.count()).where(PlantingRow.space_id == space_id))
    if used:
        row.archived = True
        _save(request, session)
        return JSONResponse(space_out(row))
    session.delete(row)
    _save(request, session)
    return Response(status_code=204)


@api.get("/spaces/{space_id}/sow-now")
def sow_now(
    space_id: str, session: SessionDep, garden: GardenDep
) -> dict[str, list[dict[str, str]]]:
    """Crops that can be started in this space today."""
    return garden.sow_now(_get(session, SpaceRow, space_id))


@api.get("/sow-now")
def sow_now_all(garden: GardenDep) -> list[dict[str, Any]]:
    """Crops that can be started today, space by space."""
    return [
        {"space_id": row.id, "space_name": row.name, "methods": garden.sow_now(row)}
        for row in garden.spaces()
    ]


@api.get("/plantings")
def plantings(
    garden: GardenDep,
    season: int | None = None,
    active: bool | None = None,
    species: str | None = None,
    space_id: str | None = None,
) -> list[dict[str, Any]]:
    """Plantings, newest season first."""
    states = garden.task_states()
    return [
        planting_out(garden, row, states)
        for row in garden.plantings(
            season=season, active=active, species=species, space_id=space_id
        )
    ]


@api.post("/plantings", status_code=201)
def create_planting(
    body: PlantingIn, request: Request, session: SessionDep, garden: GardenDep
) -> dict[str, Any]:
    """Plan a planting. Method, window and season default to the next start."""
    if not body.species:
        raise HTTPException(422, "species is required")
    species = _species(garden, body.species)
    space = _get(session, SpaceRow, body.space_id) if body.space_id else None
    method = body.method or (species.methods[0] if species.methods else None)
    if method not in species.methods:
        raise HTTPException(422, f"{species.id} cannot be started with {method}")
    windows = species.windows(method)
    window = min(body.window or 0, len(windows) - 1)
    season = body.season
    if season is None:
        shift = garden.space_model(space).frost_shift if space else 0
        season = next_season(
            windows[window], garden.climate, shift, garden.clock.today()
        )
    row = PlantingRow(
        species=species.id,
        space_id=space.id if space else None,
        method=method,
        window=window,
        season=season,
        variety=body.variety or "",
        quantity=body.quantity,
        notes=body.notes or "",
        stage=STAGE_PLANNED,
    )
    session.add(row)
    _save(request, session)
    return planting_out(garden, row)


@api.get("/plantings/{planting_id}")
def planting(
    planting_id: str, session: SessionDep, garden: GardenDep
) -> dict[str, Any]:
    """A planting with its tasks, journal, harvests and earlier seasons."""
    row = _get(session, PlantingRow, planting_id)
    if row.species not in garden.catalog:
        raise HTTPException(404, "Species no longer in the catalogue")
    result = planting_out(garden, row)
    result["tasks"] = garden.planting_tasks(row)
    result["journal"] = [
        journal_out(entry)
        for entry in sorted(row.journal, key=lambda entry: entry.day, reverse=True)
    ]
    result["harvests"] = [
        harvest_out(entry)
        for entry in sorted(row.harvests, key=lambda entry: entry.day, reverse=True)
    ]
    result["history"] = [
        {
            "id": other.id,
            "season": other.season,
            "name": garden.planting_name(other),
            "space_name": garden.space_name(other),
            "stage": other.stage,
            "dates": {
                stage: day.isoformat() for stage, day in other.stage_dates().items()
            },
            "harvested": _totals(other.harvests),
        }
        for other in garden.plantings(species=row.species)
        if other.id != row.id
    ]
    return result


@api.patch("/plantings/{planting_id}")
def update_planting(
    planting_id: str,
    body: PlantingIn,
    request: Request,
    session: SessionDep,
    garden: GardenDep,
) -> dict[str, Any]:
    """Change a planting. Its species cannot change."""
    row = _get(session, PlantingRow, planting_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.pop("species", row.species) != row.species:
        raise HTTPException(422, "The species of a planting cannot change")
    species = _species(garden, row.species)
    if changes.get("space_id") is not None:
        _get(session, SpaceRow, changes["space_id"])
    method = changes.get("method") or row.method
    if method not in species.methods:
        raise HTTPException(422, f"{species.id} cannot be started with {method}")
    if changes.get("points") is not None:
        changes["points"] = json.dumps([list(point) for point in changes["points"]])
    if changes.get("space_id", row.space_id) != row.space_id:
        for key in ("region_x", "region_y", "region_width", "region_height"):
            changes.setdefault(key, None)
    for key, value in changes.items():
        if value is None and key not in ("space_id", "quantity", *PLACEMENT_FIELDS):
            continue
        setattr(row, key, value)
    row.window = min(row.window, len(species.windows(row.method)) - 1)
    _save(request, session)
    return planting_out(garden, row)


@api.delete("/plantings/{planting_id}", status_code=204)
def delete_planting(planting_id: str, request: Request, session: SessionDep) -> None:
    """Delete a planting with its journal and harvests."""
    session.delete(_get(session, PlantingRow, planting_id))
    session.execute(
        TaskStateRow.__table__.delete().where(
            TaskStateRow.uid.startswith(f"{planting_id}.")
        )
    )
    _save(request, session)


@api.post("/plantings/{planting_id}/stage")
def set_stage(
    planting_id: str,
    body: StageIn,
    request: Request,
    session: SessionDep,
    garden: GardenDep,
) -> dict[str, Any]:
    """Move a planting to a stage, on a given day or today."""
    row = _get(session, PlantingRow, planting_id)
    garden.set_stage(row, body.stage, body.day)
    _save(request, session)
    return planting_out(garden, row)


@api.get("/journal")
def journal(
    session: SessionDep,
    planting_id: str | None = None,
    space_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[dict[str, Any]]:
    """Latest journal entries."""
    query = select(JournalRow).order_by(JournalRow.day.desc(), JournalRow.created_at)
    if planting_id:
        query = query.where(JournalRow.planting_id == planting_id)
    if space_id:
        query = query.where(JournalRow.space_id == space_id)
    return [journal_out(row) for row in session.scalars(query.limit(limit))]


@api.post("/journal", status_code=201)
def add_journal(
    body: JournalIn, request: Request, session: SessionDep, garden: GardenDep
) -> dict[str, Any]:
    """Write in the journal of a planting, a space or the whole garden."""
    space_id = body.space_id
    if body.planting_id:
        planting = _get(session, PlantingRow, body.planting_id)
        space_id = space_id or planting.space_id
    if space_id:
        _get(session, SpaceRow, space_id)
    row = JournalRow(
        **body.model_dump(exclude={"space_id", "day"}),
        space_id=space_id,
        day=body.day or garden.clock.today(),
    )
    session.add(row)
    _save(request, session)
    return journal_out(row)


@api.delete("/journal/{entry_id}", status_code=204)
def delete_journal(entry_id: str, request: Request, session: SessionDep) -> None:
    """Delete a journal entry."""
    session.delete(_get(session, JournalRow, entry_id))
    _save(request, session)


@api.get("/harvests")
def harvests(
    session: SessionDep, planting_id: str | None = None, season: int | None = None
) -> list[dict[str, Any]]:
    """Harvests, latest first."""
    query = select(HarvestRow).order_by(HarvestRow.day.desc(), HarvestRow.created_at)
    if planting_id:
        query = query.where(HarvestRow.planting_id == planting_id)
    if season is not None:
        query = query.join(PlantingRow).where(PlantingRow.season == season)
    return [harvest_out(row) for row in session.scalars(query)]


@api.post("/harvests", status_code=201)
def add_harvest(
    body: HarvestIn, request: Request, session: SessionDep, garden: GardenDep
) -> dict[str, Any]:
    """Log a harvest. The first one moves the planting to harvesting."""
    planting = _get(session, PlantingRow, body.planting_id)
    day = body.day or garden.clock.today()
    if STAGES.index(planting.stage) < STAGES.index(STAGE_HARVESTING):
        garden.set_stage(planting, STAGE_HARVESTING, day)
    row = HarvestRow(**body.model_dump(exclude={"day"}), day=day)
    session.add(row)
    _save(request, session)
    return harvest_out(row)


@api.delete("/harvests/{harvest_id}", status_code=204)
def delete_harvest(harvest_id: str, request: Request, session: SessionDep) -> None:
    """Delete a harvest."""
    session.delete(_get(session, HarvestRow, harvest_id))
    _save(request, session)


def _plan_items(session: Session) -> list[PlanItemRow]:
    query = select(PlanItemRow).order_by(PlanItemRow.sort, PlanItemRow.created_at)
    return list(session.scalars(query))


def _background_dir(request: Request) -> Path:
    return request.app.state.settings.data_dir / "plan"


@api.get("/plan")
def plan(session: SessionDep, garden: GardenDep) -> dict[str, Any]:
    """Spaces and objects drawn, background, and where every plant goes."""
    return plan_out(garden, _plan_items(session))


@api.put("/plan")
def put_plan(
    body: PlanIn, request: Request, session: SessionDep, garden: GardenDep
) -> dict[str, Any]:
    """Change the size of the plan or the scale of its background."""
    row = garden.row
    changes = body.model_dump(exclude_unset=True)
    if "width" in changes or "height" in changes:
        row.plan_width = changes.get("width")
        row.plan_height = changes.get("height")
    if "background_scale" in changes:
        row.background_scale = changes["background_scale"]
    if changes.get("background_opacity") is not None:
        row.background_opacity = changes["background_opacity"]
    _save(request, session)
    return plan_out(garden, _plan_items(session))


@api.put("/plan/background")
async def put_background(
    request: Request,
    session: SessionDep,
    garden: GardenDep,
    width: Annotated[int, Query(gt=0, le=20000)],
    height: Annotated[int, Query(gt=0, le=20000)],
) -> dict[str, Any]:
    """Set the aerial view or drone photo: the image is the body of the request.

    The interface sends the pixel size it read. A new image of the same width
    keeps the scale, as for a new photo of the same place.
    """
    kind = request.headers.get("content-type", "").split(";")[0].strip()
    if kind not in BACKGROUND_TYPES:
        raise HTTPException(415, "Send a JPEG, PNG or WebP image")
    data = await request.body()
    if not data:
        raise HTTPException(422, "The image is empty")
    if len(data) > MAX_BACKGROUND_BYTES:
        raise HTTPException(413, "The image is too large")
    folder = _background_dir(request)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"background-{secrets.token_hex(6)}.{BACKGROUND_TYPES[kind]}"
    await asyncio.to_thread((folder / name).write_bytes, data)
    row = garden.row
    old = row.background
    if row.background_width != width:
        row.background_scale = None
    row.background, row.background_width, row.background_height = name, width, height
    _save(request, session)
    if old:
        (folder / old).unlink(missing_ok=True)
    return plan_out(garden, _plan_items(session))


@api.delete("/plan/background")
def delete_background(
    request: Request, session: SessionDep, garden: GardenDep
) -> dict[str, Any]:
    """Remove the background."""
    row = garden.row
    old = row.background
    row.background = row.background_width = row.background_height = None
    row.background_scale = None
    _save(request, session)
    if old:
        (_background_dir(request) / old).unlink(missing_ok=True)
    return plan_out(garden, _plan_items(session))


@api.get("/plan/background/{name}")
def background(name: str, request: Request, garden: GardenDep) -> FileResponse:
    """The background image. Its name changes with it, so it can be cached."""
    if name != garden.row.background:
        raise HTTPException(404, "Background not found")
    return FileResponse(
        _background_dir(request) / name,
        headers={"Cache-Control": "max-age=31536000, immutable"},
    )


@api.post("/plan/items", status_code=201)
def create_item(
    body: PlanItemIn, request: Request, session: SessionDep
) -> dict[str, Any]:
    """Draw an object that is not grown: lawn, path, tree…"""
    values = body.model_dump(exclude_none=True)
    missing = [
        key for key in ("kind", "x", "y", "width", "height") if key not in values
    ]
    if missing:
        raise HTTPException(422, f"{', '.join(missing)} required")
    row = PlanItemRow(**values)
    session.add(row)
    _save(request, session)
    return item_out(row)


@api.patch("/plan/items/{item_id}")
def update_item(
    item_id: str, body: PlanItemIn, request: Request, session: SessionDep
) -> dict[str, Any]:
    """Move, resize or rename an object."""
    row = _get(session, PlanItemRow, item_id)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(row, key, value)
    _save(request, session)
    return item_out(row)


@api.delete("/plan/items/{item_id}", status_code=204)
def delete_item(item_id: str, request: Request, session: SessionDep) -> None:
    """Remove an object."""
    session.delete(_get(session, PlanItemRow, item_id))
    _save(request, session)


@api.get("/tasks")
def task_list(
    garden: GardenDep,
    horizon: Annotated[int, Query(ge=0, le=366)] = TASK_HORIZON_DAYS,
) -> list[dict[str, Any]]:
    """The to-do list: tasks due soon, recent completions, own items."""
    return garden.task_list(horizon)


@api.post("/tasks", status_code=201)
def add_task(
    body: TaskIn, request: Request, session: SessionDep, garden: GardenDep
) -> dict[str, Any]:
    """Add an own item to the to-do list."""
    if not body.summary:
        raise HTTPException(422, "summary is required")
    row = TodoItemRow(summary=body.summary, due=body.due, description=body.description)
    if body.completed:
        row.completed_at = garden.clock.now()
    session.add(row)
    _save(request, session)
    return {"uid": row.id}


@api.patch("/tasks/{uid}")
def update_task(
    uid: str, body: TaskIn, request: Request, session: SessionDep, garden: GardenDep
) -> dict[str, Any]:
    """Change an item. Generated tasks can only be ticked or unticked."""
    if is_generated(uid):
        if body.completed is True and session.get(TaskStateRow, uid) is None:
            if not garden.complete_task(uid):
                raise HTTPException(404, "Task not found")
        elif body.completed is False:
            garden.reopen_task(uid)
        _save(request, session)
        return {"uid": uid}
    row = _get(session, TodoItemRow, uid)
    changes = body.model_dump(exclude_unset=True)
    completed = changes.pop("completed", None)
    for key, value in changes.items():
        if value is None and key == "summary":
            continue
        setattr(row, key, value)
    if completed is not None:
        row.completed_at = garden.clock.now() if completed else None
    _save(request, session)
    return {"uid": uid}


@api.delete("/tasks/{uid}", status_code=204)
def delete_task(
    uid: str, request: Request, session: SessionDep, garden: GardenDep
) -> None:
    """Remove an own item, or hide a generated task."""
    if is_generated(uid):
        if not garden.dismiss_task(uid):
            raise HTTPException(404, "Task not found")
    else:
        session.delete(_get(session, TodoItemRow, uid))
    _save(request, session)


@api.get("/calendar")
def calendar(garden: GardenDep, start: date, end: date) -> list[dict[str, Any]]:
    """Sowing, planting and harvest periods overlapping [start, end)."""
    if end <= start:
        raise HTTPException(422, "end must be after start")
    return garden.calendar(start, end)


@api.get("/seasons")
def seasons(session: SessionDep) -> list[dict[str, Any]]:
    """Seasons with their number of plantings and harvest totals."""
    counts = session.execute(
        select(PlantingRow.season, func.count())
        .group_by(PlantingRow.season)
        .order_by(PlantingRow.season.desc())
    ).all()
    totals: dict[int, dict[str, float]] = {}
    for season, unit, quantity in session.execute(
        select(PlantingRow.season, HarvestRow.unit, func.sum(HarvestRow.quantity))
        .join(PlantingRow)
        .group_by(PlantingRow.season, HarvestRow.unit)
    ):
        totals.setdefault(season, {})[unit] = round(quantity, 3)
    return [
        {"season": season, "plantings": count, "harvested": totals.get(season, {})}
        for season, count in counts
    ]


@api.get("/summary")
def summary(request: Request, session: SessionDep, garden: GardenDep) -> dict[str, Any]:
    """Everything the companion integration shows, in one request."""
    states = garden.task_states()
    today = garden.clock.today()
    return {
        "version": __version__,
        "instance_id": request.app.state.instance_id,
        "today": today.isoformat(),
        "garden": garden_out(garden.row),
        "spaces": [space_out(row) for row in garden.spaces()],
        "plantings": [
            planting_out(garden, row, states) for row in garden.plantings(active=True)
        ],
        "tasks": garden.task_list(),
        "events": garden.calendar(today, today + timedelta(days=SUMMARY_EVENT_DAYS)),
        "sow_now": {row.id: garden.sow_now(row) for row in garden.spaces()},
        "stages": STAGES,
        "plan": plan_out(garden, _plan_items(session), with_background=False),
    }


async def _until_closed(websocket: WebSocket) -> None:
    while (await websocket.receive())["type"] != "websocket.disconnect":
        pass


@api.websocket("/ws")
async def notices(websocket: WebSocket) -> None:
    """Push a notice whenever data changes, and once a day at midnight."""
    await websocket.accept()
    events: Events = websocket.app.state.events
    async with events.subscribe() as queue:
        await websocket.send_json({"type": "hello", "version": __version__})
        closed = asyncio.create_task(_until_closed(websocket))
        try:
            while True:
                notice = asyncio.create_task(queue.get())
                await asyncio.wait(
                    {notice, closed}, return_when=asyncio.FIRST_COMPLETED
                )
                if closed.done():
                    notice.cancel()
                    break
                await websocket.send_json({"type": notice.result()})
        finally:
            closed.cancel()


# Application


class InterfaceFiles(StaticFiles):
    """The web interface. Its page is checked again on every visit, so that an
    update shows at once; the files it loads carry a hash and never change."""

    async def get_response(
        self, path: str, scope: MutableMapping[str, Any]
    ) -> Response:
        """Add caching headers."""
        response = await super().get_response(path, scope)
        if getattr(response, "media_type", None) == "text/html":
            response.headers["Cache-Control"] = "no-cache"
        elif path.replace("\\", "/").startswith("assets/"):
            response.headers["Cache-Control"] = "max-age=31536000, immutable"
        return response


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        _LOGGER.warning("Unknown time zone %s, using UTC", name)
        return ZoneInfo("UTC")


async def _midnight(events: Events, clock: Clock) -> None:
    """Tasks and windows move with the date: tell clients each new day."""
    while True:
        now = clock.now()
        tomorrow = datetime.combine(
            now.date() + timedelta(days=1), time(0, 0, 5), now.tzinfo
        )
        await asyncio.sleep((tomorrow - now).total_seconds())
        events.notify("day")


def create_app(
    settings: Settings,
    *,
    now: Callable[[], datetime] | None = None,
    ha_config: dict[str, Any] | None = None,
    static_dir: Path = STATIC_DIR,
) -> FastAPI:
    """Build the server. `now` and `ha_config` replace the real ones in tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        state = app.state
        config = ha_config if ha_config is not None else await fetch_config(settings)
        state.ha_config = config
        zone = _zone(config["time_zone"])
        state.clock = Clock(now or (lambda: datetime.now(zone)))
        state.texts = Texts(config["language"])
        engine = make_engine(settings.database_url)
        await asyncio.to_thread(migrate, engine)
        state.sessions = make_sessions(engine)
        with state.sessions() as session:
            ensure_garden(session, config["location_name"], config["latitude"])
        state.events.bind(asyncio.get_running_loop())
        ticker = asyncio.create_task(_midnight(state.events, state.clock))
        if settings.app_mode:
            await announce(settings, token)
        else:
            _LOGGER.info("API token for the Home Assistant integration: %s", token)
        try:
            yield
        finally:
            ticker.cancel()
            with suppress(asyncio.CancelledError):
                await ticker
            engine.dispose()

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    token = settings.api_token()
    app = FastAPI(
        title="Homestead",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.instance_id = settings.instance_id()
    app.state.catalog = load_catalog()
    app.state.events = Events()
    app.include_router(api)

    @app.get("/login", include_in_schema=False)
    def login(request: Request) -> Response:
        """Stand-alone with a token: open the web interface with ?token=…"""
        given = parse_qs(request.url.query).get("token", [""])[0]
        if not given or not secrets.compare_digest(given, token):
            raise HTTPException(401, "Wrong token")
        response = RedirectResponse("./", status_code=303)
        response.set_cookie(
            TOKEN_COOKIE, token, httponly=True, samesite="strict", max_age=31536000
        )
        return response

    if (static_dir / "index.html").exists():
        app.mount("/", InterfaceFiles(directory=static_dir, html=True), name="ui")
    else:

        @app.get("/", include_in_schema=False)
        def no_ui() -> PlainTextResponse:
            return PlainTextResponse(
                "Homestead is running; the web interface is not built."
            )

    app.add_middleware(TokenGuard, settings=settings, token=token)
    return app
