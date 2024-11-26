"""Support for Shelly switch."""
import logging
import aiohttp
import async_timeout
import json
from datetime import timedelta

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Shelly switch."""
    coordinator = ShellyCoordinator(
        hass,
        entry.data[CONF_HOST],
    )
    await coordinator.async_config_entry_first_refresh()
    
    async_add_entities([
        ShellySwitch(
            coordinator,
            entry.data[CONF_NAME],
            entry.entry_id,
        )
    ])

class ShellyCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data updates."""
    
    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Shelly Switch",
            update_interval=SCAN_INTERVAL,
        )
        self.host = host
        self.session = async_get_clientsession(hass)

    async def _async_update_data(self):
        """Fetch data from Shelly device."""
        async with async_timeout.timeout(10):
            url = f"http://{self.host}/rpc/Shelly.GetInfoExt"
            async with self.session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                for component in data.get('components', []):
                    if component.get('id') == 1:
                        return {
                            "state": component.get('state', False),
                            "available": True
                        }
                return {"state": False, "available": False}

class ShellySwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Shelly switch."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_has_entity_name = True

    def __init__(
        self, 
        coordinator: ShellyCoordinator,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"shelly_custom_{entry_id}"
        self._attr_name = name

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.coordinator.data.get("state", False) if self.coordinator.data else False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("available", False) if self.coordinator.data else False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self._set_state(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self._set_state(False)
        await self.coordinator.async_request_refresh()

    async def _set_state(self, state: bool) -> None:
        """Set the state."""
        url = f"http://{self.coordinator.host}/rpc/Shelly.SetState"
        params = {
            "id": "1",
            "type": "0",
            "state": json.dumps({"state": state})
        }
        async with async_timeout.timeout(10):
            async with self.coordinator.session.get(url, params=params) as response:
                response.raise_for_status()
