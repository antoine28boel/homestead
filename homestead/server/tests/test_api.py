"""Tests for the REST API and the WebSocket notices."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from homestead_server import api as api_module
from homestead_server.climate import Night
from homestead_server.config import INGRESS_IP

from .conftest import BRUSSELS, FakeClock


def _plant(client: TestClient, species: str, space_id: str, **extra: Any) -> dict:
    response = client.post(
        "/api/plantings", json={"species": species, "space_id": space_id, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_info_and_garden(client: TestClient) -> None:
    """The garden is created with northern frost dates and the HA settings."""
    info = client.get("/api/info").json()
    assert info["language"] == "fr"
    assert info["today"] == "2027-03-20"
    assert info["species"] >= 30
    assert info["garden"] == "Jardin"

    assert client.get("/api/garden").json() == {
        "name": "Jardin",
        "last_frost": "05-15",
        "first_frost": "10-15",
        "weather_entity": None,
    }
    response = client.put("/api/garden", json={"last_frost": "2027-4-30"})
    assert response.json()["last_frost"] == "04-30"
    assert client.put("/api/garden", json={"first_frost": "13-01"}).status_code == 422


def test_catalog(client: TestClient) -> None:
    """Species come with their French names and methods."""
    catalog = {species["id"]: species for species in client.get("/api/catalog").json()}
    assert catalog["tomato"]["name"] == "Tomate"
    assert "sow_indoors" in catalog["tomato"]["methods"]


def test_spaces(client: TestClient, spaces: dict[str, str]) -> None:
    """Spaces get the default frost shift of their type until set."""
    listed = {space["id"]: space for space in client.get("/api/spaces").json()}
    assert listed[spaces["greenhouse"]]["effective_frost_shift"] == 4
    assert listed[spaces["raised"]]["effective_frost_shift"] == 1

    response = client.patch(
        f"/api/spaces/{spaces['greenhouse']}", json={"frost_shift": 6}
    )
    assert response.json()["effective_frost_shift"] == 6
    response = client.patch(
        f"/api/spaces/{spaces['greenhouse']}", json={"frost_shift": None}
    )
    assert response.json()["effective_frost_shift"] == 4
    assert (
        client.post("/api/spaces", json={"name": "x", "type": "moon"}).status_code
        == 422
    )

    # A used space is archived, an empty one deleted.
    _plant(client, "lettuce", spaces["plot"])
    assert client.delete(f"/api/spaces/{spaces['plot']}").json()["archived"] is True
    assert client.delete(f"/api/spaces/{spaces['raised']}").status_code == 204
    assert [space["id"] for space in client.get("/api/spaces").json()] == [
        spaces["greenhouse"]
    ]
    assert len(client.get("/api/spaces", params={"archived": True}).json()) == 2


def test_starts_and_sow_now(client: TestClient, spaces: dict[str, str]) -> None:
    """Start options give the next season of each window."""
    options = client.get(
        "/api/catalog/tomato/starts", params={"space_id": spaces["greenhouse"]}
    ).json()
    methods = {option["method"] for option in options}
    assert {"sow_indoors", "plant"} <= methods
    assert all(option["season"] in (2027, 2028) for option in options)
    assert "du" in options[0]["label"]
    sow = next(option for option in options if option["method"] == "sow_indoors")
    assert sow["season"] == 2028
    # Each option shows the steps it leads to.
    assert [step["key"] for step in sow["steps"]][:2] == ["sow", "task.prick_out"]
    assert sow["steps"][0]["label"] == "Semer sous abri"
    assert sow["steps"][0]["period"][0] == sow["start"]
    assert {step["status"] for step in sow["steps"]} == {"planned"}

    # Tomatoes for the greenhouse were sown in February; for open ground, now.
    now = client.get(f"/api/spaces/{spaces['plot']}/sow-now").json()
    assert any(item["id"] == "tomato" for item in now.get("sow_indoors", []))
    everywhere = client.get("/api/sow-now").json()
    assert {entry["space_id"] for entry in everywhere} == set(spaces.values())


def test_rotation_and_neighbours(client: TestClient, spaces: dict[str, str]) -> None:
    """Placing a crop tells of its family's past here and of its neighbours."""
    plot = spaces["plot"]
    old = _plant(client, "tomato", plot, season=2026)
    client.post(
        f"/api/plantings/{old['id']}/stage",
        json={"stage": "finished", "day": "2026-10-10"},
    )
    # Planned for last year but never started: it did not grow there.
    _plant(client, "pepper", plot, season=2026)
    _plant(client, "basil", plot)

    def notes(species: str) -> list[dict]:
        options = client.get(
            f"/api/catalog/{species}/starts", params={"space_id": plot}
        ).json()
        option = next(option for option in options if option["season"] == 2027)
        return option["placement"]

    potato = notes("potato")
    assert [note["kind"] for note in potato] == ["rotation"]
    assert potato[0]["text"] == (
        "Même famille (solanacées) ici en 2026 : Tomate. Laisser 4 ans entre les deux."
    )
    assert potato[0]["planting_id"] == old["id"]

    potatoes = _plant(client, "potato", plot, method="plant")
    assert [note["kind"] for note in notes("tomato")] == [
        "avoid",
        "rotation",
        "companion",
    ]

    # Regions drawn two metres apart are no longer neighbours.
    tomato = _plant(client, "tomato", plot)
    region = {"region_y": 0, "region_width": 1, "region_height": 1}
    client.patch(f"/api/plantings/{potatoes['id']}", json={"region_x": 0, **region})
    client.patch(f"/api/plantings/{tomato['id']}", json={"region_x": 3, **region})
    detail = client.get(f"/api/plantings/{tomato['id']}").json()
    assert [note["text"] for note in detail["placement"]] == [
        "Même famille (solanacées) ici en 2026 : Tomate. Laisser 4 ans entre les deux.",
        "Bon voisin : Basilic.",
    ]
    advice = detail["advice"]
    assert advice["family"] == "solanacées"
    assert "Basilic" in advice["companions"]
    # Sweet corn names the tomato as a bad neighbour: it shows on both sides.
    assert {"Maïs doux", "Pomme de terre"} <= set(advice["avoid"])
    assert advice["tips"][0].startswith("Planter profond")


