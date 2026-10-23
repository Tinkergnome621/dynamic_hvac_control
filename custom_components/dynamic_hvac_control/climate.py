"""Climate platform for Dynamic HVAC Control with Built-in 4-Slot Scheduling and Vacation Mode."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_utc_time,
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CHANGEOVER_DELAY,
    CONF_COMFORT_TARGET,
    CONF_HC_LOWER_BUFFER,
    CONF_HC_UPPER_BUFFER,
    CONF_SLEEP_TARGET,
    DEFAULT_CHANGEOVER_DELAY,
    DEFAULT_COMFORT_TARGET,
    DEFAULT_HC_LOWER_BUFFER,
    DEFAULT_HC_UPPER_BUFFER,
    DEFAULT_SLEEP_TARGET,
    MAX_HC_BUFFER,
    MIN_HC_BUFFER,
    MIN_RANGE_GAP,
    CONF_FAN_ON_MAX_HOURS,
    DEFAULT_FAN_ON_MAX_HOURS,
    CONF_AWAY_COOL,
    CONF_AWAY_HEAT,
    CONF_BOOST_COOL,
    CONF_BOOST_HEAT,
    CONF_COMFORT_COOL,
    CONF_COMFORT_HEAT,
    CONF_COOLING_OFFSET,
    CONF_COOLING_SWING,
    CONF_ECO_COOL,
    CONF_ECO_HEAT,
    CONF_ENABLE_SCHEDULE,
    CONF_ERRAND_DELAY,
    CONF_FAN_ENTITY,
    CONF_HEATING_OFFSET,
    CONF_HEATING_SWING,
    CONF_IMMUNITY_DURATION,
    CONF_MIN_CYCLE_DURATION,
    CONF_PRESENCE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_RETURN_TEMP_SENSOR,
    CONF_RETURN_HUMIDITY_SENSOR,
    CONF_SUPPLY_TEMP_SENSOR,
    CONF_SUPPLY_HUMIDITY_SENSOR,
    CONF_SLEEP_COOL,
    CONF_SLEEP_HEAT,
    CONF_TARGET_CLIMATE,
    CONF_TEMP_SENSOR,
    CONF_VACATION_COOL,
    CONF_VACATION_HEAT,
    CONF_WD_P1_PRESET,
    CONF_WD_P1_TIME,
    CONF_WD_P2_PRESET,
    CONF_WD_P2_TIME,
    CONF_WD_P3_PRESET,
    CONF_WD_P3_TIME,
    CONF_WD_P4_PRESET,
    CONF_WD_P4_TIME,
    CONF_WE_P1_PRESET,
    CONF_WE_P1_TIME,
    CONF_WE_P2_PRESET,
    CONF_WE_P2_TIME,
    CONF_WE_P3_PRESET,
    CONF_WE_P3_TIME,
    CONF_WE_P4_PRESET,
    CONF_WE_P4_TIME,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_HVAC_MODE,
    CONF_NOTIFY_PRESET,
    CONF_NOTIFY_SCHEDULE,
    CONF_NOTIFY_PRESENCE,
    CONF_NOTIFY_SENSOR_FALLBACK,
    DEFAULT_AWAY_COOL,
    DEFAULT_AWAY_HEAT,
    DEFAULT_BOOST_COOL,
    DEFAULT_BOOST_HEAT,
    DEFAULT_COMFORT_COOL,
    DEFAULT_COMFORT_HEAT,
    DEFAULT_COOLING_OFFSET,
    DEFAULT_COOLING_SWING,
    DEFAULT_ECO_COOL,
    DEFAULT_ECO_HEAT,
    DEFAULT_ENABLE_SCHEDULE,
    DEFAULT_ERRAND_DELAY,
    DEFAULT_HEATING_OFFSET,
    DEFAULT_HEATING_SWING,
    DEFAULT_IMMUNITY_DURATION,
    DEFAULT_MIN_CYCLE_DURATION,
    DEFAULT_NOTIFY_SERVICE,
    DEFAULT_NOTIFY_HVAC_MODE,
    DEFAULT_NOTIFY_PRESET,
    DEFAULT_NOTIFY_SCHEDULE,
    DEFAULT_NOTIFY_PRESENCE,
    DEFAULT_NOTIFY_SENSOR_FALLBACK,
    DEFAULT_SLEEP_COOL,
    DEFAULT_SLEEP_HEAT,
    DEFAULT_VACATION_COOL,
    DEFAULT_VACATION_HEAT,
    DEFAULT_WD_P1_PRESET,
    DEFAULT_WD_P1_TIME,
    DEFAULT_WD_P2_PRESET,
    DEFAULT_WD_P2_TIME,
    DEFAULT_WD_P3_PRESET,
    DEFAULT_WD_P3_TIME,
    DEFAULT_WD_P4_PRESET,
    DEFAULT_WD_P4_TIME,
    DEFAULT_WE_P1_PRESET,
    DEFAULT_WE_P1_TIME,
    DEFAULT_WE_P2_PRESET,
    DEFAULT_WE_P2_TIME,
    DEFAULT_WE_P3_PRESET,
    DEFAULT_WE_P3_TIME,
    DEFAULT_WE_P4_PRESET,
    DEFAULT_WE_P4_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PRESET_VACATION = "vacation"
SUPPORTED_PRESETS = [
    PRESET_NONE,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_AWAY,
    PRESET_SLEEP,
    PRESET_BOOST,
    PRESET_VACATION,
]

# v1.1.0 Anchor & Deadzone Band
TARGET_PRESETS = (PRESET_COMFORT, PRESET_SLEEP)  # one temperature + deadband
RANGE_PRESETS = (PRESET_ECO, PRESET_AWAY, PRESET_VACATION)  # floor (heat) + ceiling (cool)
BAND_TARGET = "target"
BAND_RANGE = "range"


def _clamp(value: float, low: float = 60.0, high: float = 85.0) -> float:
    """Clamp a temperature into the 60-85°F residential window, rounded to 0.1°F."""
    return round(max(low, min(high, float(value))), 1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dynamic HVAC Control entity."""
    entity = DynamicHvacControlEntity(hass, entry)
    hass.data[DOMAIN][entry.entry_id]["climate_entity"] = entity
    async_add_entities([entity])


