"""Support for EnOcean sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from enocean.utils import combine_hex, to_bitarray, from_bitarray
import voluptuous as vol
import logging

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ID,
    CONF_NAME,
    PERCENTAGE,
    POWER_WATT,
    STATE_CLOSED,
    STATE_OPEN,
    TEMP_CELSIUS
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback, AddEntitiesCallback)
#from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .device import EnOceanEntity
from .const import (
    DOMAIN)
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "EnOcean sensor"

SENSOR_TYPE_HUMIDITY = "humidity"
SENSOR_TYPE_TEMPERATURE = "temperature"
SENSOR_TYPE_BRIGHTNESS = "brightness"
SENSOR_TYPE_MULTI = "multi"

EVENT_NEW_DATA = "multisensor-new_data"


@dataclass
class EnOceanSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    unique_id: Callable[[list[int]], str | None]


@dataclass
class EnOceanSensorEntityDescription(
    SensorEntityDescription, EnOceanSensorEntityDescriptionMixin
):
    """Describes EnOcean sensor entity."""


SENSOR_DESC_TEMPERATURE = EnOceanSensorEntityDescription(
    key=SENSOR_TYPE_TEMPERATURE,
    name="Temperature",
    native_unit_of_measurement=TEMP_CELSIUS,
    icon="mdi:thermometer",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    unique_id=lambda dev_id: f"{combine_hex(dev_id)}-{SENSOR_TYPE_TEMPERATURE}",
)

SENSOR_DESC_HUMIDITY = EnOceanSensorEntityDescription(
    key=SENSOR_TYPE_HUMIDITY,
    name="Humidity",
    native_unit_of_measurement=PERCENTAGE,
    icon="mdi:water-percent",
    device_class=SensorDeviceClass.HUMIDITY,
    state_class=SensorStateClass.MEASUREMENT,
    unique_id=lambda dev_id: f"{combine_hex(dev_id)}-{SENSOR_TYPE_HUMIDITY}",
)

SENSOR_DESC_BRIGHTNESS = EnOceanSensorEntityDescription(
    key=SENSOR_TYPE_HUMIDITY,
    name="Brightness",
    native_unit_of_measurement=PERCENTAGE,
    icon="mdi:sun-wireless",
    device_class=SensorDeviceClass.ILLUMINANCE,
    state_class=SensorStateClass.MEASUREMENT,
    unique_id=lambda dev_id: f"{combine_hex(dev_id)}-{SENSOR_TYPE_BRIGHTNESS}",
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS, default=SENSOR_TYPE_MULTI): cv.string,
        vol.Optional("climate-id", default=""): cv.string
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an EnOcean sensor device."""
    dev_id = config[CONF_ID]
    dev_name = config[CONF_NAME]
    sensor_type = config[CONF_DEVICE_CLASS]
    climate_id = config["climate-id"]

    if sensor_type == SENSOR_TYPE_MULTI:
        multisensor = EnOceanMultiSensor(dev_id, dev_name, climate_id)

        add_entities([
            multisensor,
            MultiSensorSubelement(
                multisensor, dev_id, dev_name, 'temperature', SENSOR_DESC_TEMPERATURE),
            MultiSensorSubelement(multisensor, dev_id,
                                  dev_name, 'humidity', SENSOR_DESC_HUMIDITY),
            MultiSensorSubelement(
                multisensor, dev_id, dev_name, 'illumination', SENSOR_DESC_BRIGHTNESS)
        ])


class EnOceanSensor(EnOceanEntity, RestoreEntity):
    """Representation of an  EnOcean sensor device such as a power meter."""

    def __init__(self, dev_id, dev_name):
        """Initialize the EnOcean sensor device."""
        super().__init__(dev_id, dev_name)
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        # If not None, we got an initial value.
        await super().async_added_to_hass()
        if self._attr_native_value is not None:
            return

        if (state := await self.async_get_last_state()) is not None:
            self._attr_native_value = state.state

    def value_changed(self, packet):
        """Update the internal state of the sensor."""


