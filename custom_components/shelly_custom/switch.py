"""Switch platform for Shelly Custom integration."""
import logging
import aiohttp
import async_timeout
import asyncio
import json
from datetime import timedelta
from typing import Any
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, CONF_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Shelly switch from config entry."""
    host = config_entry.data[CONF_HOST]
    name = config_entry.data[CONF_NAME]
    scan_interval = config_entry.data.get(CONF_SCAN_INTERVAL, 1)
    
    async_add_entities([ShellySwitch(hass, name, host, config_entry.entry_id, scan_interval)], True)

class ShellySwitch(SwitchEntity):
    """Representation of a Shelly switch."""

    def __init__(self, hass, name, host, entry_id, scan_interval):
        """Initialize the switch."""
        self._hass = hass
        self._name = name
        self._host = host
        self._entry_id = entry_id
        self._state = None
        self._available = True
        self._attr_unique_id = f"{entry_id}_switch"
        self._scan_interval = scan_interval
        self._remove_tracker = None
        self._is_updating = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Add regular polling
        self._remove_tracker = async_track_time_interval(
            self._hass,
            self._async_update_state,
            timedelta(seconds=self._scan_interval)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._remove_tracker:
            self._remove_tracker()
        
        await super().async_will_remove_from_hass()

    @callback
    async def _async_update_state(self, *_: Any) -> None:
        """Update the entity state."""
        if self._is_updating:
            return
        
        self._is_updating = True
        try:
            state = await self._get_state()
            if state != self._state:
                self._state = state
                self.async_write_ha_state()
        finally:
            self._is_updating = False

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    async def _get_state(self):
        """Get the current state from the Shelly device."""
        url = f"http://{self._host}/rpc/Shelly.GetInfo"
        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(5):  # Reduced timeout for polling
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            for component in data.get('components', []):
                                if component.get('id') == 1:
                                    self._available = True
                                    return component.get('state', False)
                        return self._state  # Keep previous state on error
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Error getting state: %s", err)  # Changed to debug level
            self._available = False
            return self._state  # Keep previous state on error

    async def _set_state(self, state: bool):
        """Set the state of the switch."""
        url = f"http://{self._host}/rpc/Shelly.SetState"
        state_json = json.dumps({"state": state})
        params = {
            "id": "1",
            "type": "0",
            "state": state_json
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            self._state = state
                            self._available = True
                            self.async_write_ha_state()
                            return True
                        else:
                            _LOGGER.error("Error setting state: %s", await response.text())
                            return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error setting state: %s", err)
            self._available = False
            return False

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._set_state(False)

    async def async_update(self):
        """Fetch new state data for this switch."""
        self._state = await self._get_state()