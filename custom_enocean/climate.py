"""Support for EnOcean sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from enocean.utils import combine_hex, to_bitarray, from_bitarray
import voluptuous as vol
import logging


from homeassistant.const import (
    ATTR_TEMPERATURE,
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
from homeassistant.helpers import entity_platform
from homeassistant.config_entries import ConfigEntry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.template import is_number

from .device import EnOceanEntity

from .const import (
    CONF_USE_EXTERNAL_TEMP,
    DUTY_CYCLES,
    SERVICE_SET_DUTY_CYCLE,
    SERVICE_SET_EXT_TEMP,
    SERVICE_TRIGGER_REFERENCE_RUN,
    SERVICE_TRIGGER_STANDBY,
    THERMOSTAT_DUTY_CYCLE,
    THERMOSTAT_SETTINGS,
    THERMOSTAT_STATE)


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
        vol.Optional(CONF_USE_EXTERNAL_TEMP, default=False): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an EnOcean sensor device."""
    dev_id = config[CONF_ID]
    dev_name = config[CONF_NAME]
    sensor_type = config[CONF_DEVICE_CLASS]
    use_external_temp_sensor = config[CONF_USE_EXTERNAL_TEMP]

    entities: list[EnOceanClimate] = []
    if sensor_type == CLIMATE_TYPE_THERMOSTAT:
        entities = [
            EnOceanThermostatSensor(
                dev_id,
                dev_name,
                use_external_temp_sensor,
                CLIMATE_DESC_THERMOSTAT
            )
        ]

    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_TRIGGER_STANDBY, {}, "set_standby"
    )

    platform.async_register_entity_service(
        SERVICE_TRIGGER_REFERENCE_RUN, {}, "set_reference_run"
    )

    platform.async_register_entity_service(
        SERVICE_SET_DUTY_CYCLE, {vol.Required(
            'duty_cycle'): vol.In(DUTY_CYCLES)}, "set_duty_cycle"
    )

    platform.async_register_entity_service(
        SERVICE_SET_EXT_TEMP, { vol.Required('temperature'): vol.Coerce(float) }, "async_set_external_temperature"
    )

