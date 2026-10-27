"""Run the server: python -m homestead_server."""

import logging

import uvicorn

from .api import create_app
from .config import Settings


def main() -> None:
    """Start on all interfaces; the app's port is only reachable inside HA."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    settings = Settings.from_env()
    uvicorn.run(
        create_app(settings),
        host="0.0.0.0",
        port=settings.port,
        proxy_headers=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
