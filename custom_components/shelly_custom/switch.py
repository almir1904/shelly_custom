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

    switches = []
    for component in coordinator.data["components"]:
        if component["type"] == 0:  # Switch type
            switches.append(
                ShellySwitch(
                    coordinator,
                    component["name"],
                    entry.entry_id,
                    component["id"]
                )
            )
    
    async_add_entities(switches)

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
        self.device_info = None

    async def _async_update_data(self):
        """Fetch data from Shelly device."""
        async with async_timeout.timeout(10):
            url = f"http://{self.host}/rpc/Shelly.GetInfoExt"
            async with self.session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Store device info
                self.device_info = {
                    "name": data.get("name"),
                    "model": data.get("model"),
                    "sw_version": data.get("version"),
                    "fw_build": data.get("fw_build"),
                    "mac": data.get("mac_address"),
                    "host": data.get("host"),
                }

                return {
                    "components": data.get("components", []),
                    "available": True,
                    "device_info": self.device_info
                }

class ShellySwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Shelly switch."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_has_entity_name = True

    def __init__(
        self, 
        coordinator: ShellyCoordinator,
        name: str,
        entry_id: str,
        component_id: int,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"shelly_custom_{entry_id}_{component_id}"
        self._attr_name = name
        self._component_id = component_id

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {("shelly", self.coordinator.device_info["mac"])},
            "name": self.coordinator.device_info["name"],
            "model": self.coordinator.device_info["model"],
            "manufacturer": "Shelly",
            "sw_version": self.coordinator.device_info["sw_version"],
            "firmware_version": self.coordinator.device_info["fw_build"],
            "suggested_area": self.coordinator.device_info["name"].split("-")[-1] if "-" in self.coordinator.device_info["name"] else None,
        }

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if not self.coordinator.data:
            return False
        for component in self.coordinator.data["components"]:
            if component["id"] == self._component_id:
                return component.get("state", False)
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("available", False) if self.coordinator.data else False

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "firmware_version": self.coordinator.device_info["fw_build"],
            "model": self.coordinator.device_info["model"],
            "host": self.coordinator.device_info["host"],
        }

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
            "id": str(self._component_id),
            "type": "0",
            "state": json.dumps({"state": state})
        }
        async with async_timeout.timeout(10):
            async with self.coordinator.session.get(url, params=params) as response:
                response.raise_for_status()
