"""Switch platform for Dynamic HVAC Control (Vacation Mode toggle)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Vacation Mode switch entity."""
    entity = DynamicHvacVacationSwitch(hass, entry)
    # Store switch reference in hass.data for direct two-way synchronization
    hass.data[DOMAIN][entry.entry_id]["switch_entity"] = entity
    async_add_entities([entity])


class DynamicHvacVacationSwitch(SwitchEntity):
    """Switch entity to toggle Vacation Mode on/off."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:airplane"
    _attr_name = "Vacation Mode"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_vacation_mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Dynamic HVAC Control"),
            manufacturer="Dynamic HVAC Control",
            model="Central A/C & Heat Pump Controller",
        )

    @property
    def should_poll(self) -> bool:
        """Return False as this switch is event-driven."""
        return False

    @property
    def is_on(self) -> bool:
        """Return True if Vacation Mode is active on the climate entity."""
        climate_entity = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {}).get("climate_entity")
        if climate_entity:
            return climate_entity.preset_mode == "vacation"
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Vacation Mode."""
        climate_entity = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {}).get("climate_entity")
        if climate_entity:
            await climate_entity.async_set_preset_mode("vacation", reason="Vacation Mode switch turned ON")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Vacation Mode and resume normal scheduled preset."""
        climate_entity = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {}).get("climate_entity")
        if climate_entity:
            _LOGGER.info("[TEST LOG][STATE CHANGE] Vacation Mode switch turned OFF. Resuming normal schedule.")
            await climate_entity.async_resume_schedule()
        self.async_write_ha_state()