def test_planting_lifecycle(
    client: TestClient, spaces: dict[str, str], clock: FakeClock
) -> None:
    """Ticking tasks moves the planting through its stages."""
    tomato = _plant(client, "tomato", spaces["plot"], variety="Cœur de bœuf")
    assert tomato["name"] == "Tomate Cœur de bœuf"
    assert tomato["method"] == "sow_indoors"
    assert tomato["season"] == 2027
    assert tomato["stage"] == "planned"
    assert tomato["schedule"]["harvest"]
    assert tomato["next_task"]["summary"].startswith("Semer sous abri")

    uid = tomato["next_task"]["uid"]
    assert (
        client.patch(f"/api/tasks/{uid}", json={"completed": True}).status_code == 200
    )
    detail = client.get(f"/api/plantings/{tomato['id']}").json()
    assert detail["stage"] == "sown"
    assert detail["dates"] == {"sown": "2027-03-20"}
    assert uid not in {task["uid"] for task in detail["tasks"]}

    # The ticked task stays in the list for a week.
    done = [task for task in client.get("/api/tasks").json() if task["uid"] == uid]
    assert done and done[0]["completed"]
    clock.value = datetime(2027, 3, 28, 9, 0, tzinfo=BRUSSELS)
    assert uid not in {task["uid"] for task in client.get("/api/tasks").json()}

    # Unticking keeps the stage; the task is open again.
    client.patch(f"/api/tasks/{uid}", json={"completed": False})
    detail = client.get(f"/api/plantings/{tomato['id']}").json()
    assert detail["stage"] == "sown"

    # Going back to an earlier stage forgets later dates.
    response = client.post(
        f"/api/plantings/{tomato['id']}/stage",
        json={"stage": "growing", "day": "2027-05-01"},
    )
    assert response.json()["dates"] == {"sown": "2027-03-20", "growing": "2027-05-01"}
    response = client.post(
        f"/api/plantings/{tomato['id']}/stage", json={"stage": "sown"}
    )
    assert response.json()["dates"] == {"sown": "2027-03-20"}
    bad = client.post(f"/api/plantings/{tomato['id']}/stage", json={"stage": "eaten"})
    assert bad.status_code == 422


