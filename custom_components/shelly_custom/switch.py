"""Switch platform for Shelly Custom integration."""
import logging
from datetime import timedelta
import aiohttp
import async_timeout
import json
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_ON, STATE_OFF
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

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

    coordinator = ShellyUpdateCoordinator(
        hass,
        host=host,
        logger=_LOGGER,
        name="Shelly Device",
        update_interval=timedelta(seconds=1),
    )

    await coordinator.async_refresh()

    async_add_entities([ShellySwitch(coordinator, name)], False)

class ShellyUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Shelly data."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        logger: logging.Logger,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
        )
        self.host = host
        self.data = {"state": False}  # Initialize with a default state
        self._session = aiohttp.ClientSession()

    async def _async_update_data(self):
        """Fetch data from Shelly device."""
        try:
            async with async_timeout.timeout(5):
                url = f"http://{self.host}/rpc/Shelly.GetInfo"
                async with self._session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for component in data.get('components', []):
                            if component.get('id') == 1:
                                new_state = component.get('state', False)
                                _LOGGER.debug("Retrieved state: %s", new_state)
                                return {"state": new_state}
                        return self.data  # Return previous state if no state found
                    return self.data  # Return previous state on non-200 response

        except Exception as err:
            _LOGGER.error("Error communicating with device: %s", err)
            return self.data  # Return previous state on error

class ShellySwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Shelly switch."""

    def __init__(self, coordinator: ShellyUpdateCoordinator, name: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._name = name
        self._attr_unique_id = f"shelly_custom_{coordinator.host}"
        self._state = False
        self._session = aiohttp.ClientSession()

    async def async_will_remove_from_hass(self) -> None:
        """Close sessions when removed."""
        await super().async_will_remove_from_hass()
        await self._session.close()

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if self.coordinator.data:
            self._state = self.coordinator.data.get("state", self._state)
        return self._state

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        if await self._set_state(True):
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        if await self._set_state(False):
            self._state = False
            self.async_write_ha_state()

    async def _set_state(self, state: bool) -> bool:
        """Set the state of the switch."""
        url = f"http://{self.coordinator.host}/rpc/Shelly.SetState"
        state_json = json.dumps({"state": state})
        params = {
            "id": "1",
            "type": "0",
            "state": state_json
        }
        try:
            async with async_timeout.timeout(5):
                async with self._session.get(url, params=params) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        success = response_data.get("was_on") == (not state)  # Check if state changed
                        if success:
                            _LOGGER.debug("State set successfully to %s", state)
                            self.coordinator.data = {"state": state}  # Update coordinator data
                            await self.coordinator.async_request_refresh()
                            return True
                    _LOGGER.error(
                        "Error setting state: %s", 
                        await response.text() if response.status == 200 else response.status
                    )
                    return False
        except Exception as err:
            _LOGGER.error("Error setting state: %s", err)
            return False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            self._state = self.coordinator.data.get("state", self._state)
        self.async_write_ha_state()