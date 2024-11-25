"""The Shelly Custom integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import asyncio

from .const import DOMAIN

PLATFORMS = ["switch"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelly Custom from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Use asyncio.gather to properly await all platform setups
    await asyncio.gather(
        *[
            hass.config_entries.async_forward_entry_setup(entry, platform)
            for platform in PLATFORMS
        ]
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok