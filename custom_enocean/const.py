"""Constants for the ENOcean integration."""
import logging

from homeassistant.const import Platform

DOMAIN = "custom_enocean"
DATA_ENOCEAN = "custom_enocean"
ENOCEAN_DONGLE = "dongle"

ERROR_INVALID_DONGLE_PATH = "invalid_dongle_path"

SIGNAL_RECEIVE_MESSAGE = "enocean.receive_message"
SIGNAL_SEND_MESSAGE = "enocean.send_message"

LOGGER = logging.getLogger(__package__)

PLATFORMS = [
    Platform.LIGHT,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]

#sensor attributes
ATTR_VALVE_POSITION = "valve_position"
ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_HARVESTING_ACTIVE = "harvesting_active"
ATTR_WINDOW_OPEN = "window_open"
ATTR_CHARGELEVEL_OK = "chargelevel_ok"
ATTR_COMUNICATION_OK = "communication_ok"
ATTR_SIGNALSTRENGTH_OK = "signalstrength_ok"
ATTR_ACTUATOR_OK = "actuator_ok"