class DynamicHvacControlEntity(RestoreEntity, ClimateEntity):
    """Dynamic HVAC Control entity featuring built-in 4-slot scheduling, two-way sync, and 3-tier safety."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = 60.0
    _attr_max_temp = 85.0
    _attr_target_temperature_step = 1.0
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the climate entity."""
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Dynamic HVAC Control"),
            manufacturer="Dynamic HVAC Control",
            model="Central A/C & Heat Pump Controller",
        )

        # Merge entry data and options for runtime configuration
        cfg = {**entry.data, **entry.options}

        # Target Hardware Entities & Optional Diagnostic Sensors
        self._target_climate = cfg[CONF_TARGET_CLIMATE]
        self._fan_entity = cfg.get(CONF_FAN_ENTITY)
        self._temp_sensor = cfg[CONF_TEMP_SENSOR]
        self._presence_sensor = cfg.get(CONF_PRESENCE_SENSOR)
        self._humidity_sensor = cfg.get(CONF_HUMIDITY_SENSOR)
        self._supply_temp_sensor = cfg.get(CONF_SUPPLY_TEMP_SENSOR)
        self._supply_humidity_sensor = cfg.get(CONF_SUPPLY_HUMIDITY_SENSOR)
        self._return_temp_sensor = cfg.get(CONF_RETURN_TEMP_SENSOR)
        self._return_humidity_sensor = cfg.get(CONF_RETURN_HUMIDITY_SENSOR)

        # Live Sensor Readings for UI and Diagnostics
        self._current_humidity: float | None = None
        self._supply_temperature: float | None = None
        self._supply_humidity: float | None = None
        self._return_temperature: float | None = None
        self._return_humidity: float | None = None

        # Hysteresis, Offsets, Timers & Safety
        self._cooling_swing = float(cfg.get(CONF_COOLING_SWING, DEFAULT_COOLING_SWING))
        self._heating_swing = float(cfg.get(CONF_HEATING_SWING, DEFAULT_HEATING_SWING))
        self._cooling_offset = float(cfg.get(CONF_COOLING_OFFSET, DEFAULT_COOLING_OFFSET))
        self._heating_offset = float(cfg.get(CONF_HEATING_OFFSET, DEFAULT_HEATING_OFFSET))
        self._errand_delay = int(cfg.get(CONF_ERRAND_DELAY, DEFAULT_ERRAND_DELAY))
        self._immunity_duration = int(cfg.get(CONF_IMMUNITY_DURATION, DEFAULT_IMMUNITY_DURATION))
        self._min_cycle_duration = int(cfg.get(CONF_MIN_CYCLE_DURATION, DEFAULT_MIN_CYCLE_DURATION))

        # Temperature Presets (v1.1.0)
        # Target presets: one temperature. Range presets: (floor, ceiling). Boost: separate heat/cool.
        self._target_presets: dict[str, float] = {
            PRESET_COMFORT: _clamp(cfg.get(CONF_COMFORT_TARGET, DEFAULT_COMFORT_TARGET)),
            PRESET_SLEEP: _clamp(cfg.get(CONF_SLEEP_TARGET, DEFAULT_SLEEP_TARGET)),
        }
        self._range_presets: dict[str, tuple[float, float]] = {}
        for preset, heat_key, heat_def, cool_key, cool_def in (
            (PRESET_ECO, CONF_ECO_HEAT, DEFAULT_ECO_HEAT, CONF_ECO_COOL, DEFAULT_ECO_COOL),
            (PRESET_AWAY, CONF_AWAY_HEAT, DEFAULT_AWAY_HEAT, CONF_AWAY_COOL, DEFAULT_AWAY_COOL),
            (PRESET_VACATION, CONF_VACATION_HEAT, DEFAULT_VACATION_HEAT, CONF_VACATION_COOL, DEFAULT_VACATION_COOL),
        ):
            self._range_presets[preset] = self._safe_range(
                float(cfg.get(heat_key, heat_def)), float(cfg.get(cool_key, cool_def))
            )
        self._boost_cool: float = _clamp(cfg.get(CONF_BOOST_COOL, DEFAULT_BOOST_COOL))
        self._boost_heat: float = _clamp(cfg.get(CONF_BOOST_HEAT, DEFAULT_BOOST_HEAT))

        # Heat/Cool deadband buffers (settings value; the card knobs adjust the live value)
        self._cfg_lower_buffer: float = self._safe_buffer(cfg.get(CONF_HC_LOWER_BUFFER, DEFAULT_HC_LOWER_BUFFER))
        self._cfg_upper_buffer: float = self._safe_buffer(cfg.get(CONF_HC_UPPER_BUFFER, DEFAULT_HC_UPPER_BUFFER))
        self._hc_lower_buffer: float = self._cfg_lower_buffer
        self._hc_upper_buffer: float = self._cfg_upper_buffer
        self._changeover_delay: int = int(cfg.get(CONF_CHANGEOVER_DELAY, DEFAULT_CHANGEOVER_DELAY))

        # Manual hold (preset "none") remembers what kind of setpoint the user chose
        self._hold_band: str = BAND_TARGET
        self._hold_target: float = self._target_presets[PRESET_COMFORT]
        self._hold_floor: float = self._range_presets[PRESET_ECO][0]
        self._hold_ceiling: float = self._range_presets[PRESET_ECO][1]
        self._band_type: str = BAND_TARGET

        # 4-Slot Weekday (Mon - Fri) Schedules
        self._wd_slots = [
            (cfg.get(CONF_WD_P1_TIME, DEFAULT_WD_P1_TIME), cfg.get(CONF_WD_P1_PRESET, DEFAULT_WD_P1_PRESET)),
            (cfg.get(CONF_WD_P2_TIME, DEFAULT_WD_P2_TIME), cfg.get(CONF_WD_P2_PRESET, DEFAULT_WD_P2_PRESET)),
            (cfg.get(CONF_WD_P3_TIME, DEFAULT_WD_P3_TIME), cfg.get(CONF_WD_P3_PRESET, DEFAULT_WD_P3_PRESET)),
            (cfg.get(CONF_WD_P4_TIME, DEFAULT_WD_P4_TIME), cfg.get(CONF_WD_P4_PRESET, DEFAULT_WD_P4_PRESET)),
        ]

        # 4-Slot Weekend (Sat - Sun) Schedules
        self._we_slots = [
            (cfg.get(CONF_WE_P1_TIME, DEFAULT_WE_P1_TIME), cfg.get(CONF_WE_P1_PRESET, DEFAULT_WE_P1_PRESET)),
            (cfg.get(CONF_WE_P2_TIME, DEFAULT_WE_P2_TIME), cfg.get(CONF_WE_P2_PRESET, DEFAULT_WE_P2_PRESET)),
            (cfg.get(CONF_WE_P3_TIME, DEFAULT_WE_P3_TIME), cfg.get(CONF_WE_P3_PRESET, DEFAULT_WE_P3_PRESET)),
            (cfg.get(CONF_WE_P4_TIME, DEFAULT_WE_P4_TIME), cfg.get(CONF_WE_P4_PRESET, DEFAULT_WE_P4_PRESET)),
        ]
        self._enable_schedule = cfg.get(CONF_ENABLE_SCHEDULE, DEFAULT_ENABLE_SCHEDULE)

        # Notification Trigger Settings
        self._notify_service: str = str(cfg.get(CONF_NOTIFY_SERVICE, DEFAULT_NOTIFY_SERVICE)).strip()
        self._notify_hvac_mode: bool = bool(cfg.get(CONF_NOTIFY_HVAC_MODE, DEFAULT_NOTIFY_HVAC_MODE))
        self._notify_preset: bool = bool(cfg.get(CONF_NOTIFY_PRESET, DEFAULT_NOTIFY_PRESET))
        self._notify_schedule: bool = bool(cfg.get(CONF_NOTIFY_SCHEDULE, DEFAULT_NOTIFY_SCHEDULE))
        self._notify_presence: bool = bool(cfg.get(CONF_NOTIFY_PRESENCE, DEFAULT_NOTIFY_PRESENCE))
        self._notify_sensor_fallback: bool = bool(cfg.get(CONF_NOTIFY_SENSOR_FALLBACK, DEFAULT_NOTIFY_SENSOR_FALLBACK))

        # Internal State Machine
        self._hvac_mode: HVACMode = HVACMode.COOL
        self._hvac_action: HVACAction = HVACAction.IDLE
        self._last_active_hvac_mode: HVACMode = HVACMode.COOL  # Restores correct mode on turn_on
        self._last_conditioning_direction: str = (
            HVACMode.HEAT if dt_util.now().month in (10, 11, 12, 1, 2, 3, 4) else HVACMode.COOL
        )
        self._target_temperature: float = self._target_presets[PRESET_COMFORT]
        self._target_temperature_low: float = self._target_temperature - self._hc_lower_buffer
        self._target_temperature_high: float = self._target_temperature + self._hc_upper_buffer
        self._preset_mode: str = PRESET_COMFORT
        self._current_temperature: float | None = None
        self._active_sensor_source: str = "remote"  # "remote", "fallback_physical", or "emergency"
        self._logged_sensor_fallback: bool = False
        self._logged_emergency_fallback: bool = False
        self._last_scheduled_slot: str | None = None
        self._user_fan_mode: str = "auto"
        # Fan On auto-revert (next schedule slot, Away, or max-hours cap)
        self._fan_on_max_hours: int = int(cfg.get(CONF_FAN_ON_MAX_HOURS, DEFAULT_FAN_ON_MAX_HOURS))
        self._fan_on_since: datetime | None = None
        self._fan_on_until: datetime | None = None
        self._fan_revert_reason: str = "none"
        self._fan_cap_cancel = None

        # Two-Way Dial Sync & Hardware State Tracking
        self._last_sent_physical_mode: str | None = None
        self._last_sent_target_temp: float | None = None
        self._physical_last_reported_target: float | None = None
        self._ignore_physical_target_until: datetime | None = None
        self._ignore_mode_change_until: datetime | None = None

        # Safety & Cycle Timestamps
        self._last_cycle_start: datetime | None = None
        self._last_cycle_stop: datetime | None = None

        # Errand Grace & Away Immunity Timers
        self._errand_timer_cancel = None
        self._errand_timer_end: datetime | None = None
        self._immunity_timer_cancel = None
        self._immunity_timer_end: datetime | None = None
        self._is_starting_up: bool = True

        self._listeners: list[Any] = []

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------

    @property
    def should_poll(self) -> bool:
        """Return False as climate entity is 100% event-driven."""
        return False

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if self._hvac_mode == HVACMode.HEAT_COOL:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        if self._fan_entity:
            features |= ClimateEntityFeature.FAN_MODE
        return features

    @property
    def preset_modes(self) -> list[str]:
        """Available preset modes."""
        return SUPPORTED_PRESETS

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        return self._hvac_action

    @property
    def preset_mode(self) -> str:
        """Return current preset mode."""
        return self._preset_mode

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature from the active sensor."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float:
        """Return target temperature."""
        return self._target_temperature

    @property
    def target_temperature_low(self) -> float | None:
        """Return the minimum target temperature in range mode."""
        return self._target_temperature_low

    @property
    def target_temperature_high(self) -> float | None:
        """Return the maximum target temperature in range mode."""
        return self._target_temperature_high

    @property
    def current_humidity(self) -> float | None:
        """Return current indoor humidity."""
        return self._current_humidity

    @property
    def fan_modes(self) -> list[str] | None:
        """Return list of supported fan modes."""
        if self._fan_entity:
            return ["auto", "on"]
        return None

    @property
    def fan_mode(self) -> str | None:
        """Return current fan mode."""
        if not self._fan_entity:
            return None
        return self._user_fan_mode

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode (toggle blower between On and Auto)."""
        if not self._fan_entity or fan_mode not in ("auto", "on"):
            return
        self._user_fan_mode = fan_mode
        if fan_mode == "on":
            self._fan_on_since = dt_util.utcnow()
            self._async_plan_fan_revert()
            _LOGGER.info(
                "[TEST LOG][FAN] Fan set to ON. Will return to Auto: %s (reason: %s).",
                dt_util.as_local(self._fan_on_until).strftime("%Y-%m-%d %I:%M %p") if self._fan_on_until else "never",
                self._fan_revert_reason,
            )
            await self._async_service("fan", "turn_on", {ATTR_ENTITY_ID: self._fan_entity})
        else:
            self._async_clear_fan_revert()
            _LOGGER.info("[TEST LOG][FAN] Fan set to AUTO by user.")
            if self._hvac_action not in (HVACAction.COOLING, HVACAction.HEATING):
                await self._async_service("fan", "turn_off", {ATTR_ENTITY_ID: self._fan_entity})
        self.async_write_ha_state()

    async def _async_service(
        self, domain: str, service: str, data: dict[str, Any], context: Context | None = None
    ) -> None:
        """Call a service, carrying the triggering user's context so the logbook shows who did it."""
        await self.hass.services.async_call(
            domain, service, data, blocking=False, context=context or self._context
        )

    def _next_schedule_slot_after(self, after: datetime) -> datetime | None:
        """Return the first schedule slot start (UTC) strictly after `after`, or None if the schedule can't fire."""
        if not self._enable_schedule or self._preset_mode == PRESET_VACATION:
            return None
        tz = dt_util.get_default_time_zone()
        local_after = dt_util.as_local(after)
        for add_days in range(0, 8):
            day = (local_after + timedelta(days=add_days)).date()
            slots = self._wd_slots if day.weekday() < 5 else self._we_slots
            candidates: list[datetime] = []
            for slot_time, _preset in slots:
                try:
                    hh, mm = (int(x) for x in str(slot_time)[:5].split(":"))
                except ValueError:
                    continue
                start = dt_util.as_utc(datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz))
                if start > after:
                    candidates.append(start)
            if candidates:
                return min(candidates)
        return None

    @callback
    def _async_plan_fan_revert(self) -> None:
        """Work out when Fan On returns to Auto and arm the max-hours cap timer."""
        if self._fan_cap_cancel:
            self._fan_cap_cancel()
            self._fan_cap_cancel = None
        since = self._fan_on_since or dt_util.utcnow()
        slot = self._next_schedule_slot_after(since)
        cap = since + timedelta(hours=self._fan_on_max_hours) if self._fan_on_max_hours > 0 else None
        if slot and (cap is None or slot <= cap):
            self._fan_on_until, self._fan_revert_reason = slot, "schedule"
        elif cap:
            self._fan_on_until, self._fan_revert_reason = cap, "max_hours"
        else:
            self._fan_on_until, self._fan_revert_reason = None, "none"
        if cap and cap > dt_util.utcnow():
            self._fan_cap_cancel = async_track_point_in_utc_time(self.hass, self._async_fan_cap_reached, cap)

    @callback
    def _async_fan_cap_reached(self, _now: datetime) -> None:
        """Max-hours cap for Fan On reached."""
        self._fan_cap_cancel = None
        self.hass.async_create_task(self._async_revert_fan_to_auto("max_hours"))

    @callback
    def _async_clear_fan_revert(self) -> None:
        """Clear all Fan On revert tracking."""
        if self._fan_cap_cancel:
            self._fan_cap_cancel()
            self._fan_cap_cancel = None
        self._fan_on_since = None
        self._fan_on_until = None
        self._fan_revert_reason = "none"

    async def _async_revert_fan_to_auto(self, reason: str) -> None:
        """Return Fan On to Auto (schedule change, Away, or max-hours cap)."""
        if self._user_fan_mode != "on":
            return
        _LOGGER.info("[TEST LOG][FAN] Fan On returned to Auto. Reason: %s.", reason)
        self._user_fan_mode = "auto"
        self._async_clear_fan_revert()
        if self._fan_entity and self._hvac_action not in (HVACAction.COOLING, HVACAction.HEATING):
            await self._async_service("fan", "turn_off", {ATTR_ENTITY_ID: self._fan_entity}, context=Context())
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra diagnostic, schedule, and timer attributes."""
        now = dt_util.utcnow()
        errand_remaining = 0
        if self._errand_timer_end and self._errand_timer_end > now:
            errand_remaining = int((self._errand_timer_end - now).total_seconds() / 60)

        immunity_remaining = 0
        if self._immunity_timer_end and self._immunity_timer_end > now:
            immunity_remaining = int((self._immunity_timer_end - now).total_seconds() / 60)

        delta_t = None
        if self._supply_temperature is not None and self._return_temperature is not None:
            delta_t = round(self._supply_temperature - self._return_temperature, 1)

        fan_curr_state = "n/a"
        if self._fan_entity:
            fst = self.hass.states.get(self._fan_entity)
            if fst:
                fan_curr_state = fst.state

        wall_temp = None
        wall_hum = None
        if self._target_climate:
            wall_st = self.hass.states.get(self._target_climate)
            if wall_st:
                wall_temp = wall_st.attributes.get("current_temperature")
                wall_hum = wall_st.attributes.get("current_humidity")

        return {
            "remote_sensor": self._temp_sensor,
            "active_sensor_source": self._active_sensor_source,
            "last_active_hvac_mode": self._last_active_hvac_mode,
            "last_conditioning_direction": self._last_conditioning_direction,
            "target_climate": self._target_climate,
            "wall_thermostat_temperature": wall_temp,
            "wall_thermostat_humidity": wall_hum,
            "fan_entity": self._fan_entity,
            "fan_state": fan_curr_state,
            "indoor_humidity": self._current_humidity,
            "humidity_sensor": self._humidity_sensor,
            "return_air_temperature": self._return_temperature,
            "return_temp_sensor": self._return_temp_sensor,
            "return_air_humidity": self._return_humidity,
            "return_humidity_sensor": self._return_humidity_sensor,
            "supply_air_temperature": self._supply_temperature,
            "supply_temp_sensor": self._supply_temp_sensor,
            "supply_air_humidity": self._supply_humidity,
            "supply_humidity_sensor": self._supply_humidity_sensor,
            "delta_t": delta_t,
            "target_temp_low": self.target_temperature_low,
            "target_temp_high": self.target_temperature_high,
            "band_type": self._band_type,
            "heat_start_temp": (
                self._hc_thresholds()[2] if self._hvac_mode == HVACMode.HEAT_COOL
                else round(self._target_temperature - self._heating_swing, 1) if self._hvac_mode == HVACMode.HEAT
                else None
            ),
            "cool_start_temp": (
                self._hc_thresholds()[0] if self._hvac_mode == HVACMode.HEAT_COOL
                else round(self._target_temperature + self._cooling_swing, 1) if self._hvac_mode == HVACMode.COOL
                else None
            ),
            "deadband_lower_buffer": self._hc_lower_buffer,
            "deadband_upper_buffer": self._hc_upper_buffer,
            "deadband_buffer_settings": [self._cfg_lower_buffer, self._cfg_upper_buffer],
            "min_deadband_buffer": MIN_HC_BUFFER,
            "min_range_gap": MIN_RANGE_GAP,
            "changeover_delay_minutes": self._changeover_delay,
            "hold_band": self._hold_band,
            "hold_target": self._hold_target,
            "hold_floor": self._hold_floor,
            "hold_ceiling": self._hold_ceiling,
            "schedule_enabled": self._enable_schedule,
            "last_schedule_slot": self._last_scheduled_slot,
            "vacation_mode": self._preset_mode == PRESET_VACATION,
            "errand_grace_active": self._errand_timer_cancel is not None,
            "errand_minutes_remaining": errand_remaining,
            "immunity_active": self._immunity_timer_cancel is not None,
            "immunity_minutes_remaining": immunity_remaining,
            "cooling_swing": self._cooling_swing,
            "heating_swing": self._heating_swing,
            "cooling_offset": self._cooling_offset,
            "heating_offset": self._heating_offset,
            "min_cycle_duration_minutes": self._min_cycle_duration,
            "blower_running": self._user_fan_mode == "on"
            or self._hvac_action in (HVACAction.COOLING, HVACAction.HEATING),
            "fan_on_since": self._fan_on_since.isoformat() if self._fan_on_since else None,
            "fan_on_until": self._fan_on_until.isoformat() if self._fan_on_until else None,
            "fan_revert_reason": self._fan_revert_reason,
            "fan_on_max_hours": self._fan_on_max_hours,
        }

    # --------------------------------------------------------------------------
    # Anchor & Deadzone Band (v1.1.0) setpoint model
    # --------------------------------------------------------------------------

    @staticmethod
    def _safe_buffer(value: Any) -> float:
        """Heat/Cool buffer: 3-10°F."""
        try:
            val = float(value)
        except (TypeError, ValueError):
            val = DEFAULT_HC_LOWER_BUFFER
        return round(max(MIN_HC_BUFFER, min(MAX_HC_BUFFER, val)), 1)

    @staticmethod
    def _safe_range(floor: float, ceiling: float) -> tuple[float, float]:
        """Floor/ceiling inside 60-85°F with at least MIN_RANGE_GAP between them."""
        floor = _clamp(floor, 60.0, 85.0 - MIN_RANGE_GAP)
        ceiling = _clamp(ceiling, 60.0 + MIN_RANGE_GAP, 85.0)
        if ceiling - floor < MIN_RANGE_GAP:
            ceiling = _clamp(floor + MIN_RANGE_GAP)
        return floor, ceiling

    def _boost_heats(self) -> bool:
        """In Heat/Cool, decide which way Boost pushes (last direction, else season/room)."""
        if self._last_conditioning_direction == HVACMode.HEAT:
            return True
        if self._last_conditioning_direction == HVACMode.COOL:
            return False
        if self._current_temperature is not None:
            return self._current_temperature < 70.0
        return dt_util.now().month in (10, 11, 12, 1, 2, 3, 4)

    def _resolve_band(self) -> tuple[str, float | None, float | None, float | None]:
        """Return (band, target, floor, ceiling) for the active preset or manual hold."""
        preset = self._preset_mode
        if preset in self._target_presets:
            return BAND_TARGET, self._target_presets[preset], None, None
        if preset in self._range_presets:
            floor, ceiling = self._range_presets[preset]
            return BAND_RANGE, None, floor, ceiling
        if preset == PRESET_BOOST:
            return "boost", None, self._boost_heat, self._boost_cool
        if self._hold_band == BAND_RANGE:
            return BAND_RANGE, None, self._hold_floor, self._hold_ceiling
        return BAND_TARGET, self._hold_target, None, None

    @callback
    def _apply_setpoints(self) -> None:
        """Recompute target / heat start (low) / cool start (high) from preset, hold and mode."""
        band, target, floor, ceiling = self._resolve_band()
        mode = self._hvac_mode if self._hvac_mode != HVACMode.OFF else self._last_active_hvac_mode
        lower, upper = self._hc_lower_buffer, self._hc_upper_buffer

        if band == "boost":
            if mode == HVACMode.HEAT_COOL:
                # Boost pushes one way only; the other side sits a full deadband away
                if self._boost_heats():
                    floor = self._boost_heat
                    ceiling = self._boost_heat + lower + upper
                else:
                    ceiling = self._boost_cool
                    floor = self._boost_cool - lower - upper
                floor, ceiling = self._safe_range(floor, ceiling)
            band = BAND_RANGE

        self._band_type = band
        if band == BAND_TARGET:
            target = _clamp(target, 60.0 + lower, 85.0 - upper) if mode == HVACMode.HEAT_COOL else _clamp(target)
            self._target_temperature = target
            self._target_temperature_low = _clamp(target - lower)
            self._target_temperature_high = _clamp(target + upper)
        else:
            floor, ceiling = self._safe_range(floor, ceiling)
            self._target_temperature_low = floor
            self._target_temperature_high = ceiling
            if self._preset_mode == PRESET_BOOST and mode == HVACMode.COOL:
                self._target_temperature = _clamp(self._boost_cool)
            elif self._preset_mode == PRESET_BOOST and mode == HVACMode.HEAT:
                self._target_temperature = _clamp(self._boost_heat)
            elif mode == HVACMode.COOL:
                self._target_temperature = ceiling
            elif mode == HVACMode.HEAT:
                self._target_temperature = floor
            else:
                self._target_temperature = round((floor + ceiling) / 2.0 * 2) / 2.0

    def _hc_thresholds(self) -> tuple[float, float, float, float]:
        """Heat/Cool (cool_start, cool_stop, heat_start, heat_stop)."""
        low, high = self._target_temperature_low, self._target_temperature_high
        if self._band_type == BAND_TARGET:
            # Anchor: start at the edge of the deadband, run all the way back to the target
            return high, self._target_temperature, low, self._target_temperature
        # Range: drift freely; behave like Cool at the ceiling and Heat at the floor
        return high + self._cooling_swing, high, low - self._heating_swing, low

    def _setpoint_summary(self) -> str:
        """Human-readable setpoints for notifications, e.g. 'Target: 71.0°F · Deadband: 68°F–74°F'."""
        if self._hvac_mode == HVACMode.HEAT_COOL:
            if self._band_type == BAND_TARGET:
                return (
                    f"Target: {self._target_temperature:.1f}°F · Deadband: "
                    f"{self._target_temperature_low:g}°F–{self._target_temperature_high:g}°F"
                )
            return f"Range: {self._target_temperature_low:g}°F–{self._target_temperature_high:g}°F"
        return f"Target: {self._target_temperature:.1f}°F"

    # --------------------------------------------------------------------------
    # Lifecycle & Listeners
    # --------------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Register listeners and restore previous state after restart."""
        await super().async_added_to_hass()

        # 1. State Restoration (Survives reboots and options saves)
        last_state = await self.async_get_last_state()
        if last_state:
            # Restore HVAC Mode
            if last_state.state in self.hvac_modes:
                self._hvac_mode = HVACMode(last_state.state)
                if last_state.state in (HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL):
                    self._last_active_hvac_mode = HVACMode(last_state.state)

            saved_last_active = last_state.attributes.get("last_active_hvac_mode")
            if saved_last_active in (HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL):
                self._last_active_hvac_mode = HVACMode(saved_last_active)

            saved_dir = last_state.attributes.get("last_conditioning_direction")
            if saved_dir in (HVACMode.COOL, HVACMode.HEAT):
                self._last_conditioning_direction = saved_dir

            saved_fan_mode = last_state.attributes.get("fan_mode")
            if saved_fan_mode in ("on", "auto"):
                self._user_fan_mode = saved_fan_mode
            if self._user_fan_mode == "on":
                saved_since = last_state.attributes.get("fan_on_since")
                parsed_since = dt_util.parse_datetime(saved_since) if isinstance(saved_since, str) else None
                self._fan_on_since = dt_util.as_utc(parsed_since) if parsed_since else dt_util.utcnow()

            # 1. Restore Preset Mode FIRST
            prev_preset = last_state.attributes.get("preset_mode")
            if prev_preset in SUPPORTED_PRESETS or prev_preset == PRESET_NONE:
                self._preset_mode = prev_preset

            attrs = last_state.attributes

            def _valid_temp(raw: Any) -> float | None:
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    return None
                return val if 60.0 <= val <= 85.0 else None

            # 2. Restore live deadband buffers (knob drags), unless the settings changed since
            saved_settings = attrs.get("deadband_buffer_settings")
            if isinstance(saved_settings, (list, tuple)) and len(saved_settings) == 2:
                try:
                    unchanged = (
                        float(saved_settings[0]) == self._cfg_lower_buffer
                        and float(saved_settings[1]) == self._cfg_upper_buffer
                    )
                except (TypeError, ValueError):
                    unchanged = False
                if unchanged:
                    if attrs.get("deadband_lower_buffer") is not None:
                        self._hc_lower_buffer = self._safe_buffer(attrs["deadband_lower_buffer"])
                    if attrs.get("deadband_upper_buffer") is not None:
                        self._hc_upper_buffer = self._safe_buffer(attrs["deadband_upper_buffer"])

            # 3. Restore the manual hold. Preset setpoints are always recomputed from settings.
            if "hold_band" in attrs:
                # Saved by v1.1.0+
                if attrs.get("hold_band") in (BAND_TARGET, BAND_RANGE):
                    self._hold_band = attrs["hold_band"]
                hold_target = _valid_temp(attrs.get("hold_target"))
                if hold_target is not None:
                    self._hold_target = hold_target
                floor = _valid_temp(attrs.get("hold_floor"))
                ceiling = _valid_temp(attrs.get("hold_ceiling"))
                if floor is not None and ceiling is not None:
                    self._hold_floor, self._hold_ceiling = self._safe_range(floor, ceiling)
            elif self._preset_mode == PRESET_NONE:
                # Saved by v1.0.x: low/high were cool/heat setpoints with swing, i.e. a range
                prev_low = _valid_temp(attrs.get("target_temp_low", attrs.get("target_temperature_low")))
                prev_high = _valid_temp(attrs.get("target_temp_high", attrs.get("target_temperature_high")))
                prev_temp = _valid_temp(attrs.get(ATTR_TEMPERATURE))
                if self._hvac_mode == HVACMode.HEAT_COOL and prev_low is not None and prev_high is not None:
                    self._hold_band = BAND_RANGE
                    self._hold_floor, self._hold_ceiling = self._safe_range(prev_low, prev_high)
                elif prev_temp is not None:
                    self._hold_band = BAND_TARGET
                    self._hold_target = prev_temp
                else:
                    _LOGGER.warning(
                        "[CORRUPTED SETPOINT RECOVERED] No valid manual hold found in saved state; falling back to Comfort."
                    )
                    self._preset_mode = PRESET_COMFORT

        self._apply_setpoints()

        _LOGGER.info(
            "[TEST LOG][RESTORE] Active state initialized: Mode=%s, Target=%.1f°F, Preset=%s",
            self._hvac_mode.value.upper(),
            self._target_temperature,
            self._preset_mode.upper(),
        )

        # 2. Inspect physical thermostat's initial state
        phys_state = self.hass.states.get(self._target_climate)
        if phys_state and phys_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._last_sent_physical_mode = phys_state.state
            temp_attr = phys_state.attributes.get(ATTR_TEMPERATURE)
            if temp_attr is not None:
                try:
                    val = float(temp_attr)
                    if 60.0 <= val <= 85.0:
                        self._physical_last_reported_target = val
                        self._last_sent_target_temp = val
                except ValueError:
                    pass

        # 3. Read initial temperature from 3-tier fallback hierarchy
        cur_temp, source = self._get_current_effective_temperature()
        self._current_temperature = cur_temp
        self._active_sensor_source = source

        # 4. Track remote temperature sensor changes
        self._listeners.append(
            async_track_state_change_event(
                self.hass, [self._temp_sensor], self._async_temp_sensor_changed
            )
        )

        # 5. Track physical thermostat changes (two-way sync)
        self._listeners.append(
            async_track_state_change_event(
                self.hass, [self._target_climate], self._async_target_climate_changed
            )
        )

        # 6. Track presence sensor changes (if configured)
        if self._presence_sensor:
            self._listeners.append(
                async_track_state_change_event(
                    self.hass, [self._presence_sensor], self._async_presence_changed
                )
            )

        # 7. Minute-by-minute schedule evaluation
        if self._enable_schedule:
            self._listeners.append(
                async_track_time_change(self.hass, self._async_check_schedule, second=0)
            )

        # 8. Periodic 5-minute safety watchdog & telemetry snapshot
        self._listeners.append(
            async_track_time_interval(
                self.hass, self._async_watchdog_check, timedelta(minutes=5)
            )
        )

        # 9. Track optional sensors (humidity, plenum supply/return probes, and fan)
        self._update_aux_sensors()
        aux_entities = [
            e
            for e in [
                self._humidity_sensor,
                self._supply_temp_sensor,
                self._supply_humidity_sensor,
                self._return_temp_sensor,
                self._return_humidity_sensor,
                self._fan_entity,
            ]
            if e
        ]
        if aux_entities:
            self._listeners.append(
                async_track_state_change_event(
                    self.hass, aux_entities, self._async_aux_sensor_changed
                )
            )

        # 10. Startup hook using HA async_at_started helper (works on both cold boot and live reload)
        async def _async_startup(_: HomeAssistant) -> None:
            # Unit system check: warn if Home Assistant is configured with metric units
            if self.hass.config.units.temperature_unit != UnitOfTemperature.FAHRENHEIT:
                _LOGGER.warning(
                    "[UNIT CONFIG WARNING] Home Assistant temperature unit is '%s'. Dynamic HVAC Control is engineered "
                    "for Fahrenheit (°F) with built-in residential safety bounds (60°F - 85°F) and 65°F freeze protection. "
                    "Ensure Settings -> System -> General -> Unit system is set to US Customary to prevent unintended regulation.",
                    self.hass.config.units.temperature_unit,
                )

            # Preserve Vacation mode and manual holds strictly on reboot!
            if self._preset_mode in (PRESET_VACATION, PRESET_NONE):
                _LOGGER.info("Startup check: Preserving active %s preset across restart.", self._preset_mode)
            elif self._enable_schedule:
                self._async_sync_schedule_to_current_time()

            await self._async_evaluate_regulation()

            # Fan On: re-arm the revert plan, or revert now if its time passed while HA was offline
            if self._fan_entity and self._user_fan_mode == "on":
                self._async_plan_fan_revert()
                if self._fan_on_until and self._fan_on_until <= dt_util.utcnow():
                    await self._async_revert_fan_to_auto(
                        f"{self._fan_revert_reason} time passed while Home Assistant was offline"
                    )
                else:
                    self.async_write_ha_state()

            self._log_telemetry_snapshot("Startup Initialization")
            self._is_starting_up = False

        async_at_started(self.hass, _async_startup)

    async def async_will_remove_from_hass(self) -> None:
        """Cancel all timers and listeners when integration unloads or reloads."""
        for unsub in self._listeners:
            unsub()
        self._listeners.clear()

        if self._errand_timer_cancel:
            self._errand_timer_cancel()
            self._errand_timer_cancel = None

        if self._immunity_timer_cancel:
            self._immunity_timer_cancel()
            self._immunity_timer_cancel = None

        if self._fan_cap_cancel:
            self._fan_cap_cancel()
            self._fan_cap_cancel = None

        await super().async_will_remove_from_hass()

    # --------------------------------------------------------------------------
    # Service Call Handlers & Feature Methods
    # --------------------------------------------------------------------------

    async def async_turn_on(self) -> None:
        """Turn on the climate entity (restores previous active Cool/Heat mode)."""
        await self.async_set_hvac_mode(self._last_active_hvac_mode)

    async def async_turn_off(self) -> None:
        """Turn off the climate entity (standard HA service)."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode not in self.hvac_modes:
            return

        old_mode = self._hvac_mode
        self._hvac_mode = hvac_mode
        if hvac_mode in (HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL):
            self._last_active_hvac_mode = hvac_mode

        if old_mode != hvac_mode:
            _LOGGER.info(
                "[TEST LOG][STATE CHANGE] HVAC Mode changed from %s to %s. Reason: Requested via user interface or service call.",
                str(old_mode).upper(),
                str(hvac_mode).upper(),
            )

        if hvac_mode == HVACMode.OFF:
            if self._hvac_action in (HVACAction.COOLING, HVACAction.HEATING):
                run_sec = int((dt_util.utcnow() - self._last_cycle_start).total_seconds()) if self._last_cycle_start else 0
                _LOGGER.info(
                    "[TEST LOG][HVAC STOP] Stopping %s cycle immediately. Cycle runtime: %dm %ds. Reason: HVAC mode switched to OFF.",
                    str(self._hvac_action).upper(),
                    run_sec // 60,
                    run_sec % 60,
                )
                self._last_cycle_stop = dt_util.utcnow()
            old_action = self._hvac_action
            self._hvac_action = HVACAction.OFF
            if old_action != HVACAction.OFF:
                _LOGGER.info(
                    "[TEST LOG][STATE CHANGE] HVAC Action changed from %s to OFF. Reason: HVAC mode switched to OFF.",
                    str(old_action).upper(),
                )
            await self._async_call_physical_off()
        else:
            self._apply_setpoints()
            await self._async_evaluate_regulation()

        if old_mode != hvac_mode:
            self.hass.async_create_task(
                self._async_send_notification(
                    title="Climate Mode Changed",
                    message=f"{self.name or 'Dynamic HVAC Control'} mode switched from {str(old_mode).upper()} to {str(hvac_mode).upper()}.",
                    notification_type="hvac_mode",
                )
            )

        self.async_write_ha_state()
        self._notify_switch()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target, the Heat/Cool buffers (knob drags), or a manual range.

        * `temperature`           -> manual hold on that target (any mode). In Heat/Cool the
                                     deadband moves with it (target dot drag, -/+, voice).
        * `target_temp_low/high`  -> in Heat/Cool on a target band: change the buffers
                                     (persistent, preset kept). On a range band: manual range hold.
        """
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode and hvac_mode in self._attr_hvac_modes and hvac_mode != self._hvac_mode:
            await self.async_set_hvac_mode(hvac_mode)

        temp = kwargs.get(ATTR_TEMPERATURE)
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        if temp is None and temp_low is None and temp_high is None:
            return

        old_preset = self._preset_mode

        if temp is not None:
            new_temp = _clamp(temp)
            old_temp = self._target_temperature
            self._hold_band = BAND_TARGET
            self._hold_target = new_temp
            self._preset_mode = PRESET_NONE
            _LOGGER.info(
                "[TEST LOG][STATE CHANGE] Target temperature changed from %.1f°F to %.1f°F (Preset '%s' cleared to NONE). Reason: Manual user adjustment via UI or service call.",
                old_temp,
                new_temp,
                old_preset.upper(),
            )

        if (temp_low is not None or temp_high is not None) and self._hvac_mode == HVACMode.HEAT_COOL:
            if self._band_type == BAND_TARGET or temp is not None:
                anchor = self._hold_target if temp is not None else self._target_temperature
                if temp_low is not None:
                    self._hc_lower_buffer = self._safe_buffer(anchor - float(temp_low))
                if temp_high is not None:
                    self._hc_upper_buffer = self._safe_buffer(float(temp_high) - anchor)
                _LOGGER.info(
                    "[TEST LOG][STATE CHANGE] Heat/Cool buffers changed to -%.1f°F / +%.1f°F around %.1f°F (Preset '%s' kept). Reason: Deadband knob adjustment via UI or service call.",
                    self._hc_lower_buffer,
                    self._hc_upper_buffer,
                    anchor,
                    self._preset_mode.upper(),
                )
            else:
                floor = _clamp(temp_low) if temp_low is not None else self._target_temperature_low
                ceiling = _clamp(temp_high) if temp_high is not None else self._target_temperature_high
                if ceiling - floor < MIN_RANGE_GAP:
                    # The knob that moved stops at the gap; it never pushes the other one
                    if temp_low is not None and temp_high is None:
                        floor = ceiling - MIN_RANGE_GAP
                    else:
                        ceiling = floor + MIN_RANGE_GAP
                self._hold_floor, self._hold_ceiling = self._safe_range(floor, ceiling)
                self._hold_band = BAND_RANGE
                self._preset_mode = PRESET_NONE
                _LOGGER.info(
                    "[TEST LOG][STATE CHANGE] Manual range set to heat below %.1f°F / cool above %.1f°F (Preset '%s' cleared to NONE). Reason: Range knob adjustment via UI or service call.",
                    self._hold_floor,
                    self._hold_ceiling,
                    old_preset.upper(),
                )
        elif temp is None:
            # Range-only call outside Heat/Cool: use the side that matches the mode
            side = temp_high if self._hvac_mode == HVACMode.COOL else temp_low
            if side is None:
                side = temp_low if temp_low is not None else temp_high
            self._hold_band = BAND_TARGET
            self._hold_target = _clamp(side)
            self._preset_mode = PRESET_NONE

        self._apply_setpoints()
        await self._async_evaluate_regulation()
        self.async_write_ha_state()
        self._notify_switch()

    async def async_set_preset_mode(
        self,
        preset_mode: str,
        reason: str = "User selection via UI or service call",
        notify: bool = True,
    ) -> None:
        """Set new preset mode."""
        if preset_mode not in SUPPORTED_PRESETS and preset_mode != PRESET_NONE:
            return

        old_preset = self._preset_mode
        self._preset_mode = preset_mode

        # Fan On returns to Auto when the system switches to Away; otherwise re-plan (Vacation suspends the schedule)
        if self._user_fan_mode == "on":
            if preset_mode == PRESET_AWAY and old_preset != PRESET_AWAY:
                await self._async_revert_fan_to_auto("away")
            elif old_preset != preset_mode:
                self._async_plan_fan_revert()

        # If entering Comfort mode, start 60-minute Away Immunity Window (Pre-Cooling)
        if preset_mode == PRESET_COMFORT:
            self._async_start_immunity_window()

        # If entering Vacation mode, cancel any active errand timers
        if preset_mode == PRESET_VACATION:
            if self._errand_timer_cancel:
                self._errand_timer_cancel()
                self._errand_timer_cancel = None
                self._errand_timer_end = None

        # Update setpoints from the preset (target band or range)
        self._apply_setpoints()

        if old_preset != preset_mode:
            _LOGGER.info(
                "[TEST LOG][STATE CHANGE] Preset mode changed from '%s' to '%s'. Target setpoint set to %.1f°F (Range: %.1f°F - %.1f°F). Reason: %s.",
                old_preset.upper(),
                preset_mode.upper(),
                self._target_temperature,
                self._target_temperature_low,
                self._target_temperature_high,
                reason,
            )

        await self._async_evaluate_regulation()

        if old_preset != preset_mode and notify and not self._is_starting_up:
            target_str = f" ({self._setpoint_summary()})"
            self.hass.async_create_task(
                self._async_send_notification(
                    title="Preset Mode Changed",
                    message=f"{self.name or 'Dynamic HVAC Control'} preset set to {preset_mode.capitalize()}{target_str}.",
                    notification_type="preset",
                )
            )

        self.async_write_ha_state()
        self._notify_switch()

    async def async_resume_schedule(self) -> None:
        """Resume normal schedule based on current time (called when Vacation switch turns off)."""
        if self._enable_schedule:
            self._async_sync_schedule_to_current_time()
        else:
            await self.async_set_preset_mode(PRESET_COMFORT, notify=False)

    async def _async_send_notification(self, title: str, message: str, notification_type: str) -> None:
        """Dispatch a notification based on user configuration."""
        if self._is_starting_up:
            return

        enabled = False
        if notification_type == "hvac_mode" and self._notify_hvac_mode:
            enabled = True
        elif notification_type == "preset" and self._notify_preset:
            enabled = True
        elif notification_type == "schedule" and self._notify_schedule:
            enabled = True
        elif notification_type == "presence" and self._notify_presence:
            enabled = True
        elif notification_type == "sensor_fallback" and self._notify_sensor_fallback:
            enabled = True

        if not enabled:
            return

        # Fire HA event for custom automations
        self.hass.bus.async_fire(
            f"{DOMAIN}_notification",
            {
                "type": notification_type,
                "title": title,
                "message": message,
                "entity_id": self.entity_id,
            },
        )

        service = self._notify_service or "notify.persistent_notification"
        if service and "." not in service:
            _LOGGER.warning(
                "Configured notification service '%s' is missing domain prefix. Automatically prefixing with 'notify.'.",
                service,
            )
            service = f"notify.{service}"

        try:
            domain, service_name = service.split(".", 1)
            if domain == "persistent_notification":
                await self._async_service(
                    "persistent_notification",
                    "create",
                    {
                        "title": title,
                        "message": message,
                        "notification_id": f"{DOMAIN}_{notification_type}",
                    }
                )
                return

            if not self.hass.services.has_service(domain, service_name):
                _LOGGER.warning(
                    "Notification target service '%s' is not registered in Home Assistant. Falling back to persistent notifications.",
                    service,
                )
                await self._async_service(
                    "persistent_notification",
                    "create",
                    {
                        "title": title,
                        "message": message,
                        "notification_id": f"{DOMAIN}_{notification_type}",
                    }
                )
                return

            await self._async_service(
                domain,
                service_name,
                {
                    "title": title,
                    "message": message,
                }
            )
        except Exception as err:
            _LOGGER.warning("Failed to dispatch %s notification via %s: %s", notification_type, service, err)

    def _notify_switch(self) -> None:
        """Notify Vacation Mode switch of state changes."""
        switch_entity = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {}).get("switch_entity")
        if switch_entity and switch_entity.hass:
            switch_entity.async_write_ha_state()

    # --------------------------------------------------------------------------
    # 3-Tier Sensor Safety & Fallback Hierarchy
    # --------------------------------------------------------------------------

    def _get_current_effective_temperature(self) -> tuple[float | None, str]:
        """Read room temperature using 3-tier safety hierarchy.
        
        Tier 1: Configured remote sensor (Average House Helper).
        Tier 2: Automatic fallback to physical thermostat built-in sensor.
        Tier 3: Emergency (both sensors offline).
        """
        now = dt_util.utcnow()

        # Tier 1: Primary Remote Sensor Helper
        state = self.hass.states.get(self._temp_sensor)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            # Check for completely dead/frozen sensor (2 hour threshold for steady afternoons)
            report_time = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
            is_stale = False
            if report_time and (now - report_time) > timedelta(minutes=120):
                is_stale = True

            if not is_stale:
                try:
                    val = float(state.state)
                    if self._logged_sensor_fallback:
                        _LOGGER.info(
                            "[TEST LOG][STATE CHANGE] Sensor source changed from 'fallback_physical' to 'remote'. "
                            "Reason: Remote sensor '%s' is back online and reporting valid reading (%.1f°F). Resumed primary Tier 1 tracking.",
                            self._temp_sensor,
                            val,
                        )
                        self._logged_sensor_fallback = False
                        self.hass.async_create_task(
                            self._async_send_notification(
                                title="Sensor Restored",
                                message=f"Remote sensor '{self._temp_sensor}' is back online. Resumed primary temperature tracking.",
                                notification_type="sensor_fallback",
                            )
                        )
                    return val, "remote"
                except (ValueError, TypeError):
                    pass

        # Tier 2: Automatic Fallback to Physical Thermostat Ambient Probe
        phys_state = self.hass.states.get(self._target_climate)
        if phys_state and phys_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            phys_temp = phys_state.attributes.get("current_temperature")
            if phys_temp is not None:
                try:
                    val = float(phys_temp)
                    if not self._logged_sensor_fallback:
                        _LOGGER.warning(
                            "[TEST LOG][STATE CHANGE] Sensor source changed from 'remote' to 'fallback_physical'. "
                            "Reason: Remote sensor '%s' is unavailable or stale (>2h). Auto-failing over to physical thermostat '%s' built-in probe (%.1f°F).",
                            self._temp_sensor,
                            self._target_climate,
                            val,
                        )
                        self._logged_sensor_fallback = True
                        self.hass.async_create_task(
                            self._async_send_notification(
                                title="Sensor Fallback Warning",
                                message=f"Remote sensor '{self._temp_sensor}' is stale or unavailable. Auto-switched to wall unit probe ({val}°F).",
                                notification_type="sensor_fallback",
                            )
                        )
                    return val, "fallback_physical"
                except (ValueError, TypeError):
                    pass

        # Tier 3: Emergency (No valid sensor available)
        return None, "emergency"

    # --------------------------------------------------------------------------
    # Scheduling Engine (4 Mon-Fri Slots, 4 Sat-Sun Slots)
    # --------------------------------------------------------------------------

    def _async_sync_schedule_to_current_time(self) -> None:
        """Determine which schedule slot should be active right now."""
        now = dt_util.now()
        current_time_str = now.strftime("%H:%M")
        weekday = now.weekday()
        active_slots = self._wd_slots if weekday < 5 else self._we_slots
        day_type = "Weekday" if weekday < 5 else "Weekend"

        # Find the latest slot whose time <= current_time
        applicable_slot = None
        slot_number = 1
        for idx, (slot_time, slot_preset) in enumerate(active_slots, start=1):
            if current_time_str >= slot_time[:5]:
                applicable_slot = (slot_time[:5], slot_preset)
                slot_number = idx

        # If before the first slot of the day, wrap to slot 4 of previous day
        if applicable_slot is None:
            # Monday morning (0) -> Sunday night (weekend slot 4)
            # Saturday morning (5) -> Friday night (weekday slot 4)
            # Tuesday-Friday (1-4) -> Weekday slot 4
            # Sunday (6) -> Saturday night (weekend slot 4)
            if weekday == 0 or weekday == 6:
                prev_slots = self._we_slots
                day_type = "Weekend"
            else:
                prev_slots = self._wd_slots
                day_type = "Weekday"

            applicable_slot = (prev_slots[-1][0][:5], prev_slots[-1][1])
            slot_number = len(prev_slots)

        slot_time, slot_preset = applicable_slot
        self._last_scheduled_slot = f"{day_type} Slot {slot_number} ({slot_time})"

        # Presence check:
        # If slot is Away but user is actually Home: don't force Away
        if slot_preset == PRESET_AWAY and self._is_presence_home():
            slot_preset = PRESET_COMFORT

        _LOGGER.info("Synced schedule to current time: %s -> %s", self._last_scheduled_slot, slot_preset)
        self.hass.async_create_task(
            self.async_set_preset_mode(
                slot_preset,
                reason=f"Schedule synced to active slot: {self._last_scheduled_slot}",
                notify=False,
            )
        )

    async def _async_check_schedule(self, now: datetime) -> None:
        """Evaluate schedules every minute."""
        if not self._enable_schedule or self._preset_mode == PRESET_VACATION:
            return

        local_now = dt_util.as_local(now)
        current_time_str = local_now.strftime("%H:%M")
        weekday = local_now.weekday()

        active_slots = self._wd_slots if weekday < 5 else self._we_slots
        day_type = "Weekday" if weekday < 5 else "Weekend"

        for idx, (slot_time, slot_preset) in enumerate(active_slots, start=1):
            if current_time_str == slot_time[:5]:
                slot_name = f"{day_type} Slot {idx} ({slot_time[:5]})"
                if self._last_scheduled_slot != slot_name:
                    _LOGGER.info("Schedule triggered: %s -> setting preset %s", slot_name, slot_preset)
                    self._last_scheduled_slot = slot_name

                    # Fan On returns to Auto at the next scheduled slot (catch-up syncs don't count)
                    if self._user_fan_mode == "on":
                        await self._async_revert_fan_to_auto("schedule")

                    # Presence-Aware: If slot is Away but user is actually Home (e.g. sick day, holiday)
                    if slot_preset == PRESET_AWAY and self._is_presence_home():
                        _LOGGER.info("Schedule called for Away, but presence is Home. Staying in Comfort.")
                        slot_preset = PRESET_COMFORT

                    self.hass.async_create_task(
                        self._async_send_notification(
                            title="Schedule Transition",
                            message=f"{self.name or 'Dynamic HVAC Control'} schedule triggered {slot_name} ({slot_preset.capitalize()}).",
                            notification_type="schedule",
                        )
                    )

                    # Apply preset (If Comfort triggers, it automatically activates Pre-Cooling Immunity)
                    await self.async_set_preset_mode(
                        slot_preset,
                        reason=f"Scheduled slot '{slot_name}' reached",
                        notify=False,
                    )
                break

    # --------------------------------------------------------------------------
    # Core Regulation Engine (Decoupled Offsets & 3-Tier Safety Hand-off)
    # --------------------------------------------------------------------------

    def _get_physical_limits(self) -> tuple[float, float]:
        """Get the physical thermostat's min and max temperature limits."""
        state = self.hass.states.get(self._target_climate)
        min_temp = 60.0
        max_temp = 85.0
        if state:
            if state.attributes.get("min_temp") is not None:
                try:
                    min_temp = float(state.attributes["min_temp"])
                except (ValueError, TypeError):
                    pass
            if state.attributes.get("max_temp") is not None:
                try:
                    max_temp = float(state.attributes["max_temp"])
                except (ValueError, TypeError):
                    pass
        return min_temp, max_temp

    async def _async_evaluate_regulation(self) -> None:
        """Evaluate temperature and control the physical thermostat."""
        # Always read temperature first so UI display and attributes remain active even when OFF!
        cur_temp, source = self._get_current_effective_temperature()
        self._current_temperature = cur_temp
        self._active_sensor_source = source

        if self._hvac_mode == HVACMode.OFF:
            physical_state = self.hass.states.get(self._target_climate)
            cur_mode = physical_state.state if physical_state else None
            if cur_mode != HVACMode.OFF or self._last_sent_physical_mode != HVACMode.OFF:
                await self._async_call_physical_off()
            self.async_write_ha_state()
            return

        # Tier 3 Emergency Failsafe Hand-off: If both remote and physical sensors are offline!
        if cur_temp is None or source == "emergency":
            if not self._logged_emergency_fallback:
                _LOGGER.error(
                    "[TEST LOG][STATE CHANGE] Sensor source changed to 'emergency'. "
                    "Reason: Both remote sensor (%s) and physical thermostat probe (%s) are offline! Engaging Tier 3 failsafe local control at target %.1f°F.",
                    self._temp_sensor,
                    self._target_climate,
                    self._target_temperature,
                )
                self._logged_emergency_fallback = True
                self.hass.async_create_task(
                    self._async_send_notification(
                        title="EMERGENCY: All Sensors Offline",
                        message=f"Both remote sensor and wall thermostat probe are unavailable! Failsafe handoff engaged at {self._target_temperature}°F.",
                        notification_type="sensor_fallback",
                    )
                )
            await self._async_call_physical_safe_handoff(self._target_temperature)
            if self._hvac_action != HVACAction.IDLE:
                _LOGGER.info(
                    "[TEST LOG][STATE CHANGE] HVAC Action changed from %s to IDLE. Reason: Tier 3 emergency failsafe handed control over to physical thermostat.",
                    str(self._hvac_action).upper(),
                )
            self._hvac_action = HVACAction.IDLE
            self.async_write_ha_state()
            return

        self._logged_emergency_fallback = False

        now = dt_util.utcnow()
        min_cycle = timedelta(minutes=self._min_cycle_duration)
        raw_min, raw_max = self._get_physical_limits()
        # Enforce strict residential safety limits (Never command cooling below 62°F or heating above 82°F)
        min_limit = max(62.0, raw_min)
        max_limit = min(82.0, raw_max)

        # --- FREEZE PROTECTION LOCKOUT ---
        # If room temperature drops <= 65.0°F, NEVER run cooling!
        if self._hvac_mode == HVACMode.COOL and self._current_temperature is not None and self._current_temperature <= 65.0:
            if self._hvac_action == HVACAction.COOLING:
                run_sec = int((now - self._last_cycle_start).total_seconds()) if self._last_cycle_start else 0
                _LOGGER.warning(
                    "[TEST LOG][FREEZE GUARD] Room temperature (%.1f°F) is <= 65.0°F! Emergency halting cooling cycle to protect home and HVAC coils.",
                    self._current_temperature,
                )
                self._last_cycle_stop = now
                self._hvac_action = HVACAction.IDLE
            await self._async_call_physical_off()
            self.async_write_ha_state()
            return

        # --- COOLING MODE (True 1-Sided Swing & Safe Cooling Offset) ---
        if self._hvac_mode == HVACMode.COOL:
            # Turn ON when room warms to Target + Swing (e.g. 72 + 2 = 74°F)
            activate_temp = self._target_temperature + self._cooling_swing
            # Turn OFF when room reaches Target Setpoint (72.0°F)
            deactivate_temp = self._target_temperature

            if self._current_temperature >= activate_temp:
                # Need cooling! Check minimum compressor off-time
                if self._last_cycle_stop and (now - self._last_cycle_stop) < min_cycle:
                    remaining = int(min_cycle.total_seconds() - (now - self._last_cycle_stop).total_seconds())
                    _LOGGER.info(
                        "[TEST LOG][CYCLE DELAY] Cooling demand active (Current: %.1f°F >= Activate: %.1f°F), "
                        "but compressor START is delayed: Anti-short-cycle minimum off/dwell time active (%ds remaining of %dm cycle).",
                        self._current_temperature,
                        activate_temp,
                        remaining,
                        self._min_cycle_duration,
                    )
                    return

                physical_cool_target = max(self._target_temperature - self._cooling_offset, min_limit)
                if self._hvac_action != HVACAction.COOLING:
                    self._last_cycle_start = now
                    old_action = self._hvac_action
                    self._hvac_action = HVACAction.COOLING
                    _LOGGER.info(
                        "[TEST LOG][HVAC START] Starting COOLING cycle. Current Temp: %.1f°F, Target: %.1f°F (Activate threshold: %.1f°F), "
                        "Wall Target Setpoint: %.1f°F (Offset: -%.1f°F). Reason: Room temperature (%.1f°F) reached or exceeded cooling activation threshold (%.1f°F).",
                        self._current_temperature,
                        self._target_temperature,
                        activate_temp,
                        physical_cool_target,
                        self._cooling_offset,
                        self._current_temperature,
                        activate_temp,
                    )
                    _LOGGER.info(
                        "[TEST LOG][STATE CHANGE] HVAC Action changed from %s to COOLING. Reason: Room temperature (%.1f°F) >= activation threshold (%.1f°F).",
                        str(old_action).upper(),
                        self._current_temperature,
                        activate_temp,
                    )

                await self._async_call_physical_cooling(physical_cool_target)

            elif self._current_temperature <= deactivate_temp:
                # Target achieved! Check minimum compressor run-time
                if self._last_cycle_start and (now - self._last_cycle_start) < min_cycle:
                    remaining = int(min_cycle.total_seconds() - (now - self._last_cycle_start).total_seconds())
                    _LOGGER.info(
                        "[TEST LOG][CYCLE DELAY] Cooling target satisfied (Current: %.1f°F <= Target: %.1f°F), "
                        "but compressor STOP is delayed: Minimum cycle run-time protection active (%ds remaining of %dm cycle).",
                        self._current_temperature,
                        deactivate_temp,
                        remaining,
                        self._min_cycle_duration,
                    )
                    return

                if self._hvac_action == HVACAction.COOLING:
                    self._last_cycle_stop = now
                    run_sec = int((now - self._last_cycle_start).total_seconds()) if self._last_cycle_start else 0
                    old_action = self._hvac_action
                    self._hvac_action = HVACAction.IDLE
                    _LOGGER.info(
                        "[TEST LOG][HVAC STOP] Stopping COOLING cycle. Cycle runtime: %dm %ds. Current Temp: %.1f°F, Target: %.1f°F. "
                        "Reason: Room temperature (%.1f°F) dropped to or below target setpoint (%.1f°F) - cooling demand satisfied.",
                        run_sec // 60,
                        run_sec % 60,
                        self._current_temperature,
                        self._target_temperature,
                        self._current_temperature,
                        deactivate_temp,
                    )
                    _LOGGER.info(
                        "[TEST LOG][STATE CHANGE] HVAC Action changed from COOLING to IDLE. Reason: Target setpoint reached (cooling satisfied).",
                    )
                await self._async_call_physical_off()

        # --- HEATING MODE (True 1-Sided Swing & Heat Pump Aux Protection) ---
        elif self._hvac_mode == HVACMode.HEAT:
            activate_temp = self._target_temperature - self._heating_swing
            deactivate_temp = self._target_temperature

            if self._current_temperature <= activate_temp:
                if self._last_cycle_stop and (now - self._last_cycle_stop) < min_cycle:
                    remaining = int(min_cycle.total_seconds() - (now - self._last_cycle_stop).total_seconds())
                    _LOGGER.info(
                        "[TEST LOG][CYCLE DELAY] Heating demand active (Current: %.1f°F <= Activate: %.1f°F), "
                        "but furnace/compressor START is delayed: Anti-short-cycle minimum off/dwell time active (%ds remaining of %dm cycle).",
                        self._current_temperature,
                        activate_temp,
                        remaining,
                        self._min_cycle_duration,
                    )
                    return

                physical_heat_target = min(self._target_temperature + self._heating_offset, max_limit)
                if self._hvac_action != HVACAction.HEATING:
                    self._last_cycle_start = now
                    old_action = self._hvac_action
                    self._hvac_action = HVACAction.HEATING
                    _LOGGER.info(
                        "[TEST LOG][HVAC START] Starting HEATING cycle. Current Temp: %.1f°F, Target: %.1f°F (Activate threshold: %.1f°F), "
                        "Wall Target Setpoint: %.1f°F (Offset: +%.1f°F). Reason: Room temperature (%.1f°F) reached or fell below heating activation threshold (%.1f°F).",
                        self._current_temperature,
                        self._target_temperature,
                        activate_temp,
                        physical_heat_target,
                        self._heating_offset,
                        self._current_temperature,
                        activate_temp,
                    )
                    _LOGGER.info(
                        "[TEST LOG][STATE CHANGE] HVAC Action changed from %s to HEATING. Reason: Room temperature (%.1f°F) <= activation threshold (%.1f°F).",
                        str(old_action).upper(),
                        self._current_temperature,
                        activate_temp,
                    )

                await self._async_call_physical_heating(physical_heat_target)

            elif self._current_temperature >= deactivate_temp:
                if self._last_cycle_start and (now - self._last_cycle_start) < min_cycle:
                    remaining = int(min_cycle.total_seconds() - (now - self._last_cycle_start).total_seconds())
                    _LOGGER.info(
                        "[TEST LOG][CYCLE DELAY] Heating target satisfied (Current: %.1f°F >= Target: %.1f°F), "
                        "but furnace/compressor STOP is delayed: Minimum cycle run-time protection active (%ds remaining of %dm cycle).",
                        self._current_temperature,
                        deactivate_temp,
                        remaining,
                        self._min_cycle_duration,
                    )
                    return

                if self._hvac_action == HVACAction.HEATING:
                    self._last_cycle_stop = now
                    run_sec = int((now - self._last_cycle_start).total_seconds()) if self._last_cycle_start else 0
                    old_action = self._hvac_action
                    self._hvac_action = HVACAction.IDLE
                    _LOGGER.info(
                        "[TEST LOG][HVAC STOP] Stopping HEATING cycle. Cycle runtime: %dm %ds. Current Temp: %.1f°F, Target: %.1f°F. "
                        "Reason: Room temperature (%.1f°F) rose to or above target setpoint (%.1f°F) - heating demand satisfied.",
                        run_sec // 60,
                        run_sec % 60,
                        self._current_temperature,
                        self._target_temperature,
                        self._current_temperature,
                        deactivate_temp,
                    )
                    _LOGGER.info(
                        "[TEST LOG][STATE CHANGE] HVAC Action changed from HEATING to IDLE. Reason: Target setpoint reached (heating satisfied).",
                    )
                await self._async_call_physical_off()

        # --- HEAT_COOL MODE (Dual Range Deadband Regulation) ---
        elif self._hvac_mode == HVACMode.HEAT_COOL:
            # Target band: start at target -/+ buffer, stop at the target.
            # Range band: start at floor - heat swing / ceiling + cool swing, stop at floor / ceiling.
            cool_activate, cool_deactivate, heat_activate, heat_deactivate = self._hc_thresholds()
            changeover = timedelta(minutes=max(self._changeover_delay, self._min_cycle_duration))

            if self._current_temperature >= cool_activate:
                if self._current_temperature <= 65.0:
                    if self._hvac_action == HVACAction.COOLING:
                        self._last_cycle_stop = now
                        self._hvac_action = HVACAction.IDLE
                    await self._async_call_physical_off()
                    self.async_write_ha_state()
                    return

                # Reversing valve & compressor protection: Never go straight from HEATING to COOLING
                if self._hvac_action == HVACAction.HEATING:
                    if self._last_cycle_start and (now - self._last_cycle_start) < min_cycle:
                        return
                    self._last_cycle_stop = now
                    run_sec = int((now - self._last_cycle_start).total_seconds()) if self._last_cycle_start else 0
                    self._hvac_action = HVACAction.IDLE
                    _LOGGER.info(
                        "[TEST LOG][HVAC STOP] Stopping HEATING cycle before mode switchover. Runtime: %dm %ds. Entering anti-short-cycle dwell.",
                        run_sec // 60,
                        run_sec % 60,
                    )
                    await self._async_call_physical_off()
                    self.async_write_ha_state()
                    return

                wait = changeover if self._last_conditioning_direction == HVACMode.HEAT else min_cycle
                if self._last_cycle_stop and (now - self._last_cycle_stop) < wait:
                    remaining = int(wait.total_seconds() - (now - self._last_cycle_stop).total_seconds())
                    _LOGGER.info(
                        "[TEST LOG][CYCLE DELAY] Cooling demand active in HEAT_COOL mode, but %s active (%ds remaining).",
                        "heat-to-cool changeover wait" if wait == changeover and wait != min_cycle else "compressor dwell",
                        remaining,
                    )
                    return

                physical_cool_target = max(cool_deactivate - self._cooling_offset, min_limit)
                if self._hvac_action != HVACAction.COOLING:
                    self._last_cycle_start = now
                    old_action = self._hvac_action
                    self._hvac_action = HVACAction.COOLING
                    _LOGGER.info(
                        "[TEST LOG][HVAC START] Starting COOLING cycle in HEAT_COOL mode. Current: %.1f°F >= Activate: %.1f°F, Wall Target: %.1f°F.",
                        self._current_temperature,
                        cool_activate,
                        physical_cool_target,
                    )
                    _LOGGER.info(
                        "[TEST LOG][STATE CHANGE] HVAC Action changed from %s to COOLING. Reason: Room temperature (%.1f°F) >= cooling threshold (%.1f°F).",
                        str(old_action).upper(),
                        self._current_temperature,
                        cool_activate,
                    )
                await self._async_call_physical_cooling(physical_cool_target)

            elif self._current_temperature <= heat_activate:
                # Reversing valve & compressor protection: Never go straight from COOLING to HEATING
                if self._hvac_action == HVACAction.COOLING:
                    if self._last_cycle_start and (now - self._last_cycle_start) < min_cycle:
                        return
                    self._last_cycle_stop = now
                    run_sec = int((now - self._last_cycle_start).total_seconds()) if self._last_cycle_start else 0
                    self._hvac_action = HVACAction.IDLE
                    _LOGGER.info(
                        "[TEST LOG][HVAC STOP] Stopping COOLING cycle before mode switchover. Runtime: %dm %ds. Entering anti-short-cycle dwell.",
                        run_sec // 60,
                        run_sec % 60,
                    )
                    await self._async_call_physical_off()
                    self.async_write_ha_state()
                    return

                wait = changeover if self._last_conditioning_direction == HVACMode.COOL else min_cycle
                if self._last_cycle_stop and (now - self._last_cycle_stop) < wait:
                    remaining = int(wait.total_seconds() - (now - self._last_cycle_stop).total_seconds())
                    _LOGGER.info(
                        "[TEST LOG][CYCLE DELAY] Heating demand active in HEAT_COOL mode, but %s active (%ds remaining).",
                        "cool-to-heat changeover wait" if wait == changeover and wait != min_cycle else "furnace dwell",
                        remaining,
                    )
                    return

                physical_heat_target = min(heat_deactivate + self._heating_offset, max_limit)
                if self._hvac_action != HVACAction.HEATING:
                    self._last_cycle_start = now
                    old_action = self._hvac_action
                    self._hvac_action = HVACAction.HEATING
                    _LOGGER.info(
                        "[TEST LOG][HVAC START] Starting HEATING cycle in HEAT_COOL mode. Current: %.1f°F <= Activate: %.1f°F, Wall Target: %.1f°F.",
                        self._current_temperature,
                        heat_activate,
                        physical_heat_target,
                    )
                    _LOGGER.info(
                        "[TEST LOG][STATE CHANGE] HVAC Action changed from %s to HEATING. Reason: Room temperature (%.1f°F) <= heating threshold (%.1f°F).",
                        str(old_action).upper(),
                        self._current_temperature,
                        heat_activate,
                    )
                await self._async_call_physical_heating(physical_heat_target)

            else:
                # Inside deadband
                if self._hvac_action == HVACAction.COOLING and self._current_temperature <= cool_deactivate:
                    if self._last_cycle_start and (now - self._last_cycle_start) < min_cycle:
                        return
                    self._last_cycle_stop = now
                    run_sec = int((now - self._last_cycle_start).total_seconds()) if self._last_cycle_start else 0
                    self._hvac_action = HVACAction.IDLE
                    _LOGGER.info(
                        "[TEST LOG][HVAC STOP] Stopping COOLING in HEAT_COOL mode. Runtime: %dm %ds. Current: %.1f°F <= Setpoint: %.1f°F.",
                        run_sec // 60,
                        run_sec % 60,
                        self._current_temperature,
                        cool_deactivate,
                    )
                    _LOGGER.info("[TEST LOG][STATE CHANGE] HVAC Action changed from COOLING to IDLE. Reason: Target setpoint reached (cooling satisfied).")
                    await self._async_call_physical_off()
                elif self._hvac_action == HVACAction.HEATING and self._current_temperature >= heat_deactivate:
                    if self._last_cycle_start and (now - self._last_cycle_start) < min_cycle:
                        return
                    self._last_cycle_stop = now
                    run_sec = int((now - self._last_cycle_start).total_seconds()) if self._last_cycle_start else 0
                    self._hvac_action = HVACAction.IDLE
                    _LOGGER.info(
                        "[TEST LOG][HVAC STOP] Stopping HEATING in HEAT_COOL mode. Runtime: %dm %ds. Current: %.1f°F >= Setpoint: %.1f°F.",
                        run_sec // 60,
                        run_sec % 60,
                        self._current_temperature,
                        heat_deactivate,
                    )
                    _LOGGER.info("[TEST LOG][STATE CHANGE] HVAC Action changed from HEATING to IDLE. Reason: Target setpoint reached (heating satisfied).")
                    await self._async_call_physical_off()
                elif self._hvac_action == HVACAction.IDLE:
                    physical_state = self.hass.states.get(self._target_climate)
                    if physical_state and physical_state.state != HVACMode.OFF and self._last_sent_physical_mode != HVACMode.OFF:
                        await self._async_call_physical_off()

        self.async_write_ha_state()

    async def _async_call_physical_cooling(self, target_temp: float) -> None:
        """Command physical thermostat to Cool and set safe temperature."""
        self._last_conditioning_direction = HVACMode.COOL
        safe_target = max(62.0, min(85.0, round(target_temp, 1)))
        self._ignore_physical_target_until = dt_util.utcnow() + timedelta(seconds=15)

        physical_state = self.hass.states.get(self._target_climate)
        cur_mode = physical_state.state if physical_state else None
        cur_temp = None
        if physical_state and physical_state.attributes.get(ATTR_TEMPERATURE) is not None:
            try:
                cur_temp = float(physical_state.attributes[ATTR_TEMPERATURE])
            except (ValueError, TypeError):
                pass

        if cur_mode != HVACMode.COOL or self._last_sent_physical_mode != HVACMode.COOL:
            await self._async_service(
                "climate",
                "set_hvac_mode",
                {ATTR_ENTITY_ID: self._target_climate, "hvac_mode": HVACMode.COOL}
            )
            self._last_sent_physical_mode = HVACMode.COOL
            self._ignore_mode_change_until = dt_util.utcnow() + timedelta(seconds=15)

        if cur_temp is None or abs(cur_temp - safe_target) >= 0.5 or (self._last_sent_target_temp is None or abs(self._last_sent_target_temp - safe_target) >= 0.5):
            await self._async_service(
                "climate",
                "set_temperature",
                {ATTR_ENTITY_ID: self._target_climate, ATTR_TEMPERATURE: safe_target}
            )
            self._last_sent_target_temp = safe_target

    async def _async_call_physical_heating(self, target_temp: float) -> None:
        """Command physical thermostat to Heat and set safe temperature."""
        self._last_conditioning_direction = HVACMode.HEAT
        safe_target = max(60.0, min(82.0, round(target_temp, 1)))
        self._ignore_physical_target_until = dt_util.utcnow() + timedelta(seconds=15)

        physical_state = self.hass.states.get(self._target_climate)
        cur_mode = physical_state.state if physical_state else None
        cur_temp = None
        if physical_state and physical_state.attributes.get(ATTR_TEMPERATURE) is not None:
            try:
                cur_temp = float(physical_state.attributes[ATTR_TEMPERATURE])
            except (ValueError, TypeError):
                pass

        if cur_mode != HVACMode.HEAT or self._last_sent_physical_mode != HVACMode.HEAT:
            await self._async_service(
                "climate",
                "set_hvac_mode",
                {ATTR_ENTITY_ID: self._target_climate, "hvac_mode": HVACMode.HEAT}
            )
            self._last_sent_physical_mode = HVACMode.HEAT
            self._ignore_mode_change_until = dt_util.utcnow() + timedelta(seconds=15)

        if cur_temp is None or abs(cur_temp - safe_target) >= 0.5 or (self._last_sent_target_temp is None or abs(self._last_sent_target_temp - safe_target) >= 0.5):
            await self._async_service(
                "climate",
                "set_temperature",
                {ATTR_ENTITY_ID: self._target_climate, ATTR_TEMPERATURE: safe_target}
            )
            self._last_sent_target_temp = safe_target

    async def _async_call_physical_safe_handoff(self, target_temp: float) -> None:
        """Engage Tier 3 failsafe: Hand over normal setpoint with 0 offset to physical thermostat."""
        if self._hvac_mode in (HVACMode.COOL, HVACMode.HEAT):
            desired_mode = self._hvac_mode
            safe_target = max(60.0, min(85.0, round(target_temp, 1)))
        elif self._hvac_mode == HVACMode.HEAT_COOL:
            # In HEAT_COOL, hand off in last active conditioning direction (HEAT or COOL)
            _c_start, cool_stop, _h_start, heat_stop = self._hc_thresholds()
            if self._last_conditioning_direction == HVACMode.HEAT:
                desired_mode = HVACMode.HEAT
                safe_target = _clamp(heat_stop)
            elif self._last_conditioning_direction == HVACMode.COOL:
                desired_mode = HVACMode.COOL
                safe_target = _clamp(cool_stop)
            else:
                # Direction unknown: check physical wall thermostat's current temperature against midpoint
                midpoint = (self._target_temperature_low + self._target_temperature_high) / 2.0
                phys_state = self.hass.states.get(self._target_climate) if self._target_climate else None
                phys_temp = None
                if phys_state and phys_state.attributes.get("current_temperature") is not None:
                    try:
                        phys_temp = float(phys_state.attributes["current_temperature"])
                    except (ValueError, TypeError):
                        pass

                temp_to_check = self._current_temperature if self._current_temperature is not None else phys_temp

                if temp_to_check is not None:
                    if temp_to_check < midpoint:
                        desired_mode = HVACMode.HEAT
                        safe_target = _clamp(heat_stop)
                    else:
                        desired_mode = HVACMode.COOL
                        safe_target = _clamp(cool_stop)
                else:
                    # Both sensors completely dead and wall temp unknown: default to HEAT during cold months (Oct-Apr)
                    now_month = dt_util.now().month
                    if now_month in (10, 11, 12, 1, 2, 3, 4):
                        desired_mode = HVACMode.HEAT
                        safe_target = _clamp(heat_stop)
                    else:
                        desired_mode = HVACMode.COOL
                        safe_target = _clamp(cool_stop)
        else:
            desired_mode = HVACMode.OFF
            safe_target = max(60.0, min(85.0, round(target_temp, 1)))
        self._ignore_physical_target_until = dt_util.utcnow() + timedelta(seconds=15)

        await self._async_service(
            "climate",
            "set_hvac_mode",
            {ATTR_ENTITY_ID: self._target_climate, "hvac_mode": desired_mode}
        )
        self._last_sent_physical_mode = desired_mode
        self._ignore_mode_change_until = dt_util.utcnow() + timedelta(seconds=15)

        if desired_mode != HVACMode.OFF:
            await self._async_service(
                "climate",
                "set_temperature",
                {ATTR_ENTITY_ID: self._target_climate, ATTR_TEMPERATURE: safe_target}
            )
            self._last_sent_target_temp = safe_target

    async def _async_call_physical_off(self) -> None:
        """Shut off physical thermostat and ensure fan entity is not held in continuous on."""
        self._ignore_physical_target_until = dt_util.utcnow() + timedelta(seconds=15)
        physical_state = self.hass.states.get(self._target_climate)
        cur_mode = physical_state.state if physical_state else None

        if cur_mode != HVACMode.OFF or self._last_sent_physical_mode != HVACMode.OFF:
            await self._async_service(
                "climate",
                "set_hvac_mode",
                {ATTR_ENTITY_ID: self._target_climate, "hvac_mode": HVACMode.OFF}
            )
            self._last_sent_physical_mode = HVACMode.OFF
            self._ignore_mode_change_until = dt_util.utcnow() + timedelta(seconds=15)

        # When idle, only turn off the fan entity if the user hasn't explicitly set fan mode to 'on'
        if self._fan_entity and self._user_fan_mode != "on":
            fan_state = self.hass.states.get(self._fan_entity)
            if fan_state and fan_state.state != "off":
                _LOGGER.info(
                    "[TEST LOG][FAN STOP] Switching circulation fan '%s' from %s to OFF/Auto. Reason: HVAC system is idle or off and fan mode is Auto.",
                    self._fan_entity,
                    fan_state.state,
                )
                await self._async_service(
                    "fan", "turn_off", {ATTR_ENTITY_ID: self._fan_entity}
                )

    # --------------------------------------------------------------------------
    # Watchdog, Diagnostic Telemetry & Event Listeners
    # --------------------------------------------------------------------------

    def _log_telemetry_snapshot(self, trigger_reason: str = "5-Minute Heartbeat") -> None:
        """Log a comprehensive 5-minute diagnostic snapshot of all temperatures, states, and safety timers."""
        now = dt_util.utcnow()

        # Effective & Remote Sensor
        remote_state = self.hass.states.get(self._temp_sensor) if self._temp_sensor else None
        remote_val = f"{remote_state.state}°F" if remote_state and remote_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) else (remote_state.state if remote_state else "n/a")

        # Wall Thermostat
        phys_state = self.hass.states.get(self._target_climate) if self._target_climate else None
        phys_temp = phys_state.attributes.get("current_temperature") if phys_state else None
        phys_temp_str = f"{phys_temp}°F" if phys_temp is not None else "n/a"
        phys_mode = phys_state.state if phys_state else "unknown"
        phys_action = phys_state.attributes.get("hvac_action") if phys_state else "unknown"
        phys_target = phys_state.attributes.get(ATTR_TEMPERATURE) if phys_state else None
        phys_target_str = f"{phys_target}°F" if phys_target is not None else "n/a"

        # Fan
        fan_state_str = "n/a"
        if self._fan_entity:
            fst = self.hass.states.get(self._fan_entity)
            fan_state_str = fst.state if fst else "unknown"

        # Compressor Telemetry
        if self._hvac_action in (HVACAction.COOLING, HVACAction.HEATING):
            run_sec = int((now - self._last_cycle_start).total_seconds()) if self._last_cycle_start else 0
            compressor_status = f"RUNNING ({self._hvac_action.value.upper()}) for {run_sec // 60}m {run_sec % 60}s"
        else:
            if self._last_cycle_stop:
                off_sec = int((now - self._last_cycle_stop).total_seconds())
                min_dwell_sec = int(self._min_cycle_duration * 60)
                dwell_rem = max(0, min_dwell_sec - off_sec)
                compressor_status = f"IDLE / OFF for {off_sec // 60}m {off_sec % 60}s (anti-short-cycle dwell remaining: {dwell_rem}s)"
            else:
                compressor_status = "IDLE / OFF (no prior cycle recorded)"

        # Presence & Timers
        presence_str = "Home" if self._is_presence_home() else "Away"
        if self._errand_timer_end and self._errand_timer_end > now:
            presence_str += f" [Errand Grace: {int((self._errand_timer_end - now).total_seconds() / 60)}m remaining]"
        if self._immunity_timer_end and self._immunity_timer_end > now:
            presence_str += f" [Pre-cooling Immunity: {int((self._immunity_timer_end - now).total_seconds() / 60)}m remaining]"

        # Active offset
        offset_val = 0.0
        if self._hvac_mode == HVACMode.COOL:
            offset_val = -self._cooling_offset
        elif self._hvac_mode == HVACMode.HEAT:
            offset_val = self._heating_offset

        schedule_str = self._last_scheduled_slot if self._enable_schedule else "Disabled"
        cur_temp_str = f"{self._current_temperature:.1f}°F" if self._current_temperature is not None else "OFFLINE"

        # Optional Sensors & Duct Diagnostics
        hum_str = f"{self._current_humidity}%" if self._current_humidity is not None else "n/a"
        ret_temp_str = f"{self._return_temperature}°F" if self._return_temperature is not None else "n/a"
        ret_hum_str = f"{self._return_humidity}%" if self._return_humidity is not None else "n/a"
        sup_temp_str = f"{self._supply_temperature}°F" if self._supply_temperature is not None else "n/a"
        sup_hum_str = f"{self._supply_humidity}%" if self._supply_humidity is not None else "n/a"
        delta_str = f"{round(self._supply_temperature - self._return_temperature, 1)}°F" if (self._supply_temperature is not None and self._return_temperature is not None) else "n/a"

        _LOGGER.info(
            "[TEST LOG][%s]\n"
            "  * Current Temps : Effective=%s (source=%s), Remote Sensor (%s)=%s, Wall Unit (%s)=%s\n"
            "  * Air Probes    : Return=[%s, %s], Supply=[%s, %s], Delta-T=%s, Room Humidity=%s\n"
            "  * Target Targets: Target Setpoint=%.1f°F (Range: %.1f°F - %.1f°F), Dynamic Offset=%.1f°F, Wall Setpoint=%s\n"
            "  * System State  : HVAC Mode=%s, HVAC Action=%s, Preset=%s, Blower Fan=%s\n"
            "  * Hardware State: Wall Mode=%s, Wall Action=%s\n"
            "  * Compressor    : %s (min_cycle=%dm)\n"
            "  * Schedule/Pres : Schedule=%s | Presence=%s",
            trigger_reason.upper(),
            cur_temp_str,
            self._active_sensor_source,
            self._temp_sensor,
            remote_val,
            self._target_climate,
            phys_temp_str,
            ret_temp_str,
            ret_hum_str,
            sup_temp_str,
            sup_hum_str,
            delta_str,
            hum_str,
            self._target_temperature,
            self._target_temperature_low,
            self._target_temperature_high,
            offset_val,
            phys_target_str,
            str(self._hvac_mode).upper(),
            str(self._hvac_action).upper(),
            self._preset_mode.upper(),
            fan_state_str,
            str(phys_mode).upper(),
            str(phys_action).upper(),
            compressor_status,
            self._min_cycle_duration,
            schedule_str,
            presence_str,
        )

    def _read_float_sensor(self, entity_id: str | None) -> float | None:
        """Helper to safely read a float state from an entity ID."""
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        if st and st.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return round(float(st.state), 1)
            except (ValueError, TypeError):
                pass
        return None

    def _update_aux_sensors(self) -> None:
        """Update live readings for optional sensors."""
        self._current_humidity = self._read_float_sensor(self._humidity_sensor)
        self._supply_temperature = self._read_float_sensor(self._supply_temp_sensor)
        self._supply_humidity = self._read_float_sensor(self._supply_humidity_sensor)
        self._return_temperature = self._read_float_sensor(self._return_temp_sensor)
        self._return_humidity = self._read_float_sensor(self._return_humidity_sensor)

    @callback
    def _async_aux_sensor_changed(self, event: Event) -> None:
        """Handle changes in optional sensors or fan entity."""
        self._update_aux_sensors()
        self.async_write_ha_state()

    async def _async_watchdog_check(self, now: datetime) -> None:
        """Periodic 5-minute safety watchdog evaluating sensor health and logging telemetry snapshot."""
        await self._async_evaluate_regulation()
        self._log_telemetry_snapshot("5-Minute Heartbeat")

    async def _async_temp_sensor_changed(self, event: Event) -> None:
        """Handle temperature updates from remote sensor helper."""
        await self._async_evaluate_regulation()

    async def _async_target_climate_changed(self, event: Event) -> None:
        """Two-way sync: Handle physical thermostat dial turns, mode changes, and season switchovers."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if not new_state or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        # 1. Handle Manual OFF Switch at the Wall
        if (
            old_state is not None
            and old_state.state != HVACMode.OFF
            and new_state.state == HVACMode.OFF
            and self._last_sent_physical_mode != HVACMode.OFF
        ):
            _LOGGER.info(
                "[TEST LOG][STATE CHANGE] HVAC Mode changed from %s to OFF. Reason: Physical wall thermostat was manually switched OFF at the wall unit.",
                str(self._hvac_mode).upper(),
            )
            if self._hvac_action in (HVACAction.COOLING, HVACAction.HEATING):
                run_sec = int((dt_util.utcnow() - self._last_cycle_start).total_seconds()) if self._last_cycle_start else 0
                _LOGGER.info(
                    "[TEST LOG][HVAC STOP] Stopping %s cycle immediately. Cycle runtime: %dm %ds. Reason: Wall thermostat manually switched OFF.",
                    str(self._hvac_action).upper(),
                    run_sec // 60,
                    run_sec % 60,
                )
                self._last_cycle_stop = dt_util.utcnow()
            old_action = self._hvac_action
            self._hvac_mode = HVACMode.OFF
            self._hvac_action = HVACAction.OFF
            if old_action != HVACAction.OFF:
                _LOGGER.info(
                    "[TEST LOG][STATE CHANGE] HVAC Action changed from %s to OFF. Reason: Wall thermostat manually switched OFF.",
                    str(old_action).upper(),
                )
            self._last_sent_physical_mode = HVACMode.OFF
            self.hass.async_create_task(
                self._async_send_notification(
                    title="Wall Thermostat Switched Off",
                    message="Thermostat was manually switched OFF at the wall unit.",
                    notification_type="hvac_mode",
                )
            )
            self.async_write_ha_state()
            self._notify_switch()
            return

        # 2. Handle Manual Mode Switch / Season Changeover at the Wall (e.g. user toggles between COOL and HEAT)
        if (
            old_state is not None
            and old_state.state != new_state.state
            and new_state.state in (HVACMode.COOL, HVACMode.HEAT)
            and self._last_sent_physical_mode != new_state.state
        ):
            _LOGGER.info(
                "[TEST LOG][STATE CHANGE] HVAC Mode changed from %s to %s. Reason: Physical wall thermostat was manually switched at the wall unit (Season Changeover).",
                str(self._hvac_mode).upper(),
                str(new_state.state).upper(),
            )
            self._hvac_mode = HVACMode(new_state.state)
            self._last_sent_physical_mode = new_state.state
            self._last_active_hvac_mode = HVACMode(new_state.state)
            self.hass.async_create_task(
                self._async_send_notification(
                    title="Season Changeover at Wall",
                    message=f"Wall thermostat switched to {new_state.state.upper()} mode.",
                    notification_type="hvac_mode",
                )
            )

            # Sync setpoint for the new season/mode from the preset or hold
            self._apply_setpoints()
            self._last_sent_target_temp = self._target_temperature

            temp_attr = new_state.attributes.get(ATTR_TEMPERATURE)
            if temp_attr is not None:
                try:
                    val = float(temp_attr)
                    if 60.0 <= val <= 85.0:
                        self._physical_last_reported_target = val
                except (ValueError, TypeError):
                    pass

            await self._async_evaluate_regulation()
            self.async_write_ha_state()
            self._notify_switch()
            return

        # 3. Handle Dial Target Temperature Adjustments
        # STRICT SAFETY GUARD A: If wall unit is OFF or integration is OFF, NEVER sync temperature adjustments!
        if new_state.state == HVACMode.OFF or self._hvac_mode == HVACMode.OFF:
            return

        now = dt_util.utcnow()
        # STRICT SAFETY GUARD B: Mode change suppression window (reject all dial values during mode transitions)
        if self._ignore_mode_change_until and now < self._ignore_mode_change_until:
            return

        target_temp = new_state.attributes.get(ATTR_TEMPERATURE)
        if target_temp is not None:
            try:
                new_target = float(target_temp)

                # STRICT SAFETY GUARD C: Reject frost-guard or out-of-range temperatures (<60°F or >85°F)
                if new_target < 60.0 or new_target > 85.0:
                    _LOGGER.debug(
                        "Ignoring physical thermostat target %.1f°F outside safe residential range (60-85°F).",
                        new_target,
                    )
                    return

                # STRICT SAFETY GUARD D: Echo suppression window
                # Inside the window, only ignore a reported value within 0.5°F of _last_sent_target_temp (that's our own echo).
                # Any value >= 1.0°F away from both _last_sent_target_temp and _physical_last_reported_target is a real user press.
                if (
                    self._ignore_physical_target_until
                    and now < self._ignore_physical_target_until
                    and self._last_sent_target_temp is not None
                    and abs(new_target - self._last_sent_target_temp) <= 0.5
                ):
                    return

                # Genuine user adjustment check (must differ by at least 1.0°F from sent and reported to reject rounding jitter)
                if (
                    self._physical_last_reported_target is not None
                    and abs(new_target - self._physical_last_reported_target) >= 1.0
                    and (self._last_sent_target_temp is None or abs(new_target - self._last_sent_target_temp) >= 1.0)
                ):
                    baseline = (
                        self._last_sent_target_temp
                        if self._last_sent_target_temp is not None
                        else self._physical_last_reported_target
                    )
                    delta = round(new_target - baseline, 1)

                    if self._hvac_mode == HVACMode.HEAT_COOL:
                        if self._band_type == BAND_TARGET:
                            # Wall dial moves the target; the deadband travels with it
                            new_user_target = _clamp(self._target_temperature + delta)
                            self._hold_band = BAND_TARGET
                            self._hold_target = new_user_target
                            _LOGGER.info(
                                "[TEST LOG][STATE CHANGE] Wall dial adjusted by delta %+0.1f°F (wall dial %.1f°F vs baseline %.1f°F). Target changed from %.1f°F to %.1f°F in HEAT_COOL mode.",
                                delta,
                                new_target,
                                baseline,
                                self._target_temperature,
                                new_user_target,
                            )
                        else:
                            floor, ceiling = self._target_temperature_low, self._target_temperature_high
                            if new_state.state == HVACMode.COOL or self._hvac_action == HVACAction.COOLING:
                                use_ceiling = True
                            elif new_state.state == HVACMode.HEAT or self._hvac_action == HVACAction.HEATING:
                                use_ceiling = False
                            else:
                                use_ceiling = abs(new_target - ceiling) <= abs(new_target - floor)
                            if use_ceiling:
                                ceiling = _clamp(ceiling + delta)
                                floor = min(floor, ceiling - MIN_RANGE_GAP)
                            else:
                                floor = _clamp(floor + delta)
                                ceiling = max(ceiling, floor + MIN_RANGE_GAP)
                            self._hold_band = BAND_RANGE
                            self._hold_floor, self._hold_ceiling = self._safe_range(floor, ceiling)
                            _LOGGER.info(
                                "[TEST LOG][STATE CHANGE] Wall dial adjusted by delta %+0.1f°F (wall dial %.1f°F vs baseline %.1f°F). Range changed to %.1f°F - %.1f°F in HEAT_COOL mode.",
                                delta,
                                new_target,
                                baseline,
                                self._hold_floor,
                                self._hold_ceiling,
                            )
                        self._preset_mode = PRESET_NONE
                        self._apply_setpoints()
                        self._physical_last_reported_target = new_target
                        self._last_sent_target_temp = new_target
                        self._ignore_physical_target_until = now + timedelta(seconds=15)
                        await self._async_evaluate_regulation()
                        self.async_write_ha_state()
                        self._notify_switch()
                    else:
                        new_user_target = _clamp(self._target_temperature + delta)
                        if abs(new_user_target - self._target_temperature) >= 0.5:
                            _LOGGER.info(
                                "[TEST LOG][STATE CHANGE] Wall dial adjusted by delta %+0.1f°F (wall dial %.1f°F vs baseline %.1f°F). Target temperature changed from %.1f°F to %.1f°F (Preset '%s' cleared to NONE).",
                                delta,
                                new_target,
                                baseline,
                                self._target_temperature,
                                new_user_target,
                                self._preset_mode.upper(),
                            )
                            self._hold_band = BAND_TARGET
                            self._hold_target = new_user_target
                            self._preset_mode = PRESET_NONE
                            self._apply_setpoints()
                            self._physical_last_reported_target = new_target
                            self._last_sent_target_temp = new_target
                            self._ignore_physical_target_until = now + timedelta(seconds=15)
                            await self._async_evaluate_regulation()
                            self.async_write_ha_state()
                            self._notify_switch()

                self._physical_last_reported_target = new_target
            except (ValueError, TypeError):
                pass

    def _is_presence_home(self) -> bool:
        """Check if presence entity is home across person, tracker, binary_sensor, or zone."""
        if not self._presence_sensor:
            return True
        st = self.hass.states.get(self._presence_sensor)
        if not st or st.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return True
        # person / device_tracker
        if st.state.lower() in ("home", STATE_HOME):
            return True
        # binary_sensor
        if st.state.lower() in ("on", STATE_ON):
            return True
        # zone (count > 0)
        try:
            return float(st.state) > 0
        except ValueError:
            return False

    async def _async_presence_changed(self, event: Event) -> None:
        """Handle presence transitions (Errand Grace Period & Schedule Return)."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if not new_state or not old_state:
            return

        was_home = old_state.state.lower() in ("home", "on") or (old_state.state.isdigit() and int(old_state.state) > 0)
        is_home = new_state.state.lower() in ("home", "on") or (new_state.state.isdigit() and int(new_state.state) > 0)

        # User left home -> Start 1-Hour Errand Grace Timer
        if was_home and not is_home:
            if self._immunity_timer_cancel is not None:
                _LOGGER.info(
                    "[TEST LOG][PRESENCE] Residents departed, but Away transition ignored. Reason: Pre-cooling immunity window is active."
                )
                return

            _LOGGER.info(
                "[TEST LOG][PRESENCE] Residents departed. Reason: Presence sensor '%s' changed from %s to %s. Starting %d-minute errand grace timer.",
                self._presence_sensor,
                old_state.state,
                new_state.state,
                self._errand_delay,
            )
            self._errand_timer_end = dt_util.utcnow() + timedelta(minutes=self._errand_delay)

            self.hass.async_create_task(
                self._async_send_notification(
                    title="Errand Grace Delay Started",
                    message=f"No presence detected. Holding Comfort for {self._errand_delay} minutes before switching to Away.",
                    notification_type="presence",
                )
            )

            @callback
            def _async_errand_expired(_: datetime) -> None:
                self._errand_timer_cancel = None
                self._errand_timer_end = None
                if not self._is_presence_home():
                    _LOGGER.info(
                        "[TEST LOG][PRESENCE] Errand grace period (%d min) expired with no residents home. Switching to Away preset.",
                        self._errand_delay,
                    )
                    self.hass.async_create_task(
                        self.async_set_preset_mode(
                            PRESET_AWAY,
                            reason=f"Errand grace timer ({self._errand_delay}m) expired without residents returning",
                            notify=False,
                        )
                    )
                    self.hass.async_create_task(
                        self._async_send_notification(
                            title="Away Mode Activated",
                            message="Errand grace delay expired with no presence detected. Switched to Away preset.",
                            notification_type="presence",
                        )
                    )

            self._errand_timer_cancel = async_call_later(
                self.hass, self._errand_delay * 60, _async_errand_expired
            )
            self.async_write_ha_state()

        # User returned home -> Cancel errand timer, restore currently scheduled slot!
        elif not was_home and is_home:
            if self._errand_timer_cancel:
                _LOGGER.info(
                    "[TEST LOG][PRESENCE] Residents returned home before errand grace timer expired. Errand timer canceled."
                )
                self._errand_timer_cancel()
                self._errand_timer_cancel = None
                self._errand_timer_end = None

            if self._preset_mode == PRESET_AWAY:
                _LOGGER.info(
                    "[TEST LOG][PRESENCE] Residents returned home while Away. Reason: Presence sensor '%s' detected arrival (%s). Restoring scheduled preset.",
                    self._presence_sensor,
                    new_state.state,
                )
                self.hass.async_create_task(
                    self._async_send_notification(
                        title="Welcome Home",
                        message="Presence detected. Resumed scheduled Comfort preset.",
                        notification_type="presence",
                    )
                )
                if self._enable_schedule:
                    self._async_sync_schedule_to_current_time()
                else:
                    await self.async_set_preset_mode(
                        PRESET_COMFORT,
                        reason="Resident returned home (Welcome Home trigger)",
                        notify=False,
                    )

            self.async_write_ha_state()

    def _async_start_immunity_window(self) -> None:
        """Start 60-minute Away Immunity Window when entering Comfort mode."""
        if self._immunity_timer_cancel:
            self._immunity_timer_cancel()

        _LOGGER.info(
            "[TEST LOG][PRE-COOLING] Starting %d-minute Away Immunity Window for Pre-Cooling.",
            self._immunity_duration,
        )
        self._immunity_timer_end = dt_util.utcnow() + timedelta(minutes=self._immunity_duration)

        @callback
        def _async_immunity_expired(_: datetime) -> None:
            self._immunity_timer_cancel = None
            self._immunity_timer_end = None
            _LOGGER.info("[TEST LOG][PRE-COOLING] Pre-cooling immunity window (%d min) expired.", self._immunity_duration)
            # If user is still not home when pre-cooling immunity ends, safely revert to Away only if still in Comfort!
            if self._presence_sensor and not self._is_presence_home() and self._preset_mode == PRESET_COMFORT:
                _LOGGER.info(
                    "[TEST LOG][PRE-COOLING] Pre-cooling immunity expired and no residents home. Reverting to Away preset."
                )
                self.hass.async_create_task(
                    self.async_set_preset_mode(
                        PRESET_AWAY,
                        reason=f"Pre-cooling immunity window ({self._immunity_duration}m) expired with no residents home",
                        notify=False,
                    )
                )
                self.hass.async_create_task(
                    self._async_send_notification(
                        title="Pre-Cooling Finished",
                        message="Pre-cooling window finished and no presence detected. Switched to Away preset.",
                        notification_type="presence",
                    )
                )
            self.async_write_ha_state()

        self._immunity_timer_cancel = async_call_later(
            self.hass, self._immunity_duration * 60, _async_immunity_expired
        )
