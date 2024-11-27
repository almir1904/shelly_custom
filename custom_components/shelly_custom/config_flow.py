"""Config flow for Shelly Custom integration."""
import logging
import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class ShellyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shelly Custom."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                device_info = await self._validate_input(user_input)
                await self.async_set_unique_id(device_info["mac_address"])
                self._abort_if_unique_id_configured()

                # Use device name as the default name
                title = device_info.get("name", user_input[CONF_HOST])
                return self.async_create_entry(title=title, data=user_input)

            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", ex)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
            }),
            errors=errors,
        )

    async def _validate_input(self, user_input):
        """Validate the user input allows us to connect."""
        session = async_get_clientsession(self.hass)
        
        async with async_timeout.timeout(10):
            async with session.get(
                f"http://{user_input[CONF_HOST]}/rpc/Shelly.GetInfoExt"
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return {
                    "name": data.get("name"),
                    "mac_address": data.get("mac_address"),
                    "model": data.get("model")
                }