def test_planting_steps(client: TestClient, spaces: dict[str, str]) -> None:
    """Steps are done, open, planned, or past without being ticked."""
    tomato = _plant(client, "tomato", spaces["plot"])
    url = f"/api/plantings/{tomato['id']}"

    def status() -> dict[str, str]:
        return {step["key"]: step["status"] for step in client.get(url).json()["steps"]}

    assert status()["sow"] == "open"
    assert set(list(status().values())[1:]) == {"planned"}

    client.post(f"{url}/stage", json={"stage": "sown", "day": "2027-03-20"})
    assert status()["sow"] == "done"
    assert status()["task.prick_out"] == "open"
    assert status()["transplant"] == "open"
    assert status()["task.stake"] == "planned"

    client.patch(f"/api/tasks/{tomato['id']}.task.prick_out", json={"completed": True})
    client.post(f"{url}/stage", json={"stage": "transplanted", "day": "2027-05-20"})
    steps = {step["key"]: step for step in client.get(url).json()["steps"]}
    assert steps["task.prick_out"]["status"] == "done"
    assert steps["task.prick_out"]["day"] == "2027-03-20"
    assert steps["harden_off"]["status"] == "skipped"
    assert steps["task.stake"] == {
        "key": "task.stake",
        "kind": "crop",
        "label": "Tuteurer",
        "day": "2027-05-27",
        "period": None,
        "status": "open",
        "action": None,
        "frost": None,
    }


def _forecast(client: TestClient, *lows: tuple[str, float]) -> None:
    client.app.state.forecast = [  # type: ignore[attr-defined]
        Night(date.fromisoformat(day), low) for day, low in lows
    ]


def test_frost_alert(
    client: TestClient, spaces: dict[str, str], clock: FakeClock
) -> None:
    """Tender crops in the open get a task before a frosty night."""
    clock.value = datetime(2027, 5, 20, 9, 0, tzinfo=BRUSSELS)
    tomato = _plant(client, "tomato", spaces["plot"])
    sheltered = _plant(client, "tomato", spaces["greenhouse"])
    leek = _plant(client, "leek", spaces["plot"])
    for planting in (tomato, sheltered, leek):
        client.post(
            f"/api/plantings/{planting['id']}/stage",
            json={"stage": "transplanted", "day": "2027-05-18"},
        )
    _forecast(client, ("2027-05-22", 0.5), ("2027-05-23", -1.5))

    tasks = client.get("/api/tasks").json()
    frost = [task for task in tasks if ".frost." in task["uid"]]
    assert [task["planting_id"] for task in frost] == [tomato["id"]]
    assert frost[0]["uid"] == f"{tomato['id']}.frost.2027-05-22"
    assert frost[0]["summary"] == "Protéger du gel : Tomate (Potager)"
    assert frost[0]["due"] == "2027-05-21"
    assert frost[0]["description"] == "Minimum prévu : \u22121,5 °C le 23/05/2027."
    assert client.get("/api/summary").json()["frost"] == {
        "day": "2027-05-23",
        "low": -1.5,
    }

    # Ticked, it stays done for this cold spell.
    client.patch(f"/api/tasks/{frost[0]['uid']}", json={"completed": True})
    detail = client.get(f"/api/plantings/{tomato['id']}").json()
    assert not [task for task in detail["tasks"] if ".frost." in task["uid"]]
    assert detail["stage"] == "transplanted"

    def alerts() -> list[str]:
        return [
            task["planting_id"]
            for task in client.get("/api/tasks").json()
            if ".frost." in task["uid"] and not task["completed"]
        ]

    # A greenhouse only needs help against a harder frost.
    _forecast(client, ("2027-05-22", -3.0))
    assert alerts() == [sheltered["id"]]
    _forecast(client, ("2027-05-25", -1.0))
    assert alerts() == [tomato["id"]]
    _forecast(client)
    assert client.get("/api/summary").json()["frost"] is None


def test_frost_holds_planting_out(
    client: TestClient, spaces: dict[str, str], clock: FakeClock
) -> None:
    """Planting out waits until after the frost forecast."""
    clock.value = datetime(2027, 5, 20, 9, 0, tzinfo=BRUSSELS)
    tomato = _plant(client, "tomato", spaces["plot"], method="plant")
    lettuce = _plant(client, "lettuce", spaces["plot"], method="plant")
    _forecast(client, ("2027-05-21", -1.0), ("2027-05-24", -0.5))
    detail = client.get(f"/api/plantings/{tomato['id']}").json()
    plant = next(task for task in detail["tasks"] if task["uid"].endswith(".plant"))
    assert plant["due"] == "2027-05-25"
    assert plant["frost"] == {"day": "2027-05-24", "low": -0.5}
    assert plant["description"].startswith(
        "Gel prévu le 24/05/2027 (\u22120,5 °C) : attendre le 25/05/2027."
    )
    step = next(step for step in detail["steps"] if step["key"] == "plant")
    assert step["frost"] == {"day": "2027-05-24", "low": -0.5}

    # Half-hardy lettuce does not mind a light frost.
    detail = client.get(f"/api/plantings/{lettuce['id']}").json()
    assert detail["tasks"][0]["frost"] is None


