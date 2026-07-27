"""Lovelace resource tests using the official Home Assistant fixtures."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edf_tempo.api import (
    TempoCalendarData,
    TempoDayData,
    TempoSeasonSummaryData,
)
from custom_components.edf_tempo.const import (
    CARD_URL_PATH,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
)
from custom_components.edf_tempo.coordinator import EdfTempoDataUpdateCoordinator
from custom_components.edf_tempo.frontend import CARD_RESOURCE_URL

LOVELACE_DATA = "lovelace"

MOCK_DATA = TempoCalendarData(
    today=TempoDayData("2026-07-27", "BLUE", "Blue", False, None),
    tomorrow=TempoDayData("2026-07-28", "WHITE", "White", False, None),
    season_summary=TempoSeasonSummaryData(
        "2025-09-01", "2026-08-31", 360, 298, 42, 20
    ),
    fetched_at="2026-07-27T11:00:00+02:00",
)


async def _mock_first_refresh(
    coordinator: EdfTempoDataUpdateCoordinator,
) -> None:
    coordinator.async_set_updated_data(MOCK_DATA)


async def test_lovelace_resource_is_served_and_not_duplicated(
    hass: HomeAssistant,
    hass_client,
) -> None:
    """Register one Lovelace module and serve the bundled card JavaScript."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EDF Tempo",
        data={CONF_CLIENT_ID: "client-id", CONF_CLIENT_SECRET: "client-secret"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch.object(
        EdfTempoDataUpdateCoordinator,
        "async_config_entry_first_refresh",
        _mock_first_refresh,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        lovelace_data = hass.data[LOVELACE_DATA]
        resources = (
            lovelace_data["resources"]
            if isinstance(lovelace_data, dict)
            else lovelace_data.resources
        )
        await resources.async_get_info()
        matching_resources = [
            resource
            for resource in resources.async_items()
            if resource["url"].split("?", 1)[0] == CARD_URL_PATH
        ]
        assert len(matching_resources) == 1
        assert matching_resources[0]["url"] == CARD_RESOURCE_URL
        assert matching_resources[0]["type"] == "module"

        client = await hass_client()
        response = await client.get(CARD_URL_PATH)
        assert response.status == 200
        assert "custom:edf-tempo-card" in await response.text()

        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        matching_resources = [
            resource
            for resource in resources.async_items()
            if resource["url"].split("?", 1)[0] == CARD_URL_PATH
        ]
        assert len(matching_resources) == 1

        remove_result = await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
        assert remove_result == {"require_restart": False}

        await resources.async_get_info()
        matching_resources = [
            resource
            for resource in resources.async_items()
            if resource["url"].split("?", 1)[0] == CARD_URL_PATH
        ]
        assert matching_resources == []
