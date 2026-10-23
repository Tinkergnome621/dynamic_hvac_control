import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_COMFORT_COOL,
    CONF_COMFORT_HEAT,
    CONF_COMFORT_TARGET,
    CONF_SLEEP_COOL,
    CONF_SLEEP_HEAT,
    CONF_SLEEP_TARGET,
    DEFAULT_COMFORT_COOL,
    DEFAULT_COMFORT_HEAT,
    DEFAULT_SLEEP_COOL,
    DEFAULT_SLEEP_HEAT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SWITCH]

CARD_DIR = os.path.join(os.path.dirname(__file__), "frontend")
CARD_PATH = os.path.join(CARD_DIR, "dynamic-hvac-control-card.js")
CARD_URL = "/dynamic_hvac_control/dynamic-hvac-control-card.js"
ICON_PATH = os.path.join(os.path.dirname(__file__), "brand", "icon.png")
ICON_URL = "/dynamic_hvac_control/icon.png"
DATA_CARD_REGISTERED = f"{DOMAIN}_card_registered"


async def _async_register_card(hass: HomeAssistant) -> None:
    """Register custom card static path and frontend resource once per HA start."""
    if hass.data.get(DATA_CARD_REGISTERED):
        return
    hass.data[DATA_CARD_REGISTERED] = True

    if not os.path.exists(CARD_PATH):
        _LOGGER.warning("Bundled card not found at %s", CARD_PATH)
        return

    # 1. Register HTTP static path
    try:
        if hasattr(hass.http, "async_register_static_paths"):
            from homeassistant.components.http import StaticPathConfig
            paths = [StaticPathConfig(CARD_URL, CARD_PATH, False)]
            if os.path.exists(ICON_PATH):
                paths.append(StaticPathConfig(ICON_URL, ICON_PATH, True))
            await hass.http.async_register_static_paths(paths)
        elif hasattr(hass.http, "register_static_path"):
            hass.http.register_static_path(CARD_URL, CARD_PATH, False)
            if os.path.exists(ICON_PATH):
                hass.http.register_static_path(ICON_URL, ICON_PATH, True)
        _LOGGER.info("Registered Dynamic HVAC Control Card static path at %s", CARD_URL)
    except Exception as err:
        _LOGGER.error("Failed to register static path for card: %s", err)

    # 2. Register frontend extra_js_url
    try:
        from homeassistant.components.frontend import add_extra_js_url
        add_extra_js_url(hass, CARD_URL)
        _LOGGER.info("Registered Dynamic HVAC Control Card in Lovelace frontend resources")
    except Exception as err:
        _LOGGER.debug("Could not automatically register frontend resource: %s", err)


def _midpoint_target(cfg: dict, cool_key: str, heat_key: str, default_cool: float, default_heat: float) -> float:
    """Old cool/heat pair -> one target (midpoint, rounded to the nearest 0.5°F, kept within 60-85°F)."""
    try:
        cool = float(cfg.get(cool_key, default_cool))
        heat = float(cfg.get(heat_key, default_heat))
    except (TypeError, ValueError):
        cool, heat = default_cool, default_heat
    return max(60.0, min(85.0, round((cool + heat), 0) / 2.0))


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate older config entries.

    v2 -> v3 (integration v1.1.0, Anchor & Deadzone Band):
      * Comfort and Sleep become single targets: midpoint of their old cool/heat values.
      * Eco, Away and Vacation keep their old values: heat value = floor, cool value = ceiling.
      * Boost keeps separate cool/heat values.
    """
    if config_entry.version > 3:
        return False  # Downgrade from a future version: refuse rather than guess

    if config_entry.version < 3:
        data = {**config_entry.data}
        options = {**config_entry.options}
        merged = {**data, **options}
        new_values = {
            CONF_COMFORT_TARGET: _midpoint_target(
                merged, CONF_COMFORT_COOL, CONF_COMFORT_HEAT, DEFAULT_COMFORT_COOL, DEFAULT_COMFORT_HEAT
            ),
            CONF_SLEEP_TARGET: _midpoint_target(
                merged, CONF_SLEEP_COOL, CONF_SLEEP_HEAT, DEFAULT_SLEEP_COOL, DEFAULT_SLEEP_HEAT
            ),
        }
        data.update(new_values)
        if options:
            options.update(new_values)
        hass.config_entries.async_update_entry(config_entry, data=data, options=options, version=3)
        _LOGGER.info(
            "Migrated Dynamic HVAC Control entry to v3: Comfort target %.1f°F, Sleep target %.1f°F",
            new_values[CONF_COMFORT_TARGET],
            new_values[CONF_SLEEP_TARGET],
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dynamic HVAC Control from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    await _async_register_card(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.entry_id in hass.data.get(DOMAIN, {}):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options are updated in the UI."""
    await hass.config_entries.async_reload(entry.entry_id)
