"""Support for Shelly switch."""
import logging
import aiohttp
import async_timeout
import json
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_ON

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Shelly switch."""
    async_add_entities([
        ShellySwitch(
            entry.data[CONF_HOST],
            entry.data[CONF_NAME],
            entry.entry_id,
        )
    ])

class ShellySwitch(SwitchEntity):
    """Representation of a Shelly switch."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, host: str, name: str, entry_id: str) -> None:
        """Initialize the switch."""
        self._host = host
        self._attr_unique_id = f"shelly_custom_{entry_id}"
        self._attr_name = name
        self._session = aiohttp.ClientSession()
        self._attr_is_on = False
        self._attr_available = True

    async def async_added_to_hass(self) -> None:
        """Run when entity is added."""
        await super().async_added_to_hass()
        await self._update_state()

    async def _update_state(self) -> None:
        """Update the state."""
        try:
            async with async_timeout.timeout(5):
                url = f"http://{self._host}/rpc/Shelly.GetInfo"
                async with self._session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for component in data.get('components', []):
                            if component.get('id') == 1:
                                self._attr_available = True
                                self._attr_is_on = component.get('state', False)
                                break
                    else:
                        self._attr_available = False
        except Exception as err:
            _LOGGER.error("Error updating state: %s", err)
            self._attr_available = False
        
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Close sessions when removed."""
        await self._session.close()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self._set_state(False)

    async def _set_state(self, state: bool) -> None:
        """Set the state."""
        url = f"http://{self._host}/rpc/Shelly.SetState"
        params = {
            "id": "1",
            "type": "0",
            "state": json.dumps({"state": state})
        }
        try:
            async with async_timeout.timeout(5):
                async with self._session.get(url, params=params) as response:
                    if response.status == 200:
                        await self._update_state()
        except Exception as err:
            _LOGGER.error("Error setting state: %s", err)
            self._attr_available = False
            self.async_write_ha_state()