def test_weather_settings(client: TestClient) -> None:
    """The weather entity is chosen in the settings."""
    weather = client.get("/api/weather").json()
    assert weather == {
        "connected": False,
        "entity_id": None,
        "entities": [],
        "nights": [],
    }
    response = client.put("/api/garden", json={"weather_entity": "weather.home"})
    assert response.json()["weather_entity"] == "weather.home"
    assert client.put("/api/garden", json={"weather_entity": ""}).status_code == 200
    bad = client.put("/api/garden", json={"weather_entity": "sensor.temperature"})
    assert bad.status_code == 422


def test_compute_frost_dates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Frost dates come from thirty years of minimums, and are only proposed."""
    assert client.post("/api/garden/frost-dates").status_code == 409
    state = client.app.state  # type: ignore[attr-defined]
    state.ha_config = state.ha_config | {"longitude": 4.35, "elevation": 60}
    asked: dict[str, Any] = {}

    async def minimums(*args: Any) -> list[tuple[date, float]]:
        asked["args"] = args
        return [
            (date(year, month, 10), -1.0 if month in (4, 11) else 6.0)
            for year in range(1997, 2027)
            for month in range(1, 13)
        ]

    monkeypatch.setattr(api_module, "fetch_minimums", minimums)
    found = client.post("/api/garden/frost-dates").json()
    assert found == {
        "last_frost": "04-10",
        "first_frost": "11-10",
        "last_median": "04-10",
        "first_median": "11-10",
        "years": 30,
    }
    assert asked["args"] == (50.8, 4.35, 60, 2026, "Europe/Brussels")
    assert client.get("/api/garden").json()["last_frost"] == "05-15"


def test_dismiss_task(client: TestClient, spaces: dict[str, str]) -> None:
    """Deleting a generated task hides it without changing the stage."""
    lettuce = _plant(client, "lettuce", spaces["plot"])
    uid = lettuce["next_task"]["uid"]
    assert client.delete(f"/api/tasks/{uid}").status_code == 204
    detail = client.get(f"/api/plantings/{lettuce['id']}").json()
    assert detail["stage"] == "planned"
    assert uid not in {task["uid"] for task in detail["tasks"]}
    assert client.delete("/api/tasks/nothing.sow").status_code == 404


def test_update_and_delete_planting(client: TestClient, spaces: dict[str, str]) -> None:
    """Variety, space and method can change; the species cannot."""
    tomato = _plant(client, "tomato", spaces["greenhouse"])
    response = client.patch(
        f"/api/plantings/{tomato['id']}",
        json={"variety": "Noire de Crimée", "method": "plant", "quantity": 4},
    )
    assert response.status_code == 200
    assert response.json()["method"] == "plant"
    assert response.json()["quantity"] == 4
    assert (
        client.patch(
            f"/api/plantings/{tomato['id']}", json={"species": "carrot"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/plantings/{tomato['id']}", json={"method": "sow_direct"}
        ).status_code
        == 422
    )
    client.post("/api/journal", json={"planting_id": tomato["id"], "note": "ok"})
    assert client.delete(f"/api/plantings/{tomato['id']}").status_code == 204
    assert client.get(f"/api/plantings/{tomato['id']}").status_code == 404
    assert client.get("/api/journal").json() == []


def test_journal_and_harvests(client: TestClient, spaces: dict[str, str]) -> None:
    """Journal entries take the planting's space; a harvest starts harvesting."""
    radish = _plant(client, "radish", spaces["raised"])
    entry = client.post(
        "/api/journal",
        json={
            "planting_id": radish["id"],
            "kind": "watering",
            "amount": 5,
            "unit": "L",
        },
    ).json()
    assert entry["space_id"] == spaces["raised"]
    assert entry["day"] == "2027-03-20"
    garden_note = client.post("/api/journal", json={"note": "Paillage"}).json()
    assert garden_note["planting_id"] is None
    assert client.post("/api/journal", json={"kind": "dancing"}).status_code == 422
    assert len(client.get("/api/journal").json()) == 2
    assert (
        len(client.get("/api/journal", params={"space_id": spaces["raised"]}).json())
        == 1
    )

    client.post(
        "/api/harvests",
        json={"planting_id": radish["id"], "quantity": 12, "unit": "pieces"},
    )
    client.post(
        "/api/harvests",
        json={"planting_id": radish["id"], "quantity": 8, "unit": "pieces"},
    )
    detail = client.get(f"/api/plantings/{radish['id']}").json()
    assert detail["stage"] == "harvesting"
    assert detail["harvested"] == {"pieces": 20}
    assert len(detail["harvests"]) == 2
    assert client.get("/api/seasons").json() == [
        {"season": 2027, "plantings": 1, "harvested": {"pieces": 20}}
    ]
    bad = client.post(
        "/api/harvests", json={"planting_id": radish["id"], "quantity": 0}
    )
    assert bad.status_code == 422


