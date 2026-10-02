import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_NOTIFY_PRESET,
    CONF_NOTIFY_SERVICE,
    CONF_VACATION_HEAT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SWITCH]

CARD_DIR = os.path.join(os.path.dirname(__file__), "frontend")
CARD_PATH = os.path.join(CARD_DIR, "dynamic-hvac-control-card.js")
CARD_URL = "/dynamic_hvac_control/dynamic-hvac-control-card.js"


async def _async_register_card(hass: HomeAssistant) -> None:
    """Register custom card static path and frontend resource."""
    if not os.path.exists(CARD_PATH):
        _LOGGER.warning("Bundled card not found at %s", CARD_PATH)
        return

    # 1. Register HTTP static path
    try:
        if hasattr(hass.http, "async_register_static_paths"):
            from homeassistant.components.http import StaticPathConfig
            await hass.http.async_register_static_paths([
                StaticPathConfig(CARD_URL, CARD_PATH, False)
            ])
        elif hasattr(hass.http, "register_static_path"):
            hass.http.register_static_path(CARD_URL, CARD_PATH, False)
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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate entry automatically if needed."""
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
