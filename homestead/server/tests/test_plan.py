"""Tests for the garden plan."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01"
    b"\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _draw(client: TestClient, space_id: str, **geometry: Any) -> dict:
    response = client.patch(f"/api/spaces/{space_id}", json=geometry)
    assert response.status_code == 200, response.text
    return response.json()


def _plant(client: TestClient, species: str, space_id: str, **extra: Any) -> dict:
    response = client.post(
        "/api/plantings", json={"species": species, "space_id": space_id, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_empty_plan(client: TestClient, spaces: dict[str, str]) -> None:
    """Spaces not drawn yet are listed, and the plan has a default size."""
    plan = client.get("/api/plan").json()
    assert (plan["width"], plan["height"]) == (12.0, 9.0)
    assert plan["background"] is None
    assert [space["placed"] for space in plan["spaces"]] == [False] * 3
    assert plan["items"] == []
    assert plan["plantings"] == []


def test_draw_spaces(client: TestClient, spaces: dict[str, str]) -> None:
    """Drawn spaces get a surface; the plan grows to hold them."""
    plot = _draw(client, spaces["plot"], x=1, y=1, width=8, height=4)
    assert plot["placed"] is True
    assert plot["surface"] == 32
    assert plot["area"] is None

    _draw(client, spaces["greenhouse"], x=12, y=2, width=3, height=2, rotation=90)
    plan = client.get("/api/plan").json()
    # Turned a quarter, the greenhouse reaches 13.5 + 1 m of margin.
    assert plan["width"] == 15.5
    assert plan["height"] == 9.0

    # A null clears the drawing; other fields are left alone.
    cleared = _draw(client, spaces["plot"], x=None, name="Grand potager")
    assert cleared["placed"] is False
    assert cleared["name"] == "Grand potager"
    assert cleared["surface"] is None

    response = client.patch(f"/api/spaces/{spaces['plot']}", json={"shape": "star"})
    assert response.status_code == 422


def test_plan_size_and_items(client: TestClient) -> None:
    """A set size wins; objects can be drawn, moved and removed."""
    response = client.post(
        "/api/plan/items",
        json={
            "kind": "tree",
            "label": "Pommier",
            "x": 2,
            "y": 3,
            "width": 4,
            "height": 4,
        },
    )
    assert response.status_code == 201
    tree = response.json()
    assert client.post("/api/plan/items", json={"kind": "tree"}).status_code == 422
    assert (
        client.post(
            "/api/plan/items",
            json={"kind": "castle", "x": 0, "y": 0, "width": 1, "height": 1},
        ).status_code
        == 422
    )

    moved = client.patch(f"/api/plan/items/{tree['id']}", json={"x": 5}).json()
    assert (moved["x"], moved["y"]) == (5, 3)

    plan = client.put("/api/plan", json={"width": 30, "height": 20}).json()
    assert (plan["width"], plan["height"], plan["size_set"]) == (30, 20, True)
    assert [item["label"] for item in plan["items"]] == ["Pommier"]

    plan = client.put("/api/plan", json={"width": None, "height": None}).json()
    assert (plan["width"], plan["height"], plan["size_set"]) == (12.0, 9.0, False)

    assert client.delete(f"/api/plan/items/{tree['id']}").status_code == 204
    assert client.get("/api/plan").json()["items"] == []


def test_background(client: TestClient, tmp_path: Path) -> None:
    """An image is stored, served, calibrated, replaced and removed."""
    response = client.put(
        "/api/plan/background",
        params={"width": 2000, "height": 1000},
        content=PNG,
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 200, response.text
    background = response.json()["background"]
    assert background["width"] == 2000
    assert background["scale"] is None
    assert background["opacity"] == 0.6
    name = background["url"].rsplit("/", 1)[1]
    assert (tmp_path / "plan" / name).read_bytes() == PNG

    served = client.get(f"/{background['url']}")
    assert served.content == PNG
    assert "immutable" in served.headers["cache-control"]
    assert client.get("/api/plan/background/other.png").status_code == 404

    # 8 m drawn over 400 pixels: 2 cm per pixel, and the plan is 40 by 20 m.
    plan = client.put(
        "/api/plan", json={"background_scale": 0.02, "background_opacity": 0.3}
    ).json()
    assert (plan["width"], plan["height"]) == (40, 20)
    assert plan["background"]["opacity"] == 0.3

    # A new photo of the same width keeps the scale; the old file goes.
    plan = client.put(
        "/api/plan/background",
        params={"width": 2000, "height": 1000},
        content=PNG,
        headers={"Content-Type": "image/png"},
    ).json()
    assert plan["background"]["scale"] == 0.02
    assert not (tmp_path / "plan" / name).exists()

    assert (
        client.put(
            "/api/plan/background",
            params={"width": 10, "height": 10},
            content=b"hello",
            headers={"Content-Type": "text/plain"},
        ).status_code
        == 415
    )

    plan = client.delete("/api/plan/background").json()
    assert plan["background"] is None
    assert list((tmp_path / "plan").iterdir()) == []


def test_plantings_on_plan(client: TestClient, spaces: dict[str, str]) -> None:
    """Plantings share their space until given a region of their own."""
    _draw(client, spaces["plot"], x=0, y=0, width=8, height=4)
    garlic = _plant(client, "garlic", spaces["plot"], method="plant")
    leek = _plant(client, "leek", spaces["plot"])
    _plant(client, "tomato", spaces["greenhouse"])

    plan = client.get("/api/plan").json()
    on_plan = {planting["id"]: planting for planting in plan["plantings"]}
    # The greenhouse is not drawn: its tomato is not on the plan.
    assert set(on_plan) == {garlic["id"], leek["id"]}
    assert on_plan[garlic["id"]]["region"] == {"x": 0, "y": 0, "width": 4, "height": 4}
    assert on_plan[leek["id"]]["region"]["x"] == 4
    # A bed is in rows by default; garlic is 10 cm apart, rows 25 cm apart.
    assert on_plan[garlic["id"]]["layout"] == "rows"
    assert on_plan[garlic["id"]]["layout_set"] is False
    assert on_plan[garlic["id"]]["spacing"] == 10
    assert on_plan[garlic["id"]]["count"] == 40 * 16
    assert len(on_plan[garlic["id"]]["positions"]) == 40 * 16
    assert on_plan[garlic["id"]]["dense"] is False
    assert on_plan[garlic["id"]]["in_ground"] is False

    response = client.patch(
        f"/api/plantings/{garlic['id']}",
        json={
            "region_x": 0.5,
            "region_y": 0.5,
            "region_width": 2,
            "region_height": 1,
            "layout": "staggered",
            "spacing": 20,
        },
    )
    assert response.status_code == 200, response.text
    client.post(f"/api/plantings/{garlic['id']}/stage", json={"stage": "transplanted"})
    plan = client.get("/api/plan").json()
    on_plan = {planting["id"]: planting for planting in plan["plantings"]}
    garlic_plan = on_plan[garlic["id"]]
    assert garlic_plan["region"] == {"x": 0.5, "y": 0.5, "width": 2, "height": 1}
    assert garlic_plan["layout"] == "staggered"
    assert garlic_plan["count"] == len(garlic_plan["positions"]) == 10 * 3 + 9 * 2
    assert garlic_plan["in_ground"] is True
    # The leek now has the whole space to itself.
    assert on_plan[leek["id"]]["region"]["width"] == 8

    # Free layout keeps its points; a region larger than the space is cut.
    client.patch(
        f"/api/plantings/{garlic['id']}",
        json={
            "layout": "free",
            "points": [[0.1, 0.2], [0.5, 0.5]],
            "region_x": 7,
            "region_width": 5,
        },
    )
    garlic_plan = {
        planting["id"]: planting
        for planting in client.get("/api/plan").json()["plantings"]
    }[garlic["id"]]
    assert garlic_plan["positions"] == [[0.1, 0.2], [0.5, 0.5]]
    assert garlic_plan["region"]["width"] == 1

    # Moving to another space forgets the region.
    moved = client.patch(
        f"/api/plantings/{garlic['id']}", json={"space_id": spaces["raised"]}
    )
    assert moved.status_code == 200
    _draw(client, spaces["raised"], x=10, y=0, width=1.2, height=1.2)
    garlic_plan = {
        planting["id"]: planting
        for planting in client.get("/api/plan").json()["plantings"]
    }[garlic["id"]]
    assert garlic_plan["region_set"] is False
    assert garlic_plan["region"]["width"] == 1.2

    response = client.patch(f"/api/plantings/{garlic['id']}", json={"layout": "spiral"})
    assert response.status_code == 422


def test_summary_has_plan(
    make_client: Callable[..., TestClient], spaces: dict[str, str], client: TestClient
) -> None:
    """The integration gets the plan, without the background."""
    client.put(
        "/api/plan/background",
        params={"width": 10, "height": 10},
        content=PNG,
        headers={"Content-Type": "image/png"},
    )
    summary = client.get("/api/summary").json()
    assert summary["plan"]["background"] is None
    assert len(summary["plan"]["spaces"]) == 3