def test_history(client: TestClient, spaces: dict[str, str]) -> None:
    """A planting shows the same crop in earlier seasons."""
    old = _plant(client, "carrot", spaces["plot"], season=2026)
    client.post("/api/harvests", json={"planting_id": old["id"], "quantity": 3.5})
    new = _plant(client, "carrot", spaces["plot"])
    history = client.get(f"/api/plantings/{new['id']}").json()["history"]
    assert [(item["season"], item["harvested"]) for item in history] == [
        (2026, {"kg": 3.5})
    ]
    assert [p["season"] for p in client.get("/api/plantings").json()] == [2027, 2026]
    assert len(client.get("/api/plantings", params={"season": 2026}).json()) == 1


def test_own_todo_items(client: TestClient) -> None:
    """Own items can be added, changed, ticked and removed."""
    uid = client.post(
        "/api/tasks", json={"summary": "Acheter du terreau", "due": "2027-03-22"}
    ).json()["uid"]
    item = next(task for task in client.get("/api/tasks").json() if task["uid"] == uid)
    assert item["generated"] is False
    assert item["due"] == "2027-03-22"

    client.patch(f"/api/tasks/{uid}", json={"completed": True, "summary": "Terreau"})
    item = next(task for task in client.get("/api/tasks").json() if task["uid"] == uid)
    assert item["summary"] == "Terreau"
    assert item["completed"].startswith("2027-03-20")
    assert client.delete(f"/api/tasks/{uid}").status_code == 204
    assert client.delete(f"/api/tasks/{uid}").status_code == 404
    assert client.post("/api/tasks", json={}).status_code == 422


def test_calendar(client: TestClient, spaces: dict[str, str]) -> None:
    """Calendar events cover sowing and harvest, end date exclusive."""
    tomato = _plant(client, "tomato", spaces["plot"])
    events = client.get(
        "/api/calendar", params={"start": "2027-01-01", "end": "2028-01-01"}
    ).json()
    kinds = {event["kind"] for event in events if event["planting_id"] == tomato["id"]}
    assert kinds == {"sow", "transplant", "harvest", "step"}
    # The jobs between the periods are on their own day.
    jobs = {event["uid"]: event for event in events if event["kind"] == "step"}
    stake = jobs[f"{tomato['id']}.task.stake"]
    assert stake["summary"] == "Tuteurer : Tomate"
    assert stake["location"] == "Potager"
    assert (stake["start"], stake["end"]) == ("2027-05-29", "2027-05-30")
    assert {uid.split(".", 1)[1] for uid in jobs} == {
        "task.prick_out",
        "harden_off",
        "task.stake",
        "task.side_shoots",
        "finish",
    }
    # Ticked jobs stay, marked; dismissed ones go.
    client.patch(f"/api/tasks/{tomato['id']}.sow", json={"completed": True})
    client.patch(f"/api/tasks/{tomato['id']}.task.prick_out", json={"completed": True})
    client.delete(f"/api/tasks/{tomato['id']}.harden_off")
    events = client.get(
        "/api/calendar", params={"start": "2027-01-01", "end": "2028-01-01"}
    ).json()
    jobs = {event["uid"]: event for event in events if event["kind"] == "step"}
    assert jobs[f"{tomato['id']}.task.prick_out"]["summary"].startswith("\u2713 ")
    assert jobs[f"{tomato['id']}.task.prick_out"]["start"] == "2027-03-20"
    assert f"{tomato['id']}.harden_off" not in jobs
    harvest = next(event for event in events if event["kind"] == "harvest")
    assert harvest["end"] == _next_day(tomato["schedule"]["harvest"][1])
    assert harvest["location"] == "Potager"
    empty = client.get(
        "/api/calendar", params={"start": "2030-01-01", "end": "2030-02-01"}
    ).json()
    assert empty == []
    bad = client.get(
        "/api/calendar", params={"start": "2027-02-01", "end": "2027-01-01"}
    )
    assert bad.status_code == 422


