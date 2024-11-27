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
from homeassistant.const import CONF_HOST
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Shelly switch."""
    host = entry.data[CONF_HOST]
    _LOGGER.debug("Setting up Shelly switch with host: %s", host)
    
    try:
        # Get initial device info
        session = async_get_clientsession(hass)
        async with session.get(f"http://{host}/rpc/Shelly.GetInfoExt") as response:
            response.raise_for_status()
            data = await response.json()
            _LOGGER.debug("Device info: %s", data)
            
            coordinator = ShellyCoordinator(hass, host)
            await coordinator.async_config_entry_first_refresh()

            devices = []
            for component in data.get("components", []):
                if component.get("type") == 0:  # Switch type
                    _LOGGER.debug("Adding switch component: %s", component)
                    devices.append(
                        ShellySwitch(
                            coordinator,
                            component.get("name", "Unknown"),
                            entry.entry_id,
                            component["id"],
                            data.get("name", "Unknown Device")
                        )
                    )

            async_add_entities(devices)
            _LOGGER.debug("Added %d switches", len(devices))
    except Exception as ex:
        _LOGGER.error("Error setting up Shelly switch: %s", ex)

class ShellyCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data updates."""
    
    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Shelly Switch",
            update_interval=timedelta(seconds=30),
        )
        self.host = host
        self.session = async_get_clientsession(hass)

    async def _async_update_data(self):
        """Fetch data from Shelly device."""
        try:
            async with async_timeout.timeout(10):
                async with self.session.get(f"http://{self.host}/rpc/Shelly.GetInfoExt") as response:
                    response.raise_for_status()
                    data = await response.json()
                    _LOGGER.debug("Updated data from device: %s", data)
                    return data
        except Exception as err:
            _LOGGER.error("Error getting data from device: %s", err)
            raise

class ShellySwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Shelly switch."""

    _attr_has_entity_name = True

    def __init__(
        self, 
        coordinator: ShellyCoordinator,
        name: str,
        entry_id: str,
        component_id: int,
        device_name: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{component_id}"
        self._attr_name = name
        self._component_id = component_id
        self._device_name = device_name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}")},
            "name": device_name,
            "manufacturer": "Shelly",
        }

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if not self.coordinator.data:
            return False
        for component in self.coordinator.data.get("components", []):
            if component.get("id") == self._component_id:
                return component.get("state", False)
        return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self._set_state(False)

    async def _set_state(self, state: bool) -> None:
        """Set the state."""
        try:
            url = f"http://{self.coordinator.host}/rpc/Shelly.SetState"
            params = {
                "id": str(self._component_id),
                "type": "0",
                "state": json.dumps({"state": state})
            }
            session = async_get_clientsession(self.coordinator.hass)
            async with session.get(url, params=params) as response:
                response.raise_for_status()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error setting state: %s", err)
