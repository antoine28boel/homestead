"""Constants for the Homestead integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "homestead"

STAGES: Final = [
    "planned",
    "sown",
    "transplanted",
    "growing",
    "harvesting",
    "finished",
]
JOURNAL_KINDS: Final = ["watering", "fertilizing", "treatment", "observation", "other"]
HARVEST_UNITS: Final = ["kg", "pieces"]

# The server pushes changes over a WebSocket; polling is only a safety net.
FALLBACK_INTERVAL: Final = timedelta(minutes=30)
RECONNECT_MIN: Final = 5
RECONNECT_MAX: Final = 300
