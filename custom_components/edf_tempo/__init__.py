"""The EDF Tempo integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EdfTempoClient
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, DATA_COORDINATOR, DOMAIN
from .coordinator import EdfTempoDataUpdateCoordinator
from .frontend import async_register_frontend
from .season_cache import EdfTempoSeasonCache
from .websocket_api import async_register as async_register_websocket

PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the EDF Tempo integration."""
    hass.data.setdefault(DOMAIN, {})
    await async_register_frontend(hass)
    if not hass.data[DOMAIN].get("_websocket_registered"):
        async_register_websocket(hass)
        hass.data[DOMAIN]["_websocket_registered"] = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EDF Tempo from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    season_cache = EdfTempoSeasonCache(hass)
    await season_cache.async_load()
    client = EdfTempoClient(
        session=session,
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
    )
    coordinator = EdfTempoDataUpdateCoordinator(hass, entry, client, season_cache)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.data[DOMAIN][DATA_COORDINATOR] = coordinator
    await _async_rename_sensor_entity_ids(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an EDF Tempo config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        removed = hass.data[DOMAIN].pop(entry.entry_id, None)
        if hass.data[DOMAIN].get(DATA_COORDINATOR) is removed:
            hass.data[DOMAIN].pop(DATA_COORDINATOR, None)
        if list(hass.data[DOMAIN].keys()) == ["_websocket_registered"]:
            hass.data.pop(DOMAIN)
        elif not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries."""
    return True


async def _async_rename_sensor_entity_ids(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Rename existing EDF Tempo entity IDs to their canonical English form."""
    entity_registry = er.async_get(hass)
    desired_entity_ids = {
        f"{entry.entry_id}_today": "sensor.edf_tempo_today",
        f"{entry.entry_id}_tomorrow": "sensor.edf_tempo_tomorrow",
        f"{entry.entry_id}_season_summary": "sensor.edf_tempo_season_summary",
        f"{entry.entry_id}_remaining_red_days": "sensor.edf_tempo_remaining_red_days",
        f"{entry.entry_id}_remaining_white_days": "sensor.edf_tempo_remaining_white_days",
        f"{entry.entry_id}_remaining_blue_days": "sensor.edf_tempo_remaining_blue_days",
    }

    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        desired_entity_id = desired_entity_ids.get(entity_entry.unique_id)
        if desired_entity_id is None or entity_entry.entity_id == desired_entity_id:
            continue

        if entity_registry.async_get(desired_entity_id) is not None:
            continue

        entity_registry.async_update_entity(
            entity_entry.entity_id,
            new_entity_id=desired_entity_id,
        )
