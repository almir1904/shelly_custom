"""Switch platform for Shelly Custom integration."""
import logging
import aiohttp
import async_timeout
import asyncio
import json
from datetime import timedelta
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Shelly switch from config entry."""
    host = config_entry.data[CONF_HOST]
    name = config_entry.data[CONF_NAME]
    
    async_add_entities([ShellySwitch(hass, name, host, config_entry.entry_id)], True)

class ShellySwitch(SwitchEntity):
    """Representation of a Shelly switch."""

    def __init__(self, hass, name, host, entry_id):
        """Initialize the switch."""
        self._hass = hass
        self._name = name
        self._host = host
        self._entry_id = entry_id
        self._state = None
        self._available = True
        self._attr_unique_id = f"{entry_id}_switch"
        self._polling_task = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self._polling_task = asyncio.create_task(self._polling_loop())

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

    async def _polling_loop(self):
        """Loop to poll device state."""
        while True:
            try:
                new_state = await self._get_state()
                if new_state != self._state:
                    self._state = new_state
                    self.async_write_ha_state()
            except Exception as err:
                _LOGGER.debug("Error in polling loop: %s", err)
            
            await asyncio.sleep(1)  # Poll every second

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
                async with async_timeout.timeout(5):
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            for component in data.get('components', []):
                                if component.get('id') == 1:
                                    self._available = True
                                    return component.get('state', False)
                        return self._state
        except Exception as err:
            self._available = False
            return self._state

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
        except Exception as err:
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