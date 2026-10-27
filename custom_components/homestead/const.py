"""Constants for the Homestead integration."""

from typing import Final

DOMAIN: Final = "homestead"

CONF_LAST_FROST: Final = "last_frost"
CONF_FIRST_FROST: Final = "first_frost"

# Rough mid-latitude averages, only used to pre-fill the setup form.
DEFAULT_LAST_FROST_NORTH: Final = "05-15"
DEFAULT_FIRST_FROST_NORTH: Final = "10-15"
DEFAULT_LAST_FROST_SOUTH: Final = "10-15"
DEFAULT_FIRST_FROST_SOUTH: Final = "04-15"
