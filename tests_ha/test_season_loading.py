"""Concurrent season loading with Home Assistant's real storage helpers."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edf_tempo.api import EdfTempoClient
from custom_components.edf_tempo.const import DOMAIN
from custom_components.edf_tempo.coordinator import EdfTempoDataUpdateCoordinator
from custom_components.edf_tempo.season_cache import EdfTempoSeasonCache


async def test_concurrent_calendar_requests_persist_one_shared_season(hass: HomeAssistant) -> None:
    """Two callers share the fetch and the result survives a cache reload."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    cache = EdfTempoSeasonCache(hass)
    client = EdfTempoClient(Mock(), client_id="test", client_secret="test")
    coordinator = EdfTempoDataUpdateCoordinator(hass, entry, client, cache)
    started = asyncio.Event()
    release = asyncio.Event()

    async def fetch(start, end):
        started.set()
        await release.wait()
        return {"2020-09-01": "BLUE", "2020-09-02": "WHITE"}

    with patch.object(client, "async_get_season_day_colors", new=AsyncMock(side_effect=fetch)) as request:
        first = asyncio.create_task(coordinator.async_get_season_entry(2020))
        await started.wait()
        second = asyncio.create_task(coordinator.async_get_season_entry(2020))
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(first, second)
        request.assert_awaited_once()
        assert results[0] is results[1]
        assert not coordinator._season_loads

        reloaded_cache = EdfTempoSeasonCache(hass)
        await reloaded_cache.async_load()
        assert reloaded_cache.get("2020-09-01") == results[0]
        assert await coordinator.async_get_season_entry(2020) == results[0]
        request.assert_awaited_once()
