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
        self._last_state = None
        self._session = aiohttp.ClientSession()

    async def _async_update_data(self):
        """Fetch data from Shelly device."""
        try:
            async with async_timeout.timeout(5):
                url = f"http://{self.host}/rpc/Shelly.GetInfo"
                async with self._session.get(url) as response:
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
                    _LOGGER.error("Error fetching data: %s", response.status)
                    return self.data

        except Exception as err:
            _LOGGER.error("Error communicating with device: %s", err)
            # Return previous state on error
            return self.data if self.data else {"state": False}

class ShellySwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Shelly switch."""

    def __init__(self, coordinator: ShellyUpdateCoordinator, name: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._name = name
        self._attr_unique_id = f"shelly_custom_{coordinator.host}"
        self._attr_is_on = False
        self._pending_state = None

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self._pending_state is not None:
            return self._pending_state
        return self.coordinator.data.get("state", False) if self.coordinator.data else False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self._pending_state = True
        self.async_write_ha_state()
        success = await self._set_state(True)
        if not success:
            self._pending_state = None
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self._pending_state = False
        self.async_write_ha_state()
        success = await self._set_state(False)
        if not success:
            self._pending_state = None
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
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            response_data = await response.json()
                            if response_data.get("was_on") == state:
                                _LOGGER.debug("State set successfully to %s", state)
                                # Wait briefly for the device to change state
                                await asyncio.sleep(0.5)
                                # Request a refresh to confirm the state
                                await self.coordinator.async_request_refresh()
                                self._pending_state = None
                                return True
                        _LOGGER.error(
                            "Error setting state: %s", 
                            await response.text()
                        )
                        return False
        except Exception as err:
            _LOGGER.error("Error setting state: %s", err)
            return False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug("Entity added to Home Assistant")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._pending_state is not None and self.coordinator.data:
            if self.coordinator.data.get("state") == self._pending_state:
                self._pending_state = None
        super()._handle_coordinator_update()