"""Tests for the species catalogue."""

from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.homestead.catalog import (
    CatalogError,
    load_catalog,
    parse_species,
)

TOMATO = {
    "id": "tomato",
    "names": {"en": "Tomato", "fr": "Tomate"},
    "family": "solanaceae",
    "frost": "tender",
    "sow_indoors": [{"start": -8, "end": -6}],
    "transplant": [{"start": 1, "end": 3}],
    "harvest": {"after": "transplant", "days": [60, 85], "weeks": 10},
}


def test_bundled_catalog() -> None:
    """Every bundled species file is valid and translated into French."""
    catalog = load_catalog()
    assert len(catalog) >= 30
    for species in catalog.values():
        assert species.methods, species.id
        assert "fr" in species.names, species.id
        for task in species.tasks:
            assert "fr" in task.label, f"{species.id}.{task.id}"


def test_names() -> None:
    """Names follow the language, with English as fallback."""
    species = parse_species(TOMATO)
    assert species.name("fr") == "Tomate"
    assert species.name("fr-BE") == "Tomate"
    assert species.name("nl") == "Tomato"


def test_methods_and_nursery() -> None:
    """Sowing under cover needs a transplant window."""
    species = parse_species(TOMATO)
    assert species.methods == ["sow_indoors", "plant"]
    assert species.nursery_days == 63


@pytest.mark.parametrize(
    "change",
    [
        {"frost": "very"},
        {"names": {"fr": "Tomate"}},
        {"harvest": {"after": "flowering", "days": [60, 85], "weeks": 10}},
        {"harvest": {"after": "transplant", "days": [85, 60], "weeks": 10}},
        {"sow_indoors": [{"start": -6, "end": -8}]},
        {"sow_indoors": [{"start": -8, "end": -6, "ref": "equinox"}]},
        {"sow_indoors": [], "transplant": []},
        {"tasks": [{"id": "x", "after": "sowing", "days": 3, "label": {"fr": "X"}}]},
        {"harvest": None},
    ],
)
def test_invalid(change: dict) -> None:
    """Malformed species are refused with a readable error."""
    with pytest.raises(CatalogError):
        parse_species(TOMATO | change)


def test_file_name_must_match_id(tmp_path: Path) -> None:
    """A file is named after the id of its species."""
    (tmp_path / "tomate.yaml").write_text(
        "id: tomato\nnames: {en: Tomato}\nfamily: solanaceae\nfrost: tender\n"
        "sow_direct: [{start: 1, end: 2}]\n"
        "harvest: {after: sowing, days: [60, 80], weeks: 4}\n",
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match=r"tomate\.yaml"):
        load_catalog(tmp_path)
