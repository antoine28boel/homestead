"""Settings of the Homestead server, read from the environment."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import secrets
import uuid

# Home Assistant's Supervisor proxies ingress requests from this address.
INGRESS_IP = "172.30.32.2"


@dataclass(frozen=True, slots=True)
class Settings:
    """Where data lives and how to reach Home Assistant."""

    data_dir: Path
    port: int = 8099
    supervisor_token: str | None = None
    """Set by the Supervisor when running as a Home Assistant app."""
    ha_url: str | None = None
    ha_token: str | None = None
    """Long-lived token, for a stand-alone container next to Home Assistant."""
    require_token: bool = False
    """Stand-alone only: also protect the web interface with the API token."""
    language: str | None = None
    time_zone: str | None = None
    """Used when Home Assistant cannot be asked."""

    @classmethod
    def from_env(cls) -> Settings:
        """Read HOMESTEAD_* variables and the Supervisor's token."""
        env = os.environ
        return cls(
            data_dir=Path(env.get("HOMESTEAD_DATA_DIR", "/data")),
            port=int(env.get("HOMESTEAD_PORT", "8099")),
            supervisor_token=env.get("SUPERVISOR_TOKEN") or None,
            ha_url=(env.get("HOMESTEAD_HA_URL") or "").rstrip("/") or None,
            ha_token=env.get("HOMESTEAD_HA_TOKEN") or None,
            require_token=env.get("HOMESTEAD_REQUIRE_TOKEN", "") in ("1", "true"),
            language=env.get("HOMESTEAD_LANGUAGE") or None,
            time_zone=env.get("TZ") or None,
        )

    @property
    def app_mode(self) -> bool:
        """Whether the server runs as a Home Assistant app."""
        return self.supervisor_token is not None

    @property
    def database_url(self) -> str:
        """SQLite database in the data folder."""
        return f"sqlite:///{self.data_dir / 'homestead.db'}"

    def _kept(self, name: str, make: Callable[[], str]) -> str:
        """A value created on first start and kept in the data folder."""
        path = self.data_dir / name
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        value = make()
        path.write_text(value, encoding="utf-8")
        return value

    def api_token(self) -> str:
        """Token the companion integration uses."""
        return self._kept("api_token", lambda: secrets.token_urlsafe(32))

    def instance_id(self) -> str:
        """Identifies this server, whatever its address."""
        return self._kept("instance_id", lambda: uuid.uuid4().hex)
