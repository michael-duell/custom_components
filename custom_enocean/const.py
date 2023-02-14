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



ATTR_VALUE = "value"

SERVICE_TRIGGER_STANDBY: Final = "trigger_standby"
SERVICE_TRIGGER_REFERENCE_RUN: Final = "trigger_reference_run"
SERVICE_SET_DUTY_CYCLE: Final = "set_duty_cycle"
SERVICE_SET_EXT_TEMP: Final = "set_external_temperature"

DUTY_CYCLES = [
    "AUTO",
    "2_MIN",
    "5_MIN",
    "10_MIN",
    "20_MIN",
    "30_MIN",
    "60_MIN",
    "120_MIN"
]

CONF_USE_EXTERNAL_TEMP = "use_external_tep_sensor"

THERMOSTAT_SETTINGS: Final = {
    "min": 4,
    "max": 31,
    "step": 0.5,
}

THERMOSTAT_DUTY_CYCLE: Final ={
    "AUTO": 0,
    "2_MIN": 1,
    "5_MIN": 2,
    "10_MIN": 3,
    "20_MIN": 4,
    "30_MIN": 5,
    "60_MIN": 6,
    "120_MIN": 7
}

class THERMOSTAT_STATE(Enum):
    OFF = "off"
    TEACH_IN = "teach-in"
    OPERATIONAL ="heat"