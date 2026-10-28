"""Constants shared by the Homestead server."""

from typing import Final

CONF_LAST_FROST: Final = "last_frost"
CONF_FIRST_FROST: Final = "first_frost"

# Rough mid-latitude averages, used until the gardener sets their own.
DEFAULT_LAST_FROST_NORTH: Final = "05-15"
DEFAULT_FIRST_FROST_NORTH: Final = "10-15"
DEFAULT_LAST_FROST_SOUTH: Final = "10-15"
DEFAULT_FIRST_FROST_SOUTH: Final = "04-15"

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

SHAPE_RECT: Final = "rect"
SHAPE_ROUND: Final = "round"
SHAPES: Final = (SHAPE_RECT, SHAPE_ROUND)

# Things drawn on the plan besides the spaces.
PLAN_ITEM_KINDS: Final = (
    "lawn",
    "path",
    "terrace",
    "water",
    "tree",
    "shrub",
    "hedge",
    "compost",
    "tank",
    "shed",
    "greenhouse",
    "other",
)
# Size of an empty plan, in metres.
DEFAULT_PLAN_SIZE: Final = (12.0, 9.0)
# Largest background accepted, in bytes; the interface shrinks photos first.
MAX_BACKGROUND_BYTES: Final = 20_000_000
BACKGROUND_TYPES: Final = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

METHOD_SOW_INDOORS: Final = "sow_indoors"
METHOD_SOW_DIRECT: Final = "sow_direct"
METHOD_PLANT: Final = "plant"
METHODS: Final = (METHOD_SOW_INDOORS, METHOD_SOW_DIRECT, METHOD_PLANT)

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

JOURNAL_KINDS: Final = (
    "watering",
    "fertilizing",
    "treatment",
    "observation",
    "other",
)
HARVEST_UNITS: Final = ("kg", "pieces")

REF_LAST_FROST: Final = "last_frost"
REF_FIRST_FROST: Final = "first_frost"
AFTER_SOWING: Final = "sowing"
AFTER_TRANSPLANT: Final = "transplant"
FROST_TOLERANCES: Final = ("tender", "half_hardy", "hardy")

# Tasks due within this many days appear in the to-do list.
TASK_HORIZON_DAYS: Final = 14
# Completed tasks stay visible this many days.
DONE_VISIBLE_DAYS: Final = 7
