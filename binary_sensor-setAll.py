"""Support for EnOcean binary sensors."""
from __future__ import annotations

from enocean.utils import combine_hex
import voluptuous as vol

import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .device import EnOceanEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "EnOcean binary sensor"
DEPENDENCIES = ["enocean"]
EVENT_BUTTON_PRESSED = "button_pressed"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Binary Sensor platform for EnOcean."""
    dev_id = config.get(CONF_ID)
    dev_name = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)
    _LOGGER.debug("setting up enocean instance with id %s", dev_id)

    add_entities([EnOceanBinarySensor(dev_id, dev_name, device_class)])


class EnOceanBinarySensor(EnOceanEntity, BinarySensorEntity):
    """Representation of EnOcean binary sensors such as wall switches.

    Supported EEPs (EnOcean Equipment Profiles):
    - F6-02-01 (Light and Blind Control - Application Style 2)
    - F6-02-02 (Light and Blind Control - Application Style 1)
    """
    _attr_should_poll = False

    def __init__(self, dev_id, dev_name, device_class):
        """Initialize the EnOcean binary sensor."""
        super().__init__(dev_id, dev_name)
        self._device_class = device_class
        self._is_open = True
        self._attr_unique_id = f"{combine_hex(dev_id)}-{device_class}"

    @property
    def name(self):
        """Return the default name for the binary sensor."""
        return self.dev_name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def state(self) -> str:
        """Return the state"""
        # 0.8333 is the same value as astral uses
        if self._is_open:
            return "open"

        return "closed"

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return {
            "is_open": self._is_open
        }

    @property
    def is_on(self) -> bool:
        """Return true if sensor state is on."""
        return bool(self._is_open)

    def value_changed(self, packet):
        """Fire an event with the data that have changed.

        This method is called when there is an incoming packet associated
        with this platform.

        open:
            ['0xf6', '0x0', '0xfe', '0xea', '0xd', '0xc9', '0x20'] / [246, 0, 254, 234, 13, 201, 32]
         closed:
            ['0xf6', '0x10', '0xfe', '0xea', '0xd', '0xc9', '0x20'] / [246, 16, 254, 234, 13, 201, 32]
        """

        _LOGGER.info("[%s] incoming data: %s", self.dev_name, packet.data)

        #set attribute
        self._is_open = (packet.data[1] == 0)

        #set the state
        self.schedule_update_ha_state()

        #fire event
        self.hass.bus.fire(
            EVENT_BUTTON_PRESSED,
            {
                "is_open": self._is_open,
            },
        )
