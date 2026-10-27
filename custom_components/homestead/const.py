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

# Subentries
SUBENTRY_SPACE: Final = "space"
SUBENTRY_PLANTING: Final = "planting"

# Spaces
CONF_SPACE_TYPE: Final = "space_type"
CONF_FROST_SHIFT: Final = "frost_shift"
CONF_AREA: Final = "area"

SPACE_BED: Final = "bed"
SPACE_RAISED_BED: Final = "raised_bed"
SPACE_GREENHOUSE: Final = "greenhouse"
SPACE_CONTAINER: Final = "container"
# How many weeks earlier in spring (and later in autumn) a space allows,
# compared with open ground. An unheated greenhouse gains about a month.
DEFAULT_FROST_SHIFT: Final = {
    SPACE_BED: 0,
    SPACE_RAISED_BED: 1,
    SPACE_GREENHOUSE: 4,
    SPACE_CONTAINER: 0,
}

# Plantings
CONF_SPACE: Final = "space"
CONF_SPECIES: Final = "species"
CONF_VARIETY: Final = "variety"
CONF_START: Final = "start"
CONF_METHOD: Final = "method"
CONF_WINDOW: Final = "window"
CONF_SEASON: Final = "season"
CONF_QUANTITY: Final = "quantity"

METHOD_SOW_INDOORS: Final = "sow_indoors"
METHOD_SOW_DIRECT: Final = "sow_direct"
METHOD_PLANT: Final = "plant"

STAGE_PLANNED: Final = "planned"
STAGE_SOWN: Final = "sown"
STAGE_TRANSPLANTED: Final = "transplanted"
STAGE_GROWING: Final = "growing"
STAGE_HARVESTING: Final = "harvesting"
STAGE_FINISHED: Final = "finished"
STAGES: Final = [
    STAGE_PLANNED,
    STAGE_SOWN,
    STAGE_TRANSPLANTED,
    STAGE_GROWING,
    STAGE_HARVESTING,
    STAGE_FINISHED,
]

# Catalogue
REF_LAST_FROST: Final = "last_frost"
REF_FIRST_FROST: Final = "first_frost"
AFTER_SOWING: Final = "sowing"
AFTER_TRANSPLANT: Final = "transplant"
FROST_TOLERANCES: Final = ("tender", "half_hardy", "hardy")

# Tasks due within this many days appear in the to-do list.
TASK_HORIZON_DAYS: Final = 14
# Completed tasks stay visible this many days.
DONE_VISIBLE_DAYS: Final = 7
