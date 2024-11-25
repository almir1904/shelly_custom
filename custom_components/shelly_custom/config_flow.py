"""Config flow for Shelly Custom integration."""
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
import aiohttp
import async_timeout

from .const import (
    DOMAIN, 
    ERROR_CANNOT_CONNECT, 
    ERROR_UNKNOWN, 
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL
)

class ShellyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shelly devices."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Test the connection to the device
                async with aiohttp.ClientSession() as session:
                    async with async_timeout.timeout(10):
                        url = f"http://{user_input[CONF_HOST]}/rpc/Shelly.GetInfo"
                        async with session.get(url) as response:
                            if response.status == 200:
                                info = await response.json()
                                # Create unique ID from device MAC address if available
                                unique_id = info.get('mac_address', user_input[CONF_HOST])
                                
                                await self.async_set_unique_id(unique_id)
                                self._abort_if_unique_id_configured()

                                # Add scan_interval to the saved data
                                user_input[CONF_SCAN_INTERVAL] = user_input.get(
                                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                                )

                                return self.async_create_entry(
                                    title=user_input[CONF_NAME],
                                    data=user_input
                                )
                            else:
                                errors["base"] = ERROR_CANNOT_CONNECT
            except aiohttp.ClientError:
                errors["base"] = ERROR_CANNOT_CONNECT
            except Exception:  # pylint: disable=broad-except
                errors["base"] = ERROR_UNKNOWN

        # Show configuration form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_NAME): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
            }),
            errors=errors,
        )