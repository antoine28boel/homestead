"""Species catalogue: one YAML file per species in the catalog folder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .const import (
    AFTER_SOWING,
    AFTER_TRANSPLANT,
    FROST_TOLERANCES,
    METHOD_PLANT,
    METHOD_SOW_DIRECT,
    METHOD_SOW_INDOORS,
    REF_FIRST_FROST,
    REF_LAST_FROST,
)

CATALOG_DIR = Path(__file__).parent / "catalog"


class CatalogError(ValueError):
    """A species file does not follow the catalogue format."""


def localized(texts: dict[str, str], language: str) -> str:
    """Pick a text in the language of Home Assistant, falling back to English."""
    return texts.get(language) or texts.get(language.split("-")[0]) or texts["en"]


@dataclass(frozen=True, slots=True)
class Window:
    """A period of the year, in weeks from a frost date."""

    start: int
    end: int
    ref: str = REF_LAST_FROST
    harvest_days: tuple[int, int] | None = None
    """Overrides the days to harvest of the species (autumn sowings…)."""


@dataclass(frozen=True, slots=True)
class Harvest:
    """When harvest starts and how long it lasts."""

    after: str
    days: tuple[int, int]
    weeks: int


@dataclass(frozen=True, slots=True)
class CropTask:
    """A one-off job, some days after sowing or transplanting."""

    id: str
    after: str
    days: int
    label: dict[str, str]


@dataclass(frozen=True, slots=True)
class Species:
    """A crop of the catalogue."""

    id: str
    names: dict[str, str]
    family: str
    frost: str
    sow_indoors: tuple[Window, ...]
    sow_direct: tuple[Window, ...]
    transplant: tuple[Window, ...]
    harvest: Harvest
    germination_days: tuple[int, int] | None = None
    spacing_cm: tuple[int, int] | None = None
    """In the row, then between rows."""
    tasks: tuple[CropTask, ...] = ()

    def name(self, language: str) -> str:
        """Name of the species in the given language."""
        return localized(self.names, language)

    @property
    def methods(self) -> list[str]:
        """Ways of starting this crop."""
        methods = []
        if self.sow_indoors and self.transplant:
            methods.append(METHOD_SOW_INDOORS)
        if self.sow_direct:
            methods.append(METHOD_SOW_DIRECT)
        if self.transplant:
            methods.append(METHOD_PLANT)
        return methods

    def windows(self, method: str) -> tuple[Window, ...]:
        """Windows in which a crop is started with this method."""
        if method == METHOD_SOW_INDOORS:
            return self.sow_indoors
        if method == METHOD_SOW_DIRECT:
            return self.sow_direct
        return self.transplant

    @property
    def nursery_days(self) -> int:
        """Usual time between sowing under cover and transplanting."""
        if not self.sow_indoors or not self.transplant:
            return 0
        return max(0, (self.transplant[0].start - self.sow_indoors[0].start) * 7)


def _pair(raw: Any, field: str) -> tuple[int, int]:
    if not isinstance(raw, list) or len(raw) != 2 or raw[0] > raw[1]:
        raise CatalogError(f"{field} must be [min, max]")
    return int(raw[0]), int(raw[1])


def _windows(raw: Any, field: str) -> tuple[Window, ...]:
    windows = []
    for item in raw or []:
        ref = item.get("ref", REF_LAST_FROST)
        if ref not in (REF_LAST_FROST, REF_FIRST_FROST):
            raise CatalogError(f"{field}: unknown ref {ref!r}")
        if item["start"] > item["end"]:
            raise CatalogError(f"{field}: start is after end")
        harvest_days = item.get("harvest_days")
        windows.append(
            Window(
                start=int(item["start"]),
                end=int(item["end"]),
                ref=ref,
                harvest_days=_pair(harvest_days, f"{field}.harvest_days")
                if harvest_days is not None
                else None,
            )
        )
    return tuple(windows)


def _after(value: Any, field: str) -> str:
    if value not in (AFTER_SOWING, AFTER_TRANSPLANT):
        raise CatalogError(f"{field}: after must be sowing or transplant")
    return value


def parse_species(raw: dict[str, Any]) -> Species:
    """Build a species from the content of its YAML file."""
    try:
        names = dict(raw["names"])
        if "en" not in names:
            raise CatalogError("names must include en")
        if raw["frost"] not in FROST_TOLERANCES:
            raise CatalogError(f"unknown frost tolerance {raw['frost']!r}")
        harvest = raw["harvest"]
        spacing = raw.get("spacing_cm")
        germination = raw.get("germination_days")
        species = Species(
            id=str(raw["id"]),
            names=names,
            family=str(raw["family"]),
            frost=raw["frost"],
            sow_indoors=_windows(raw.get("sow_indoors"), "sow_indoors"),
            sow_direct=_windows(raw.get("sow_direct"), "sow_direct"),
            transplant=_windows(raw.get("transplant"), "transplant"),
            harvest=Harvest(
                after=_after(harvest["after"], "harvest"),
                days=_pair(harvest["days"], "harvest.days"),
                weeks=int(harvest["weeks"]),
            ),
            germination_days=_pair(germination, "germination_days")
            if germination is not None
            else None,
            spacing_cm=(int(spacing["plant"]), int(spacing["row"]))
            if spacing
            else None,
            tasks=tuple(
                CropTask(
                    id=str(task["id"]),
                    after=_after(task["after"], f"tasks.{task['id']}"),
                    days=int(task["days"]),
                    label=dict(task["label"]),
                )
                for task in raw.get("tasks") or []
            ),
        )
    except (KeyError, TypeError) as err:
        raise CatalogError(f"missing or invalid field: {err}") from err
    if not species.methods:
        raise CatalogError("no sowing or planting window")
    if any("en" not in task.label for task in species.tasks):
        raise CatalogError("task labels must include en")
    return species


def load_catalog(directory: Path = CATALOG_DIR) -> dict[str, Species]:
    """Read every species file. Blocking: run it in the executor."""
    catalog: dict[str, Species] = {}
    for path in sorted(directory.glob("*.yaml")):
        with path.open(encoding="utf-8") as file:
            raw = yaml.safe_load(file)
        try:
            species = parse_species(raw)
        except CatalogError as err:
            raise CatalogError(f"{path.name}: {err}") from err
        if species.id != path.stem:
            raise CatalogError(f"{path.name}: id must be {path.stem!r}")
        catalog[species.id] = species
    return catalog