def _next_day(day: str) -> str:
    from datetime import date, timedelta

    return (date.fromisoformat(day) + timedelta(days=1)).isoformat()


def test_summary(client: TestClient, spaces: dict[str, str]) -> None:
    """The integration's summary lists active plantings and tasks."""
    lettuce = _plant(client, "lettuce", spaces["plot"])
    finished = _plant(client, "radish", spaces["raised"])
    client.post(f"/api/plantings/{finished['id']}/stage", json={"stage": "finished"})
    summary = client.get("/api/summary").json()
    assert [planting["id"] for planting in summary["plantings"]] == [lettuce["id"]]
    assert len(summary["spaces"]) == 3
    assert summary["stages"][0] == "planned"
    assert summary["garden"]["name"] == "Jardin"
    assert summary["instance_id"] == client.get("/api/info").json()["instance_id"]
    assert lettuce["id"] in {event["planting_id"] for event in summary["events"]}
    assert set(summary["sow_now"]) == set(spaces.values())


def test_websocket_notices(client: TestClient) -> None:
    """Clients are told when something changes."""
    with client.websocket_connect("/api/ws") as websocket:
        assert websocket.receive_json()["type"] == "hello"
        client.post("/api/journal", json={"note": "Pluie"})
        assert websocket.receive_json() == {"type": "changed"}


def test_app_mode_auth(
    make_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """In Home Assistant, only ingress and the token get through."""
    announced: list[str] = []

    async def announce(settings: Any, token: str) -> bool:
        announced.append(token)
        return True

    monkeypatch.setattr(api_module, "announce", announce)
    outsider = make_client(supervisor_token="supervisor")
    token = announced[0]
    assert outsider.get("/api/health").status_code == 200
    assert outsider.get("/api/info").status_code == 401
    assert outsider.get("/").status_code == 401
    assert (
        outsider.get("/api/info", headers={"Authorization": "Bearer nope"}).status_code
        == 401
    )
    response = outsider.get("/api/info", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["app_mode"] is True

    ingress = make_client(client_host=INGRESS_IP, supervisor_token="supervisor")
    assert ingress.get("/api/info").status_code == 200
    # Same data folder, so the same token.
    assert announced == [token, token]


def test_stand_alone_token(
    make_client: Callable[..., TestClient], tmp_path: Path
) -> None:
    """A stand-alone server can require the token, also as a cookie."""
    client = make_client(require_token=True)
    token = (tmp_path / "api_token").read_text(encoding="utf-8")
    assert client.get("/api/info").status_code == 401
    assert client.get("/login", params={"token": "nope"}).status_code == 401
    response = client.get("/login", params={"token": token}, follow_redirects=False)
    assert response.status_code == 303
    assert client.get("/api/info").status_code == 200


def test_static_ui(make_client: Callable[..., TestClient], tmp_path: Path) -> None:
    """The built web interface is served at the root."""
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>Homestead</h1>", encoding="utf-8")
    (static / "assets").mkdir()
    (static / "assets" / "index-abc.js").write_text("", encoding="utf-8")
    client = make_client(static_dir=static)
    page = client.get("/")
    assert "Homestead" in page.text
    # The page is checked on every visit; its hashed files are cached.
    assert page.headers["cache-control"] == "no-cache"
    assert "immutable" in client.get("/assets/index-abc.js").headers["cache-control"]
    assert client.get("/api/health").json() == {"status": "ok"}


def test_wrong_token_refused(client: TestClient) -> None:
    """An open stand-alone server still refuses a wrong token."""
    assert client.get("/api/info").status_code == 200
    response = client.get("/api/info", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_no_ui(client: TestClient) -> None:
    """Without a built interface, the root says so."""
    assert "not built" in client.get("/").text
