"""Constants for the ENOcean integration."""
import logging

from enum import Enum
from homeassistant.const import Platform
from typing import Final

DOMAIN = "custom_enocean"
DATA_ENOCEAN = "custom_enocean"
ENOCEAN_DONGLE = "dongle"

ERROR_INVALID_DONGLE_PATH = "invalid_dongle_path"

SIGNAL_RECEIVE_MESSAGE = "enocean.receive_message"
SIGNAL_SEND_MESSAGE = "enocean.send_message"

LOGGER = logging.getLogger(__package__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE
]

THERMOSTAT_SETTINGS: Final = {
    "min": 4,
    "max": 31,
    "step": 0.5,
}

class THERMOSTAT_STATE(Enum):
    OFF = 0
    TEACH_IN = 1
    OPERATIONAL = 2
    ERROR = 3