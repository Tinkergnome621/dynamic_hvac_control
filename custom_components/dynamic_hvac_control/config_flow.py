"""Config flow for Dynamic HVAC Control integration."""
from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_TARGET_CLIMATE,
    CONF_FAN_ENTITY,
    CONF_TEMP_SENSOR,
    CONF_PRESENCE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_SUPPLY_TEMP_SENSOR,
    CONF_SUPPLY_HUMIDITY_SENSOR,
    CONF_RETURN_TEMP_SENSOR,
    CONF_RETURN_HUMIDITY_SENSOR,
    CONF_COOLING_SWING,
    CONF_HEATING_SWING,
    CONF_COOLING_OFFSET,
    CONF_HEATING_OFFSET,
    CONF_ERRAND_DELAY,
    CONF_IMMUNITY_DURATION,
    CONF_MIN_CYCLE_DURATION,
    CONF_COMFORT_COOL,
    CONF_COMFORT_HEAT,
    CONF_ECO_COOL,
    CONF_ECO_HEAT,
    CONF_AWAY_COOL,
    CONF_AWAY_HEAT,
    CONF_SLEEP_COOL,
    CONF_SLEEP_HEAT,
    CONF_BOOST_COOL,
    CONF_BOOST_HEAT,
    CONF_VACATION_COOL,
    CONF_VACATION_HEAT,
    CONF_ENABLE_SCHEDULE,
    CONF_WD_P1_TIME,
    CONF_WD_P1_PRESET,
    CONF_WD_P2_TIME,
    CONF_WD_P2_PRESET,
    CONF_WD_P3_TIME,
    CONF_WD_P3_PRESET,
    CONF_WD_P4_TIME,
    CONF_WD_P4_PRESET,
    CONF_WE_P1_TIME,
    CONF_WE_P1_PRESET,
    CONF_WE_P2_TIME,
    CONF_WE_P2_PRESET,
    CONF_WE_P3_TIME,
    CONF_WE_P3_PRESET,
    CONF_WE_P4_TIME,
    CONF_WE_P4_PRESET,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_HVAC_MODE,
    CONF_NOTIFY_PRESET,
    CONF_NOTIFY_SCHEDULE,
    CONF_NOTIFY_PRESENCE,
    CONF_NOTIFY_SENSOR_FALLBACK,
    DEFAULT_COOLING_SWING,
    DEFAULT_HEATING_SWING,
    DEFAULT_COOLING_OFFSET,
    DEFAULT_HEATING_OFFSET,
    DEFAULT_ERRAND_DELAY,
    DEFAULT_IMMUNITY_DURATION,
    DEFAULT_MIN_CYCLE_DURATION,
    DEFAULT_COMFORT_COOL,
    DEFAULT_COMFORT_HEAT,
    DEFAULT_ECO_COOL,
    DEFAULT_ECO_HEAT,
    DEFAULT_AWAY_COOL,
    DEFAULT_AWAY_HEAT,
    DEFAULT_SLEEP_COOL,
    DEFAULT_SLEEP_HEAT,
    DEFAULT_BOOST_COOL,
    DEFAULT_BOOST_HEAT,
    DEFAULT_VACATION_COOL,
    DEFAULT_VACATION_HEAT,
    DEFAULT_ENABLE_SCHEDULE,
    DEFAULT_WD_P1_TIME,
    DEFAULT_WD_P1_PRESET,
    DEFAULT_WD_P2_TIME,
    DEFAULT_WD_P2_PRESET,
    DEFAULT_WD_P3_TIME,
    DEFAULT_WD_P3_PRESET,
    DEFAULT_WD_P4_TIME,
    DEFAULT_WD_P4_PRESET,
    DEFAULT_WE_P1_TIME,
    DEFAULT_WE_P1_PRESET,
    DEFAULT_WE_P2_TIME,
    DEFAULT_WE_P2_PRESET,
    DEFAULT_WE_P3_TIME,
    DEFAULT_WE_P3_PRESET,
    DEFAULT_WE_P4_TIME,
    DEFAULT_WE_P4_PRESET,
    DEFAULT_NOTIFY_SERVICE,
    DEFAULT_NOTIFY_HVAC_MODE,
    DEFAULT_NOTIFY_PRESET,
    DEFAULT_NOTIFY_SCHEDULE,
    DEFAULT_NOTIFY_PRESENCE,
    DEFAULT_NOTIFY_SENSOR_FALLBACK,
)

