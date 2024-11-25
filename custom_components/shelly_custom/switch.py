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

    # Get initial state
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://{host}/rpc/Shelly.GetInfo") as response:
                if response.status == 200:
                    data = await response.json()
                    initial_state = False
                    for component in data.get('components', []):
                        if component.get('id') == 1:
                            initial_state = component.get('state', False)
                            break
    except Exception as err:
        _LOGGER.error("Error getting initial state: %s", err)
        initial_state = False

    coordinator = ShellyUpdateCoordinator(
        hass,
        host=host,
        logger=_LOGGER,
        name="Shelly Device",
        update_interval=timedelta(seconds=1),
        initial_state=initial_state,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

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
        initial_state: bool,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
        )
        self.host = host
        self.data = {"state": initial_state}
        self._last_state = initial_state

    async def _async_update_data(self):
        """Fetch data from Shelly device."""
        try:
            async with async_timeout.timeout(5):
                async with aiohttp.ClientSession() as session:
                    url = f"http://{self.host}/rpc/Shelly.GetInfo"
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            current_state = None
                            for component in data.get('components', []):
                                if component.get('id') == 1:
                                    current_state = component.get('state', False)
                                    break

                            if current_state != self._last_state:
                                _LOGGER.debug(
                                    "State changed from %s to %s",
                                    self._last_state,
                                    current_state
                                )
                                self._last_state = current_state

                            return {"state": current_state}
                        raise UpdateFailed(f"Error fetching data: {response.status}")
        except Exception as err:
            _LOGGER.error("Error communicating with device: %s", err)
            raise UpdateFailed(f"Error communicating with device: {err}")

class ShellySwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Shelly switch."""

    def __init__(self, coordinator: ShellyUpdateCoordinator, name: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._name = name
        self._attr_unique_id = f"shelly_custom_{coordinator.host}"
        self._attr_is_on = coordinator.data.get("state", False)

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.coordinator.data.get("state", False)

    @property
    def state(self):
        """Return the state of the switch."""
        if self.coordinator.data.get("state"):
            return STATE_ON
        return STATE_OFF

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._set_state(False)

    async def _set_state(self, state: bool):
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
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            self.coordinator.data = {"state": state}
                            self.async_write_ha_state()
                            await self.coordinator.async_request_refresh()
                        else:
                            _LOGGER.error(
                                "Error setting state: %s", 
                                await response.text()
                            )
        except Exception as err:
            _LOGGER.error("Error setting state: %s", err)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug("Entity added to Home Assistant")
        
        # Force initial state update
        self._handle_coordinator_update()