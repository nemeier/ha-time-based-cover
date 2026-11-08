"""Constants for the Time Based Cover integration."""

from datetime import timedelta

DOMAIN = "time_based_cover"

CONF_SOURCE_COVER = "source_cover"
CONF_TRAVEL_TIME_UP = "travel_time_up"
CONF_TRAVEL_TIME_DOWN = "travel_time_down"

DEFAULT_TRAVEL_TIME = 30.0
MIN_TRAVEL_TIME = 1.0
MAX_TRAVEL_TIME = 300.0

DIRECTION_UP = "up"
DIRECTION_DOWN = "down"

POSITION_OPEN = 100
POSITION_CLOSED = 0

# How often the estimated position is pushed to Home Assistant while moving
UPDATE_INTERVAL = timedelta(seconds=1)

SERVICE_SET_KNOWN_POSITION = "set_known_position"