def limit_value(value, min_value, max_value):
    """
    Begrenzt den Wert auf einen Bereich zwischen min_value und max_value.
    """
    if value < min_value:
        return min_value
    elif value > max_value:
        return max_value
    else:
        return value


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
        use_external_temp_sensor,
        description: EnOceanClimateEntityDescription
    ):
        """Initialize the EnOcean thermostat sensor device."""
        super().__init__(dev_id, dev_name, description)

        self._attr_native_value = None
        self._state = THERMOSTAT_STATE.OFF
        self._valve_position = 0
        self._use_internal_setpoint = False
        self._target_temperature = 20
        self._current_temperature = 0
        self._use_external_temp_sensor = use_external_temp_sensor
        self._external_temperature = 0
        self._harvesting_active = False
        self._chargelevel_ok = False
        self._window_open = False
        self._communication_ok = False
        self._signalstrength_ok = False
        self._actuator_ok = False
        self._trigger_reference_run = False
        self._duty_cycle = THERMOSTAT_DUTY_CYCLE["AUTO"]
        self._summer_mode = False
        self._trigger_standby = False

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
        elif self._valve_position > 50:
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
            "valve position": self._valve_position,
            "target temperature": self._target_temperature,
            "current temperature": self._current_temperature,

            "harvesting active": self._harvesting_active,
            "window open": self._window_open,
            "duty cycle": self._duty_cycle,
            "chargelevel ok": self._chargelevel_ok,
            "communication ok": self._communication_ok,
            "signalstrength ok": self._signalstrength_ok,
            "actuator ok": self._actuator_ok,

            "use external temp. sensor": self._use_external_temp_sensor,
            "external temperature": self._external_temperature,

        }

    @property
    def state(self) -> str | None:
        """Return the current state."""
        if self._state is None:
            return None

        return self._state.value

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        mapping = {
            PRESET_AWAY: ACTIVE_STATE_AWAY,
            PRESET_COMFORT: ACTIVE_STATE_COMFORT,
            PRESET_HOME: ACTIVE_STATE_HOME,
            PRESET_SLEEP: ACTIVE_STATE_SLEEP,
        }
        if preset_mode in mapping:
            # set active state
            _LOGGER.error("not implemented")

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self._summer_mode = True
            self._state = THERMOSTAT_STATE.OFF
        elif hvac_mode == HVACMode.HEAT:
            self._summer_mode = False
            self._state = THERMOSTAT_STATE.OPERATIONAL
        self.schedule_update_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._target_temperature = limit_value(kwargs[ATTR_TEMPERATURE],self._attr_min_temp,self._attr_max_temp)
            self._use_internal_setpoint = True

        await self.async_update_ha_state()


    def set_standby(self):
        """Set standby"""
        self._trigger_standby = True

    def set_reference_run(self):
        """Set reference run"""
        self._trigger_reference_run = True

    def set_duty_cycle(self, duty_cycle: str):
        """Set duty cycle"""
        self._duty_cycle = THERMOSTAT_DUTY_CYCLE[duty_cycle]
        self.schedule_update_ha_state()

    async def async_set_external_temperature(self, temperature: int):
        """Set external temperature"""
        self._external_temperature =  limit_value(temperature, 0, 80)
        await self.async_update_ha_state()

    def value_changed(self, packet):

        _LOGGER.debug("[%s] incoming data: %s", self.dev_name, packet.data)

        databits = to_bitarray(packet.data)
        self._attr_native_value = databits

        teach_in = not databits[36]

        if teach_in:
            # teach-in
            self.handle_teachin_telegram(databits)

        else:
            # normal mode
            self.handle_data_telegram(databits)

        """Update the internal state of the sensor."""
        self.schedule_update_ha_state()

    def handle_data_telegram(self, databits):
        _LOGGER.debug("[%s] handle data telegram", self.dev_name)

        if (not self._summer_mode):
            self._state = THERMOSTAT_STATE.OPERATIONAL
        else:
            self._state = THERMOSTAT_STATE.OFF

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
        if (local_offset_mode == 1 and not self._use_internal_setpoint):
            self._target_temperature = from_bitarray(databits[17:24])/2.0

        self._use_internal_setpoint = False

        # trigger a warning, if the TSL does not match value sent to ACT (selection of temperature sensor (ext/int) )
        if (tslmode != self._use_external_temp_sensor):
            text = "internal sensor"
            if (tslmode == 1):
                text = "external sensor"
            _LOGGER.warning(
                "[%s] expected actuator to use %s (TSL=%s)", self.dev_name, text, tslmode)

        # trigger warnig bits
        if (not (self._chargelevel_ok)):
            _LOGGER.warning(
                "[%s] low chargelevel", self.dev_name)
        if (not (self._communication_ok)):
            _LOGGER.warning(
                "[%s] six or more consecuetive rdio communication errors occured", self.dev_name)
        if (not (self._signalstrength_ok)):
            _LOGGER.warning(
                "[%s] weak signal strength (<-77dBm)", self.dev_name)
        if (not (self._actuator_ok)):
            _LOGGER.error(
                "[%s] actuator is blocked", self.dev_name)

        self.send_response()

    def handle_teachin_telegram(self, databits):
        _LOGGER.debug("[%s] handle teach in telegram", self.dev_name)
        self._state = THERMOSTAT_STATE.TEACH_IN

        # extract properties
        program = (from_bitarray(databits[0:8]))
        function = (from_bitarray(databits[8:14]))
        type = (from_bitarray(databits[14:21]))
        manufacturer_id = (from_bitarray(databits[21:32]))

        # check properties
        if (program != 0xa5):
            _LOGGER.error(
                "[%s] unexpected program id: %s, expected 0xa5", self.dev_name, program)
            return
        if (function != 0x20):
            _LOGGER.error(
                "[%s] unexpected function id: %s, expected 0x20", self.dev_name, function)
            return
        if (type != 0x6):
            _LOGGER.error(
                "[%s] unexpected type: %s, expected 0x06", self.dev_name, type)
            return
        if (manufacturer_id != 0x49):
            _LOGGER.error(
                "[%s] unexpected type: %s, expected 0x45 (Micropelt)", self.dev_name, type)
            return

        # send success
        optional = [0x03]
        optional.extend([0xff, 0xff, 0xff, 0xff])
        optional.extend([0xff, 0x00])
        self.send_command(
            data=[0xa5, 0x80, 0x30, 0x49, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00],
            optional=optional,
            packet_type=0x01,
        )

        # send first telegram
        self.send_response()

    def send_response(self):
        data = [0xa5]
        # DB3
        data.extend([int(self._target_temperature * 2)])
        # DB2
        if (self._use_external_temp_sensor):
            data.extend(
                [int(limit_value( self._external_temperature * 4, 0,80))])
        else:
            data.extend([0x00])
        # DB1
        duty_bits = to_bitarray(self._duty_cycle)
        data.extend([from_bitarray([self._trigger_reference_run, duty_bits[5], duty_bits[6],
                    duty_bits[7], self._summer_mode, True, self._use_external_temp_sensor, self._trigger_standby])])

        # trigger reference run and standby only once
        self._trigger_reference_run = False
        self._trigger_standby = False

        # DB0
        data.extend([0x08])
        # extend date with 0 (place holder for senderid and status)
        data.extend([0x00, 0x00, 0x00, 0x00, 0x00])

        optional = [0x03]
        optional.extend([0xff, 0xff, 0xff, 0xff])
        optional.extend([0xff, 0x00])
        self.send_command(
            data=data,
            optional=optional,
            packet_type=0x01,
        )