class EnOceanMultiSensor(EnOceanSensor, SensorEntity):
    """Representation of an EnOcean power sensor.

    EEPs (EnOcean Equipment Profiles):
    - A5-12-01 (Automated Meter Reading, Electricity)
    """

    def __init__(
        self,
        dev_id,
        dev_name,
        climate_id
    ):

        self._attr_name = dev_name
        self._climate_id = climate_id

        """Initialize the EnOcean thermostat sensor device."""
        super().__init__(dev_id, dev_name)
        # data-telegram
        self._temperature = 0
        self._humidity = 0
        self._illumination = 0
        self._accelelleration_status = 0
        self._accelelleration_x = 0
        self._accelelleration_y = 0
        self._accelelleration_z = 0
        # signal telegram
        self._energy_status = 0
        self._harvester_delivery = 0
        self._standby = False
        self._backup_energy = 0

    @property
    def state(self) -> str | None:
        """Return the current state."""
        if self._standby:
            return "Off"

        return "On"

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return {
            "energy status": self._energy_status,
            "harvester delivery": self._harvester_delivery,
            "backup energy": self._backup_energy
        }

    def value_changed(self, packet):

        _LOGGER.debug("[%s] incoming data: %s", self.dev_name, packet.data)

        self._standby = False
        databits = to_bitarray(packet.data)

        # check program type
        program = (from_bitarray(databits[0:8]))
        if (program == 0xd2):
            self.handle_data_telegram(databits)

            self.hass.services.call('custom_enocean', 'set_external_temperature', {
                'entity_id': self._climate_id,
                'temperature': self._temperature
            })

            _LOGGER.debug("External temperature set to %s for climate %s", self._temperature, self._climate_id)

        elif (program == 0xd0):
            self.handle_signal_telegram(databits)
        else:
            _LOGGER.error(
                "[%s] unexpected program id: %s", self.dev_name, program)

        self.schedule_update_ha_state()

    def handle_data_telegram(self, databits):
        _LOGGER.debug("[%s] handle data telegram", self.dev_name)

        # extract properties
        self._temperature = from_bitarray(databits[8:18]) * 0.1 - 40
        self._humidity = from_bitarray(databits[18:26]) * 0.5
        self._illumination = from_bitarray(databits[26:43])
        self._accelelleration_status = from_bitarray(databits[43:45])
        self._accelelleration_x = from_bitarray(databits[45:55]) * 0.005 - 2.5
        self._accelelleration_y = from_bitarray(databits[55:65]) * 0.005 - 2.5
        self._accelelleration_z = from_bitarray(databits[65:74]) * 0.005 - 2.5

        _LOGGER.debug("[%s] temperature: %s", self.dev_name, self._temperature)
        _LOGGER.debug("[%s] humidity: %s", self.dev_name, self._humidity)
        _LOGGER.debug("[%s] illumination: %s",
                      self.dev_name, self._illumination)
        _LOGGER.debug("[%s] acc-status: %s", self.dev_name,
                      self._accelelleration_status)
        _LOGGER.debug("[%s] acc-x: %s", self.dev_name, self._accelelleration_x)
        _LOGGER.debug("[%s] acc-y: %s", self.dev_name, self._accelelleration_y)
        _LOGGER.debug("[%s] acc-z: %s", self.dev_name, self._accelelleration_z)

    def handle_signal_telegram(self, databits):
        _LOGGER.debug("[%s] handle signal telegram", self.dev_name)

        signal_type = from_bitarray(databits[8:16])

        # energy status
        if (signal_type == 0x06):
            self._energy_status = from_bitarray(databits[16:24])
        # energy delivery of harvester
        elif (signal_type == 0x0d):
            self._harvester_delivery = from_bitarray(databits[16:24])
        # radio diabled
        elif (signal_type == 0x0e):
            self._standby = true
        # backup battery status
        elif (signal_type == 0x10):
            self._backup_energy = from_bitarray(databits[16:24])


class MultiSensorSubelement(SensorEntity):

    def __init__(
        self,
        multisensor,
        dev_id,
        dev_name,
        type,
        description: EnOceanSensorEntityDescription
    ):
        """Initialize the EnOcean thermostat sensor device."""
        self.multisensor = multisensor
        self.entity_description = description
        self._attr_name = f"{description.name} {dev_name}"
        self._attr_unique_id = description.unique_id(dev_id)
        self._type = type
        self.dev_id = dev_id
        self.dev_name = dev_name

    @property
    def native_value(self):
        """Return value of sensor."""
        if self._type == 'temperature':
            return self.multisensor._temperature
        elif self._type == 'humidity':
            return self.multisensor._humidity
        elif self._type == 'illumination':
            return self.multisensor._illumination

        return ""

    @property
    def native_unit_of_measurement(self):
        """Get the unit of measurement."""
        if self._type == 'temperature':
            return "°C"
        elif self._type == 'humidity':
            return "%"
        elif self._type == 'illumination':
            return "lx"

        return ""
