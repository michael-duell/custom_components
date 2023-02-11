"""Support for EnOcean sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from enocean.utils import combine_hex, to_bitarray, from_bitarray
import voluptuous as vol
import logging


from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ID,
    CONF_NAME,
    TEMP_CELSIUS,
)
from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    ClimateEntityDescription,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_HOME,
    PRESET_SLEEP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .device import EnOceanEntity
from .const import THERMOSTAT_DUTY_CYCLE, THERMOSTAT_SETTINGS, THERMOSTAT_STATE

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "EnOcean sensor"

CLIMATE_TYPE_THERMOSTAT = "thermostat"

# todo
# feed sensor (+selection)
# change duty cycle
# activate standby
# trigger reference drive


@dataclass
class EnOceanClimateEntityDescriptionMixin:
    """Mixin for required keys."""
    unique_id: Callable[[list[int]], str | None]


@dataclass
class EnOceanClimateEntityDescription(
    ClimateEntityDescription, EnOceanClimateEntityDescriptionMixin
):
    """Describes EnOcean CLIMATE entity."""


CLIMATE_DESC_THERMOSTAT = EnOceanClimateEntityDescription(
    key=CLIMATE_TYPE_THERMOSTAT,
    name="Thermostat",
    # native_unit_of_measurement=TEMP_CELSIUS,
    icon="mdi:thermostat",
    unique_id=lambda dev_id: f"{combine_hex(dev_id)}-{CLIMATE_TYPE_THERMOSTAT}",
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS, default=CLIMATE_TYPE_THERMOSTAT): cv.string,
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

    entities: list[EnOceanClimate] = []
    if sensor_type == CLIMATE_TYPE_THERMOSTAT:
        entities = [
            EnOceanThermostatSensor(
                dev_id,
                dev_name,
                CLIMATE_DESC_THERMOSTAT
            )
        ]

    add_entities(entities)


class EnOceanClimate(EnOceanEntity, RestoreEntity, ClimateEntity):
    """Representation of an  EnOcean sensor device such as a power meter."""
    _attr_should_poll = False

    def __init__(self, dev_id, dev_name, description: EnOceanClimateEntityDescription):
        """Initialize the EnOcean sensor device."""
        super().__init__(dev_id, dev_name)
        self.entity_description = description
        self._attr_name = f"{description.name} {dev_name}"
        self._attr_unique_id = description.unique_id(dev_id)

    @property
    def unique_id(self) -> str:
        """Set unique id of entity."""
        return self._attr_unique_id

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


class EnOceanThermostatSensor(EnOceanClimate):
    """Representation of an EnOcean thermostat sensor device.

    """
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = [
        PRESET_AWAY,
        PRESET_COMFORT,
        PRESET_HOME,
        PRESET_SLEEP,
    ]
    _attr_icon = "mdi:thermostat"
    _attr_max_temp = THERMOSTAT_SETTINGS["max"]
    _attr_min_temp = THERMOSTAT_SETTINGS["min"]
    _attr_target_temperature_step = THERMOSTAT_SETTINGS["step"]
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(
        self,
        dev_id,
        dev_name,
        description: EnOceanClimateEntityDescription
    ):
        """Initialize the EnOcean thermostat sensor device."""
        super().__init__(dev_id, dev_name, description)

        # self.commands =
        self._attr_native_value = None
        self._state = THERMOSTAT_STATE.OFF
        self._valve_position = 0
        self._target_temperature = 20
        self._current_temperature = 0
        self.teach_in = False
        self._harvesting_active = False
        self._chargelevel_ok = False
        self._window_open = False
        self._communication_ok = False
        self._signalstrength_ok = False
        self._actuator_ok = False
        self._trigger_reference_run = False
        self._duty_cycle = THERMOSTAT_DUTY_CYCLE.AUTO
        self._summer_mode = False
        self._external_tem_sensor = False
        self._standby = False

    @property
    def hvac_mode(self) -> HVACMode:
        """HVAC current mode."""
        if self._state == THERMOSTAT_STATE.OFF:
            return HVACMode.OFF

        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """HVAC current action."""
        if self._state == THERMOSTAT_STATE.OFF:
            return HVACAction.OFF
        elif self._valve_position > 0:
            return HVACAction.HEATING

        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return PRESET_HOME

    @property
    def target_temperature(self) -> float | None:
        """Set target temperature."""
        return self._target_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return self._current_temperature

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return {
            "valve_position": self._valve_position,
            "target_temperature": self._target_temperature,
            "current_temperature": self._current_temperature,
            "harvesting_active": self._harvesting_active,
            "window_open": self._window_open,
            # "duty_cycle": self.duty_cycle,
            # "standby": self.standby,
            "chargelevel_ok": self._chargelevel_ok,
            "communication_ok": self._communication_ok,
            "signalstrength_ok": self._signalstrength_ok,
            "actuator_ok": self._actuator_ok,
            "teach:in": self.teach_in
        }

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            _LOGGER.error("not implemented")
        elif hvac_mode == HVACMode.HEAT:
            _LOGGER.error("not implemented")

    def value_changed(self, packet):

        _LOGGER.debug("[%s] incoming data: %s", self.dev_name, packet.data)

        databits = to_bitarray(packet.data)
        self._attr_native_value = databits

        #optional = [0x03]
        # optional.extend(self.dev_id)
        #optional.extend([0xFF, 0x00])
        # self.send_command(
        #    data=[0xA5, 0x28, 0x50, 0x04, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00],
        #    optional=optional,
        #    packet_type=0x01,
        #
        # )

        self.teach_in = not databits[36]

        if self.teach_in:
            # teach-in
            self._state = THERMOSTAT_STATE.TEACH_IN
            self.handle_teachin_telegram(databits)

        else:
            # normal mode
            self._state = THERMOSTAT_STATE.OPERATIONAL
            self.handle_data_telegram(databits)


        """Update the internal state of the sensor."""
        self.schedule_update_ha_state()

    def handle_data_telegram(self, databits):
        _LOGGER.debug("handle data telegram")
        # extract properties
        self._valve_position = from_bitarray(databits[8:16])
        local_offset_mode = databits[16]  # should always be 1
        self._current_temperature = from_bitarray(databits[24:32])/2.0
        tslmode = databits[32]
        self._harvesting_active = databits[33]
        self._chargelevel_ok = databits[34]
        self._window_open = databits[35]
        self._communication_ok = not databits[37]
        self._signalstrength_ok = not databits[38]
        self._actuator_ok = not databits[39]

        # if lom == 0 bit 9...15 represents temprature difference to the current target temperatur
        # -> room contol only sends the valve position, actuator does not know the target temperature
        if (local_offset_mode == 1):
            self._target_temperature = from_bitarray(databits[17:24])/2.0

        # trigger a warning, if the TSL does not match value sent to ACT (selection of temperature sensor (ext/int) )
        if (tslmode != self._external_tem_sensor):
            text = "internal sensor"
            if (tslmode == 1):
                text = "external sensor"
            _LOGGER.warning(
                "expected actuator to use %s (TSL=%s)", text, tslmode)

        self.send_response()

    def handle_teachin_telegram(self, databits):
        _LOGGER.debug("handle teach in telegram")
        # extract properties
        program = hex(from_bitarray(databits[0:8]))
        function = hex(from_bitarray(databits[8:14]))
        type = hex(from_bitarray(databits[14:21]))
        manufacturer_id = hex(from_bitarray(databits[21:32]))

        # check properties
        if (program != 0xA5):
            _LOGGER.error("unexpected program id: %s, expected 0xA5", program)
            return
        if (function != 0x20):
            _LOGGER.error(
                "unexpected function id: %s, expected 0x20", function)
            return
        if (type != 0x06):
            _LOGGER.error("unexpected program id: %s, expected 0x0", type)
            return
        if (manufacturer_id != 0x49):
            _LOGGER.error(
                "unexpected type: %s, expected 0x45 (Micropelt)", type)
            return

        # send success
        optional = [0x03]
        optional.extend([0xFF, 0xFF, 0xFF, 0xFF])
        optional.extend([0xFF, 0x00])
        self.send_command(
            data=[0xA5, 0x80, 0x30, 0x49, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00],
            optional=optional,
            packet_type=0x01,
        )

        # send first telegram
        self.send_response()

    def send_response(self):
        data = [0xA5]
        # DB3
        data.extend(hex(self.target_temperature))
        # DB2
        if (self._external_tem_sensor):
            # todo: implement feed temperature
            data.extend(0x00)
        else:
            data.extend(0x00)
        # DB1
        duty_bits = to_bitarray(self._duty_cycle)
        data.extend(from_bitarray([self._trigger_reference_run, duty_bits[2], duty_bits[1],
                    duty_bits[0], self._summer_mode, True, self._external_tem_sensor, self._standby]))

        #only trigger stanby and reference run once
        self._trigger_reference_run = False
        self._standby = False

        # DB0
        data.extend(0x80)
        # extend date with 0 (place holder for senderid and status)
        data = [0x00, 0x00, 0x00, 0x00, 0x00]

        optional = [0x03]
        optional.extend([0xFF, 0xFF, 0xFF, 0xFF])
        optional.extend([0xFF, 0x00])
        self.send_command(
            data=[0xA5, 0x80, 0x30, 0x49, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00],
            optional=optional,
            packet_type=0x01,
        )