PRESET_OPTIONS = [
    selector.SelectOptionDict(value="comfort", label="Comfort"),
    selector.SelectOptionDict(value="eco", label="Eco"),
    selector.SelectOptionDict(value="away", label="Away"),
    selector.SelectOptionDict(value="sleep", label="Sleep"),
    selector.SelectOptionDict(value="boost", label="Boost"),
]


class DynamicHvacControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dynamic HVAC Control."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: Select entities."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_presets()

        schema = vol.Schema(
            {
                vol.Required("name", default="Dynamic HVAC Control"): str,
                vol.Required(CONF_TARGET_CLIMATE): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Required(CONF_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["sensor", "input_number"])
                ),
                vol.Optional(CONF_HUMIDITY_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_FAN_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="fan")
                ),
                vol.Optional(CONF_PRESENCE_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["person", "device_tracker", "binary_sensor", "zone"])
                ),
                vol.Optional(CONF_RETURN_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_RETURN_HUMIDITY_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_SUPPLY_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_SUPPLY_HUMIDITY_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_presets(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 2: Base temperature setpoints, swings, and offsets."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_schedules()

        schema = vol.Schema(
            {
                vol.Required(CONF_COOLING_SWING, default=DEFAULT_COOLING_SWING): vol.Coerce(float),
                vol.Required(CONF_HEATING_SWING, default=DEFAULT_HEATING_SWING): vol.Coerce(float),
                vol.Required(CONF_COOLING_OFFSET, default=DEFAULT_COOLING_OFFSET): vol.Coerce(float),
                vol.Required(CONF_HEATING_OFFSET, default=DEFAULT_HEATING_OFFSET): vol.Coerce(float),
                vol.Required(CONF_MIN_CYCLE_DURATION, default=DEFAULT_MIN_CYCLE_DURATION): vol.Coerce(int),
                vol.Required(CONF_ERRAND_DELAY, default=DEFAULT_ERRAND_DELAY): vol.Coerce(int),
                vol.Required(CONF_IMMUNITY_DURATION, default=DEFAULT_IMMUNITY_DURATION): vol.Coerce(int),
                vol.Required(CONF_COMFORT_COOL, default=DEFAULT_COMFORT_COOL): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_COMFORT_HEAT, default=DEFAULT_COMFORT_HEAT): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_ECO_COOL, default=DEFAULT_ECO_COOL): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_ECO_HEAT, default=DEFAULT_ECO_HEAT): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_AWAY_COOL, default=DEFAULT_AWAY_COOL): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_AWAY_HEAT, default=DEFAULT_AWAY_HEAT): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_SLEEP_COOL, default=DEFAULT_SLEEP_COOL): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_SLEEP_HEAT, default=DEFAULT_SLEEP_HEAT): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_BOOST_COOL, default=DEFAULT_BOOST_COOL): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_BOOST_HEAT, default=DEFAULT_BOOST_HEAT): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_VACATION_COOL, default=DEFAULT_VACATION_COOL): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_VACATION_HEAT, default=DEFAULT_VACATION_HEAT): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
            }
        )

        return self.async_show_form(step_id="presets", data_schema=schema)

    async def async_step_schedules(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 3: Weekday and Weekend 4-Slot Schedules."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_notifications()

        schema = vol.Schema(
            {
                vol.Required(CONF_ENABLE_SCHEDULE, default=DEFAULT_ENABLE_SCHEDULE): bool,
                # Weekday slots (Mon-Fri)
                vol.Required(CONF_WD_P1_TIME, default=DEFAULT_WD_P1_TIME): selector.TimeSelector(),
                vol.Required(CONF_WD_P1_PRESET, default=DEFAULT_WD_P1_PRESET): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WD_P2_TIME, default=DEFAULT_WD_P2_TIME): selector.TimeSelector(),
                vol.Required(CONF_WD_P2_PRESET, default=DEFAULT_WD_P2_PRESET): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WD_P3_TIME, default=DEFAULT_WD_P3_TIME): selector.TimeSelector(),
                vol.Required(CONF_WD_P3_PRESET, default=DEFAULT_WD_P3_PRESET): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WD_P4_TIME, default=DEFAULT_WD_P4_TIME): selector.TimeSelector(),
                vol.Required(CONF_WD_P4_PRESET, default=DEFAULT_WD_P4_PRESET): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                # Weekend slots (Sat-Sun)
                vol.Required(CONF_WE_P1_TIME, default=DEFAULT_WE_P1_TIME): selector.TimeSelector(),
                vol.Required(CONF_WE_P1_PRESET, default=DEFAULT_WE_P1_PRESET): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WE_P2_TIME, default=DEFAULT_WE_P2_TIME): selector.TimeSelector(),
                vol.Required(CONF_WE_P2_PRESET, default=DEFAULT_WE_P2_PRESET): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WE_P3_TIME, default=DEFAULT_WE_P3_TIME): selector.TimeSelector(),
                vol.Required(CONF_WE_P3_PRESET, default=DEFAULT_WE_P3_PRESET): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WE_P4_TIME, default=DEFAULT_WE_P4_TIME): selector.TimeSelector(),
                vol.Required(CONF_WE_P4_PRESET, default=DEFAULT_WE_P4_PRESET): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
            }
        )

        return self.async_show_form(step_id="schedules", data_schema=schema)

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 4: Configure notification triggers and service."""
        if user_input is not None:
            service = str(user_input.get(CONF_NOTIFY_SERVICE, "")).strip()
            if service and "." not in service:
                user_input[CONF_NOTIFY_SERVICE] = f"notify.{service}"
            self._data.update(user_input)
            return self.async_create_entry(
                title=self._data.get("name", "Dynamic HVAC Control"), data=self._data
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NOTIFY_SERVICE, default=DEFAULT_NOTIFY_SERVICE): str,
                vol.Required(CONF_NOTIFY_HVAC_MODE, default=DEFAULT_NOTIFY_HVAC_MODE): bool,
                vol.Required(CONF_NOTIFY_PRESET, default=DEFAULT_NOTIFY_PRESET): bool,
                vol.Required(CONF_NOTIFY_SCHEDULE, default=DEFAULT_NOTIFY_SCHEDULE): bool,
                vol.Required(CONF_NOTIFY_PRESENCE, default=DEFAULT_NOTIFY_PRESENCE): bool,
                vol.Required(CONF_NOTIFY_SENSOR_FALLBACK, default=DEFAULT_NOTIFY_SENSOR_FALLBACK): bool,
            }
        )

        return self.async_show_form(step_id="notifications", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow to modify settings anytime."""
        return DynamicHvacControlOptionsFlow()


class DynamicHvacControlOptionsFlow(config_entries.OptionsFlow):
    """Handle options menu to modify temperatures, schedules, and delays anytime."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self._options: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Menu for options."""
        self._options = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_menu(
            step_id="init",
            menu_options=["temperatures", "sensors", "weekday_schedule", "weekend_schedule", "presence_timers", "notifications"],
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Modify temperature, humidity, fan, and plenum sensors."""
        optional_sensor_fields = [
            (CONF_HUMIDITY_SENSOR, "sensor"),
            (CONF_FAN_ENTITY, "fan"),
            (CONF_PRESENCE_SENSOR, ["person", "device_tracker", "binary_sensor", "zone"]),
            (CONF_RETURN_TEMP_SENSOR, "sensor"),
            (CONF_RETURN_HUMIDITY_SENSOR, "sensor"),
            (CONF_SUPPLY_TEMP_SENSOR, "sensor"),
            (CONF_SUPPLY_HUMIDITY_SENSOR, "sensor"),
        ]

        if user_input is not None:
            # Explicitly remove cleared optional sensors so they don't persist in options
            for conf_key, _ in optional_sensor_fields:
                val = user_input.get(conf_key)
                if not val:
                    self._options.pop(conf_key, None)
                    user_input.pop(conf_key, None)
                else:
                    self._options[conf_key] = val
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        cfg = self._options
        schema_dict: dict[Any, Any] = {
            vol.Required(
                CONF_TEMP_SENSOR,
                default=cfg.get(CONF_TEMP_SENSOR),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "input_number"])
            ),
        }

        for conf_key, domain in optional_sensor_fields:
            val = cfg.get(conf_key)
            if val:
                schema_dict[vol.Optional(conf_key, default=val)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=domain)
                )
            else:
                schema_dict[vol.Optional(conf_key)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=domain)
                )

        return self.async_show_form(step_id="sensors", data_schema=vol.Schema(schema_dict))

    async def async_step_temperatures(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Modify temperature setpoints, swings, and offsets."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        cfg = self._options
        schema = vol.Schema(
            {
                vol.Required(CONF_COOLING_SWING, default=cfg.get(CONF_COOLING_SWING, DEFAULT_COOLING_SWING)): vol.Coerce(float),
                vol.Required(CONF_HEATING_SWING, default=cfg.get(CONF_HEATING_SWING, DEFAULT_HEATING_SWING)): vol.Coerce(float),
                vol.Required(CONF_COOLING_OFFSET, default=cfg.get(CONF_COOLING_OFFSET, DEFAULT_COOLING_OFFSET)): vol.Coerce(float),
                vol.Required(CONF_HEATING_OFFSET, default=cfg.get(CONF_HEATING_OFFSET, DEFAULT_HEATING_OFFSET)): vol.Coerce(float),
                vol.Required(CONF_COMFORT_COOL, default=cfg.get(CONF_COMFORT_COOL, DEFAULT_COMFORT_COOL)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_COMFORT_HEAT, default=cfg.get(CONF_COMFORT_HEAT, DEFAULT_COMFORT_HEAT)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_ECO_COOL, default=cfg.get(CONF_ECO_COOL, DEFAULT_ECO_COOL)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_ECO_HEAT, default=cfg.get(CONF_ECO_HEAT, DEFAULT_ECO_HEAT)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_AWAY_COOL, default=cfg.get(CONF_AWAY_COOL, DEFAULT_AWAY_COOL)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_AWAY_HEAT, default=cfg.get(CONF_AWAY_HEAT, DEFAULT_AWAY_HEAT)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_SLEEP_COOL, default=cfg.get(CONF_SLEEP_COOL, DEFAULT_SLEEP_COOL)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_SLEEP_HEAT, default=cfg.get(CONF_SLEEP_HEAT, DEFAULT_SLEEP_HEAT)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_BOOST_COOL, default=cfg.get(CONF_BOOST_COOL, DEFAULT_BOOST_COOL)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_BOOST_HEAT, default=cfg.get(CONF_BOOST_HEAT, DEFAULT_BOOST_HEAT)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_VACATION_COOL, default=cfg.get(CONF_VACATION_COOL, DEFAULT_VACATION_COOL)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
                vol.Required(CONF_VACATION_HEAT, default=cfg.get(CONF_VACATION_HEAT, DEFAULT_VACATION_HEAT)): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
            }
        )
        return self.async_show_form(step_id="temperatures", data_schema=schema)

    async def async_step_weekday_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Modify Monday – Friday 4-Slot Schedule."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        cfg = self._options
        schema = vol.Schema(
            {
                vol.Required(CONF_ENABLE_SCHEDULE, default=cfg.get(CONF_ENABLE_SCHEDULE, DEFAULT_ENABLE_SCHEDULE)): bool,
                vol.Required(CONF_WD_P1_TIME, default=cfg.get(CONF_WD_P1_TIME, DEFAULT_WD_P1_TIME)): selector.TimeSelector(),
                vol.Required(CONF_WD_P1_PRESET, default=cfg.get(CONF_WD_P1_PRESET, DEFAULT_WD_P1_PRESET)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WD_P2_TIME, default=cfg.get(CONF_WD_P2_TIME, DEFAULT_WD_P2_TIME)): selector.TimeSelector(),
                vol.Required(CONF_WD_P2_PRESET, default=cfg.get(CONF_WD_P2_PRESET, DEFAULT_WD_P2_PRESET)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WD_P3_TIME, default=cfg.get(CONF_WD_P3_TIME, DEFAULT_WD_P3_TIME)): selector.TimeSelector(),
                vol.Required(CONF_WD_P3_PRESET, default=cfg.get(CONF_WD_P3_PRESET, DEFAULT_WD_P3_PRESET)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WD_P4_TIME, default=cfg.get(CONF_WD_P4_TIME, DEFAULT_WD_P4_TIME)): selector.TimeSelector(),
                vol.Required(CONF_WD_P4_PRESET, default=cfg.get(CONF_WD_P4_PRESET, DEFAULT_WD_P4_PRESET)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
            }
        )
        return self.async_show_form(step_id="weekday_schedule", data_schema=schema)

    async def async_step_weekend_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Modify Saturday – Sunday 4-Slot Schedule."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        cfg = self._options
        schema = vol.Schema(
            {
                vol.Required(CONF_WE_P1_TIME, default=cfg.get(CONF_WE_P1_TIME, DEFAULT_WE_P1_TIME)): selector.TimeSelector(),
                vol.Required(CONF_WE_P1_PRESET, default=cfg.get(CONF_WE_P1_PRESET, DEFAULT_WE_P1_PRESET)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WE_P2_TIME, default=cfg.get(CONF_WE_P2_TIME, DEFAULT_WE_P2_TIME)): selector.TimeSelector(),
                vol.Required(CONF_WE_P2_PRESET, default=cfg.get(CONF_WE_P2_PRESET, DEFAULT_WE_P2_PRESET)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WE_P3_TIME, default=cfg.get(CONF_WE_P3_TIME, DEFAULT_WE_P3_TIME)): selector.TimeSelector(),
                vol.Required(CONF_WE_P3_PRESET, default=cfg.get(CONF_WE_P3_PRESET, DEFAULT_WE_P3_PRESET)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
                vol.Required(CONF_WE_P4_TIME, default=cfg.get(CONF_WE_P4_TIME, DEFAULT_WE_P4_TIME)): selector.TimeSelector(),
                vol.Required(CONF_WE_P4_PRESET, default=cfg.get(CONF_WE_P4_PRESET, DEFAULT_WE_P4_PRESET)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=PRESET_OPTIONS)
                ),
            }
        )
        return self.async_show_form(step_id="weekend_schedule", data_schema=schema)

    async def async_step_presence_timers(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Modify Errand Grace Delay, Away Immunity Window, and Compressor Safety."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        cfg = self._options
        schema = vol.Schema(
            {
                vol.Required(CONF_ERRAND_DELAY, default=cfg.get(CONF_ERRAND_DELAY, DEFAULT_ERRAND_DELAY)): vol.Coerce(int),
                vol.Required(CONF_IMMUNITY_DURATION, default=cfg.get(CONF_IMMUNITY_DURATION, DEFAULT_IMMUNITY_DURATION)): vol.Coerce(int),
                vol.Required(CONF_MIN_CYCLE_DURATION, default=cfg.get(CONF_MIN_CYCLE_DURATION, DEFAULT_MIN_CYCLE_DURATION)): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="presence_timers", data_schema=schema)

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Modify notification triggers and service."""
        if user_input is not None:
            service = str(user_input.get(CONF_NOTIFY_SERVICE, "")).strip()
            if service and "." not in service:
                user_input[CONF_NOTIFY_SERVICE] = f"notify.{service}"
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        cfg = self._options
        schema = vol.Schema(
            {
                vol.Required(CONF_NOTIFY_SERVICE, default=cfg.get(CONF_NOTIFY_SERVICE, DEFAULT_NOTIFY_SERVICE)): str,
                vol.Required(CONF_NOTIFY_HVAC_MODE, default=cfg.get(CONF_NOTIFY_HVAC_MODE, DEFAULT_NOTIFY_HVAC_MODE)): bool,
                vol.Required(CONF_NOTIFY_PRESET, default=cfg.get(CONF_NOTIFY_PRESET, DEFAULT_NOTIFY_PRESET)): bool,
                vol.Required(CONF_NOTIFY_SCHEDULE, default=cfg.get(CONF_NOTIFY_SCHEDULE, DEFAULT_NOTIFY_SCHEDULE)): bool,
                vol.Required(CONF_NOTIFY_PRESENCE, default=cfg.get(CONF_NOTIFY_PRESENCE, DEFAULT_NOTIFY_PRESENCE)): bool,
                vol.Required(CONF_NOTIFY_SENSOR_FALLBACK, default=cfg.get(CONF_NOTIFY_SENSOR_FALLBACK, DEFAULT_NOTIFY_SENSOR_FALLBACK)): bool,
            }
        )
        return self.async_show_form(step_id="notifications", data_schema=schema)

