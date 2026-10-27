"""Fixtures for the server tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
import pytest

from homestead_server.api import create_app
from homestead_server.config import Settings

BRUSSELS = ZoneInfo("Europe/Brussels")
HA_CONFIG = {
    "language": "fr",
    "time_zone": "Europe/Brussels",
    "latitude": 50.8,
    "location_name": "Jardin",
}


class FakeClock:
    """A clock the tests move by hand."""

    def __init__(self, value: datetime) -> None:
        """Start at `value`."""
        self.value = value

    def __call__(self) -> datetime:
        """Current time."""
        return self.value


@pytest.fixture
def clock() -> FakeClock:
    """Mid-March, the start of the sowing season in Belgium."""
    return FakeClock(datetime(2027, 3, 20, 9, 0, tzinfo=BRUSSELS))


@pytest.fixture
def make_client(
    tmp_path: Path, clock: FakeClock
) -> Iterator[Callable[..., TestClient]]:
    """Build a started server with the given settings."""
    clients: list[TestClient] = []

    def make(
        client_host: str = "testclient", static_dir: Path | None = None, **settings: Any
    ) -> TestClient:
        app = create_app(
            Settings(data_dir=tmp_path, **settings),
            now=clock,
            ha_config=HA_CONFIG,
            **({"static_dir": static_dir} if static_dir else {}),
        )
        client = TestClient(app, client=(client_host, 50000))
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    """Stand-alone server without a token."""
    return make_client()


@pytest.fixture
def spaces(client: TestClient) -> dict[str, str]:
    """The three spaces of the author's garden."""
    created = {}
    for key, name, kind in (
        ("plot", "Potager", "bed"),
        ("raised", "Carré surélevé", "raised_bed"),
        ("greenhouse", "Serre", "greenhouse"),
    ):
        response = client.post("/api/spaces", json={"name": name, "type": kind})
        assert response.status_code == 201
        created[key] = response.json()["id"]
    return created
