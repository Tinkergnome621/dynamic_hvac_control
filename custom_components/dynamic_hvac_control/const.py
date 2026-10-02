"""Constants for the Dynamic HVAC Control integration."""

DOMAIN = "dynamic_hvac_control"
DEFAULT_NAME = "Dynamic HVAC Control"

# Configuration Keys - Entities
CONF_TARGET_CLIMATE = "target_climate"
CONF_FAN_ENTITY = "fan_entity"
CONF_TEMP_SENSOR = "temperature_sensor"
CONF_PRESENCE_SENSOR = "presence_sensor"

# Configuration Keys - Optional Sensors & Diagnostics
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_SUPPLY_TEMP_SENSOR = "supply_temp_sensor"
CONF_SUPPLY_HUMIDITY_SENSOR = "supply_humidity_sensor"
CONF_RETURN_TEMP_SENSOR = "return_temp_sensor"
CONF_RETURN_HUMIDITY_SENSOR = "return_humidity_sensor"

# Hysteresis, Timers & Safety
CONF_COOLING_SWING = "cooling_swing"
CONF_HEATING_SWING = "heating_swing"
CONF_COOLING_OFFSET = "cooling_offset"
CONF_HEATING_OFFSET = "heating_offset"
CONF_ERRAND_DELAY = "errand_delay"
CONF_IMMUNITY_DURATION = "immunity_duration"
CONF_MIN_CYCLE_DURATION = "min_cycle_duration"  # Minimum on/off time for compressor

# Setpoint Presets
CONF_COMFORT_COOL = "comfort_cool"
CONF_COMFORT_HEAT = "comfort_heat"
CONF_ECO_COOL = "eco_cool"
CONF_ECO_HEAT = "eco_heat"
CONF_AWAY_COOL = "away_cool"
CONF_AWAY_HEAT = "away_heat"
CONF_SLEEP_COOL = "sleep_cool"
CONF_SLEEP_HEAT = "sleep_heat"
CONF_BOOST_COOL = "boost_cool"
CONF_BOOST_HEAT = "boost_heat"

# Vacation Mode
CONF_VACATION_COOL = "vacation_cool"
CONF_VACATION_HEAT = "vacation_heat"

# Scheduling Configuration
CONF_ENABLE_SCHEDULE = "enable_schedule"

# Weekday Slots (Mon - Fri: 4 periods)
CONF_WD_P1_TIME = "wd_p1_time"
CONF_WD_P1_PRESET = "wd_p1_preset"
CONF_WD_P2_TIME = "wd_p2_time"
CONF_WD_P2_PRESET = "wd_p2_preset"
CONF_WD_P3_TIME = "wd_p3_time"
CONF_WD_P3_PRESET = "wd_p3_preset"
CONF_WD_P4_TIME = "wd_p4_time"
CONF_WD_P4_PRESET = "wd_p4_preset"

# Weekend Slots (Sat - Sun: 4 periods)
CONF_WE_P1_TIME = "we_p1_time"
CONF_WE_P1_PRESET = "we_p1_preset"
CONF_WE_P2_TIME = "we_p2_time"
CONF_WE_P2_PRESET = "we_p2_preset"
CONF_WE_P3_TIME = "we_p3_time"
CONF_WE_P3_PRESET = "we_p3_preset"
CONF_WE_P4_TIME = "we_p4_time"
CONF_WE_P4_PRESET = "we_p4_preset"

# Notification Trigger Configuration
CONF_NOTIFY_SERVICE = "notify_service"
CONF_NOTIFY_HVAC_MODE = "notify_hvac_mode"
CONF_NOTIFY_PRESET = "notify_preset"
CONF_NOTIFY_SCHEDULE = "notify_schedule"
CONF_NOTIFY_PRESENCE = "notify_presence"
CONF_NOTIFY_SENSOR_FALLBACK = "notify_sensor_fallback"

# Defaults - Swings & Delays
DEFAULT_COOLING_SWING = 2.0
DEFAULT_HEATING_SWING = 1.0
DEFAULT_COOLING_OFFSET = 3.0  # Safe offset for cooling (zero aux heat risk)
DEFAULT_HEATING_OFFSET = 1.0  # Safe offset for heat pumps (<3°F prevents aux heat strips)
DEFAULT_ERRAND_DELAY = 60  # minutes
DEFAULT_IMMUNITY_DURATION = 60  # minutes
DEFAULT_MIN_CYCLE_DURATION = 5  # minutes (compressor protection)

# Defaults - Temperatures
DEFAULT_COMFORT_COOL = 72.0
DEFAULT_COMFORT_HEAT = 68.0
DEFAULT_ECO_COOL = 76.0
DEFAULT_ECO_HEAT = 64.0
DEFAULT_AWAY_COOL = 78.0
DEFAULT_AWAY_HEAT = 62.0
DEFAULT_SLEEP_COOL = 69.0
DEFAULT_SLEEP_HEAT = 66.0
DEFAULT_BOOST_COOL = 68.0
DEFAULT_BOOST_HEAT = 72.0
DEFAULT_VACATION_COOL = 82.0
DEFAULT_VACATION_HEAT = 60.0

# Defaults - Schedules
DEFAULT_ENABLE_SCHEDULE = True

# Weekday defaults: Wake (06:30), Work/Away (08:30), Return/Pre-cool (17:00), Night (22:30)
DEFAULT_WD_P1_TIME = "06:30"
DEFAULT_WD_P1_PRESET = "comfort"
DEFAULT_WD_P2_TIME = "08:30"
DEFAULT_WD_P2_PRESET = "away"
DEFAULT_WD_P3_TIME = "17:00"
DEFAULT_WD_P3_PRESET = "comfort"
DEFAULT_WD_P4_TIME = "22:30"
DEFAULT_WD_P4_PRESET = "sleep"

# Weekend defaults: Wake (08:00), Day (11:00), Evening (17:30), Night (23:00)
DEFAULT_WE_P1_TIME = "08:00"
DEFAULT_WE_P1_PRESET = "comfort"
DEFAULT_WE_P2_TIME = "11:00"
DEFAULT_WE_P2_PRESET = "comfort"
DEFAULT_WE_P3_TIME = "17:30"
DEFAULT_WE_P3_PRESET = "comfort"
DEFAULT_WE_P4_TIME = "23:00"
DEFAULT_WE_P4_PRESET = "sleep"

# Defaults - Notification Triggers
DEFAULT_NOTIFY_SERVICE = "notify.persistent_notification"
DEFAULT_NOTIFY_HVAC_MODE = True
DEFAULT_NOTIFY_PRESET = False
DEFAULT_NOTIFY_SCHEDULE = False
DEFAULT_NOTIFY_PRESENCE = True
DEFAULT_NOTIFY_SENSOR_FALLBACK = True
