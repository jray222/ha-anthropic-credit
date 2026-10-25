"""Anthropic Credit: estimate what is left on your Anthropic API credit."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AnthropicCostClient
from .const import CONF_ADMIN_KEY
from .coordinator import AnthropicCreditCoordinator

PLATFORMS = [Platform.SENSOR]

type AnthropicCreditConfigEntry = ConfigEntry[AnthropicCreditCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AnthropicCreditConfigEntry) -> bool:
    client = AnthropicCostClient(async_get_clientsession(hass), entry.data[CONF_ADMIN_KEY])
    coordinator = AnthropicCreditCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AnthropicCreditConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
