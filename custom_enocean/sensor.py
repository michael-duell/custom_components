"""Support for EnOcean sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from enocean.utils import combine_hex
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
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .device import EnOceanEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "EnOcean sensor"

SENSOR_TYPE_THERMOSTAT = "thermostat"


@dataclass
class EnOceanSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    unique_id: Callable[[list[int]], str | None]


@dataclass
class EnOceanSensorEntityDescription(
    SensorEntityDescription, EnOceanSensorEntityDescriptionMixin
):
    """Describes EnOcean sensor entity."""

SENSOR_DESC_THERMOSTAT = EnOceanSensorEntityDescription(
    key=SENSOR_TYPE_THERMOSTAT,
    name="Thermostat",
    #native_unit_of_measurement=TEMP_CELSIUS,
    icon="mdi:thermostat",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    unique_id=lambda dev_id: f"{combine_hex(dev_id)}-{SENSOR_TYPE_THERMOSTAT}",
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS, default=SENSOR_TYPE_THERMOSTAT): cv.string,
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

    entities: list[EnOceanSensor] = []
    if sensor_type == SENSOR_TYPE_THERMOSTAT:
        entities = [
            EnOceanThermostatSensor(
                dev_id,
                dev_name,
                SENSOR_DESC_THERMOSTAT
            )
        ]

    add_entities(entities)


class EnOceanSensor(EnOceanEntity, RestoreEntity, SensorEntity):
    """Representation of an  EnOcean sensor device such as a power meter."""
    _attr_should_poll = False

    def __init__(self, dev_id, dev_name, description: EnOceanSensorEntityDescription):
        """Initialize the EnOcean sensor device."""
        super().__init__(dev_id, dev_name)
        self.entity_description = description
        self._attr_name = f"{description.name} {dev_name}"
        self._attr_unique_id = description.unique_id(dev_id)

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


class EnOceanThermostatSensor(EnOceanSensor):
    """Representation of an EnOcean thermostat sensor device.

    """

    def __init__(
        self,
        dev_id,
        dev_name,
        description: EnOceanSensorEntityDescription
    ):
        """Initialize the EnOcean thermostat sensor device."""
        super().__init__(dev_id, dev_name, description)

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return {
            "valve_position": self._is_open,
        }


    def value_changed(self, packet):

        _LOGGER.info("[%s] incoming data: %s", self.dev_name, packet.data)



        """Update the internal state of the sensor."""
        self.schedule_update_ha_state()
