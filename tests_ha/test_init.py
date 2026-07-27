"""Integration lifecycle tests using the official Home Assistant fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState, SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edf_tempo.api import (
    TempoCalendarData,
    TempoDayData,
    TempoSeasonSummaryData,
)
from custom_components.edf_tempo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
)
from custom_components.edf_tempo.coordinator import EdfTempoDataUpdateCoordinator

OLD_CREDENTIALS = {
    CONF_CLIENT_ID: "old-client-id",
    CONF_CLIENT_SECRET: "old-client-secret",
}
NEW_CREDENTIALS = {
    CONF_CLIENT_ID: "new-client-id",
    CONF_CLIENT_SECRET: "new-client-secret",
}
ENTITY_IDS = {
    "sensor.edf_tempo_today",
    "sensor.edf_tempo_tomorrow",
    "sensor.edf_tempo_season_summary",
    "sensor.edf_tempo_remaining_red_days",
    "sensor.edf_tempo_remaining_white_days",
    "sensor.edf_tempo_remaining_blue_days",
}
MOCK_DATA = TempoCalendarData(
    today=TempoDayData(
        date="2026-07-27",
        color_code="BLUE",
        display_color="Blue",
        fallback=False,
        updated_date="2026-07-27T00:00:00+02:00",
    ),
    tomorrow=TempoDayData(
        date="2026-07-28",
        color_code="WHITE",
        display_color="White",
        fallback=False,
        updated_date="2026-07-27T11:00:00+02:00",
    ),
    season_summary=TempoSeasonSummaryData(
        season_start="2025-09-01",
        season_end="2026-08-31",
        total_placed=360,
        blue_days=298,
        white_days=42,
        red_days=20,
    ),
    fetched_at="2026-07-27T11:00:00+02:00",
)


async def _mock_first_refresh(
    coordinator: EdfTempoDataUpdateCoordinator,
) -> None:
    """Provide deterministic coordinator data without contacting RTE."""
    coordinator.async_set_updated_data(MOCK_DATA)


async def test_install_reload_reauth_uninstall(hass: HomeAssistant) -> None:
    """Exercise the complete config entry lifecycle with real HA services."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EDF Tempo",
        data=OLD_CREDENTIALS,
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with (
        patch.object(
            EdfTempoDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            _mock_first_refresh,
        ),
        patch(
            "custom_components.edf_tempo.config_flow.EdfTempoClient.async_validate_credentials",
            new=AsyncMock(return_value=None),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert all(hass.states.get(entity_id) is not None for entity_id in ENTITY_IDS)
        assert hass.states.get("sensor.edf_tempo_today").state == "blue"
        assert hass.states.get("sensor.edf_tempo_tomorrow").state == "white"

        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert all(hass.states.get(entity_id) is not None for entity_id in ENTITY_IDS)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=dict(entry.data),
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=NEW_CREDENTIALS,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data == NEW_CREDENTIALS
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert all(hass.states.get(entity_id) is not None for entity_id in ENTITY_IDS)

        remove_result = await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

    assert remove_result == {"require_restart": False}
    assert hass.config_entries.async_entries(DOMAIN) == []
    assert all(hass.states.get(entity_id) is None for entity_id in ENTITY_IDS)
    assert DOMAIN not in hass.data
