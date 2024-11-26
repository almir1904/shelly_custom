"""Support for Shelly switch."""
import logging
import aiohttp
import async_timeout
import json
import asyncio
from datetime import timedelta
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=1)
RETRY_DELAY = 5

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Shelly switch."""
    async_add_entities([ShellySwitch(
        hass,
        entry.data[CONF_HOST], 
        entry.data[CONF_NAME], 
        entry.entry_id
    )])

class ShellySwitch(SwitchEntity):
    """Representation of a Shelly switch."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, host: str, name: str, entry_id: str) -> None:
        """Initialize the switch."""
        self.hass = hass
        self._host = host
        self._attr_unique_id = f"shelly_custom_{entry_id}"
        self._attr_name = name
        self._attr_is_on = False
        self._attr_available = True
        self._update_task = None
        self._shutdown = False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get the aiohttp session."""
        return async_get_clientsession(self.hass)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        self._shutdown = False
        self._update_task = asyncio.create_task(self._update_loop())
        _LOGGER.debug("Started state polling for %s", self._attr_name)

    async def _update_loop(self) -> None:
        """Periodically poll the device."""
        retry_count = 0
        while not self._shutdown:
            try:
                await self._update_state()
                retry_count = 0  # Reset retry count on successful update
                await asyncio.sleep(1)
            except Exception as err:
                retry_count += 1
                retry_delay = min(RETRY_DELAY * retry_count, 60)  # Max 60 seconds delay
                _LOGGER.warning(
                    "Error updating %s (attempt %d), retrying in %d seconds: %s",
                    self._attr_name,
                    retry_count,
                    retry_delay,
                    err,
                )
                await asyncio.sleep(retry_delay)

    async def _update_state(self) -> None:
        """Update the state."""
        try:
            session = await self._get_session()
            async with async_timeout.timeout(5):
                url = f"http://{self._host}/rpc/Shelly.GetInfoExt"
                async with session.get(url) as response:
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
                                    self._attr_available = True
                                    self.async_write_ha_state()
                                return
                    raise HomeAssistantError(f"Invalid response from device: {response.status}")
        except TimeoutError:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError("Device timeout")
        except Exception as err:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(f"Error communicating with device: {err}")

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self._shutdown = True
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        await super().async_will_remove_from_hass()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._set_state(False)

    async def _set_state(self, state: bool) -> None:
        """Set the state."""
        session = await self._get_session()
        url = f"http://{self._host}/rpc/Shelly.SetState"
        params = {
            "id": "1",
            "type": "0",
            "state": json.dumps({"state": state})
        }
        try:
            async with async_timeout.timeout(5):
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        # Force immediate state update
                        await self._update_state()
                    else:
                        raise HomeAssistantError(f"Failed to set state: {response.status}")
        except Exception as err:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(f"Error setting state: {err}")
