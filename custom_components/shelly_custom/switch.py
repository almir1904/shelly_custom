"""Support for Shelly switch."""
import logging
import aiohttp
import async_timeout
import json
import asyncio
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_HOST, CONF_NAME

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Shelly switch."""
    async_add_entities([ShellySwitch(entry.data[CONF_HOST], entry.data[CONF_NAME], entry.entry_id)])

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
        self._update_task = None

    async def async_added_to_hass(self) -> None:
        """Run when entity is added."""
        await super().async_added_to_hass()
        self._update_task = asyncio.create_task(self._update_loop())
        _LOGGER.debug("Started state polling for %s", self._attr_name)

    async def _update_loop(self) -> None:
        """Periodically poll the device."""
        while True:
            await self._update_state()
            await asyncio.sleep(1)

    async def _update_state(self) -> None:
        """Update the state."""
        try:
            async with async_timeout.timeout(5):
                url = f"http://{self._host}/rpc/Shelly.GetInfoExt"
                async with self._session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for component in data.get('components', []):
                            if component.get('id') == 1:
                                new_state = component.get('state', False)
                                if new_state != self._attr_is_on:
                                    _LOGGER.debug(
                                        "%s: State changed from %s to %s",
                                        self._attr_name,
                                        self._attr_is_on,
                                        new_state
                                    )
                                    self._attr_is_on = new_state
                                    self.async_write_ha_state()
                                break
                        self._attr_available = True
                    else:
                        self._attr_available = False
                        self.async_write_ha_state()
        except Exception as err:
            _LOGGER.debug("Error updating state for %s: %s", self._attr_name, err)
            self._attr_available = False
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Close sessions when removed."""
        if self._update_task:
            self._update_task.cancel()
        await self._session.close()
        await super().async_will_remove_from_hass()

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
            _LOGGER.error("Error setting state for %s: %s", self._attr_name, err)
            self._attr_available = False
            self.async_write_ha_state()
