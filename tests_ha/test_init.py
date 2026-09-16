"""Integration lifecycle tests using the official Home Assistant fixtures."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.config_entries import (
    ConfigEntryState,
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edf_tempo.api import (
    EdfTempoApiError,
    EdfTempoAuthError,
    TempoCalendarData,
    TempoDayData,
    TempoSeasonSummaryData,
)
from custom_components.edf_tempo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
    PARIS_TIME_ZONE,
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


class _FrozenDateTime(datetime):
    """Datetime subclass whose current time can be moved during a test."""

    fixed_now: datetime

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.fixed_now.replace(tzinfo=None)
        return cls.fixed_now.astimezone(tz)


async def _mock_first_refresh(
    coordinator: EdfTempoDataUpdateCoordinator,
) -> None:
    """Provide deterministic coordinator data without contacting RTE."""
    coordinator.async_set_updated_data(MOCK_DATA)


@pytest.mark.parametrize(
    "failure_after_midnight",
    [
        EdfTempoApiError("RTE still unavailable"),
        EdfTempoAuthError("Authentication failed"),
    ],
    ids=["api-error", "authentication-error"],
)
async def test_snapshot_expires_after_consecutive_failure_crosses_midnight(
    hass: HomeAssistant,
    failure_after_midnight: Exception,
) -> None:
    """The stored HA state must become unavailable after the snapshot expires."""
    _FrozenDateTime.fixed_now = datetime(
        2026, 7, 27, 23, 55, tzinfo=PARIS_TIME_ZONE
    )
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
        patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert hass.states.get("sensor.edf_tempo_today").state == "blue"
        assert all(
            hass.states.get(entity_id).state != STATE_UNAVAILABLE
            for entity_id in ENTITY_IDS
        )

        with patch.object(
            coordinator.client,
            "async_get_tempo_days",
            new=AsyncMock(
                side_effect=[
                    EdfTempoApiError("RTE unavailable"),
                    failure_after_midnight,
                    failure_after_midnight,
                ]
            ),
        ):
            # The first failure notifies entities, but today's snapshot is
            # still valid and must remain visible before Paris midnight.
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get("sensor.edf_tempo_today").state == "blue"
            assert all(
                hass.states.get(entity_id).state != STATE_UNAVAILABLE
                for entity_id in ENTITY_IDS
            )

            # An authentication failure follows the API failure after the
            # retained snapshot has expired. Verify the state stored by Home
            # Assistant, not only the entity's Python `available` property.
            _FrozenDateTime.fixed_now = datetime(
                2026, 7, 28, 0, 0, tzinfo=PARIS_TIME_ZONE
            )
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert all(
                hass.states.get(entity_id).state == STATE_UNAVAILABLE
                for entity_id in ENTITY_IDS
            )

            # Further failures must not rewrite the already unavailable
            # entities every five minutes.
            unavailable_last_updated = {
                entity_id: hass.states.get(entity_id).last_updated
                for entity_id in ENTITY_IDS
            }
            _FrozenDateTime.fixed_now = datetime(
                2026, 7, 28, 0, 5, tzinfo=PARIS_TIME_ZONE
            )
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert {
                entity_id: hass.states.get(entity_id).last_updated
                for entity_id in ENTITY_IDS
            } == unavailable_last_updated

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


async def test_entity_ids_remain_english_with_french_language(
    hass: HomeAssistant,
) -> None:
    """French display translations must not localize entity IDs."""
    hass.config.language = "fr"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EDF Tempo",
        data=OLD_CREDENTIALS,
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

    registry_entries = er.async_entries_for_config_entry(
        er.async_get(hass), entry.entry_id
    )
    assert {registry_entry.entity_id for registry_entry in registry_entries} == ENTITY_IDS
    assert hass.states.get("sensor.edf_tempo_aujourd_hui") is None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()


async def test_install_reload_reauth_uninstall(hass: HomeAssistant) -> None:
    """Exercise the complete config entry lifecycle with real HA services."""
    _FrozenDateTime.fixed_now = datetime(
        2026, 7, 27, 11, 0, tzinfo=PARIS_TIME_ZONE
    )
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
        patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert all(hass.states.get(entity_id) is not None for entity_id in ENTITY_IDS)
        assert hass.states.get("sensor.edf_tempo_today").state == "blue"
        assert hass.states.get("sensor.edf_tempo_tomorrow").state == "white"

        entity_registry = er.async_get(hass)
        entity_registry.async_update_entity(
            "sensor.edf_tempo_today",
            new_entity_id="sensor.ma_couleur_tempo",
        )
        assert hass.states.get("sensor.ma_couleur_tempo") is not None

        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.ma_couleur_tempo") is not None
        assert hass.states.get("sensor.edf_tempo_today") is None
        assert all(
            hass.states.get(entity_id) is not None
            for entity_id in ENTITY_IDS - {"sensor.edf_tempo_today"}
        )

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
        assert hass.states.get("sensor.ma_couleur_tempo") is not None
        assert all(
            hass.states.get(entity_id) is not None
            for entity_id in ENTITY_IDS - {"sensor.edf_tempo_today"}
        )

        remove_result = await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

    assert remove_result == {"require_restart": False}
    assert hass.config_entries.async_entries(DOMAIN) == []
    assert all(hass.states.get(entity_id) is None for entity_id in ENTITY_IDS)
    assert hass.states.get("sensor.ma_couleur_tempo") is None
    assert DOMAIN not in hass.data


async def test_repeated_reinstall_after_entity_id_renames(
    hass: HomeAssistant,
) -> None:
    """Reinstall cleanly after repeated entity ID customizations and removals."""
    entity_registry = er.async_get(hass)

    with patch.object(
        EdfTempoDataUpdateCoordinator,
        "async_config_entry_first_refresh",
        _mock_first_refresh,
    ):
        for cycle in range(1, 4):
            entry = MockConfigEntry(
                domain=DOMAIN,
                title="EDF Tempo",
                data=OLD_CREDENTIALS,
                unique_id=DOMAIN,
            )
            entry.add_to_hass(hass)

            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

            registry_entries = er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            )
            assert len(registry_entries) == len(ENTITY_IDS)
            assert {item.entity_id for item in registry_entries} == ENTITY_IDS
            assert all(hass.states.get(entity_id) is not None for entity_id in ENTITY_IDS)

            renamed_entity_id = f"sensor.ma_couleur_tempo_cycle_{cycle}"
            entity_registry.async_update_entity(
                "sensor.edf_tempo_today",
                new_entity_id=renamed_entity_id,
            )

            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            assert hass.states.get(renamed_entity_id) is not None
            assert hass.states.get("sensor.edf_tempo_today") is None
            assert len(
                er.async_entries_for_config_entry(entity_registry, entry.entry_id)
            ) == len(ENTITY_IDS)

            remove_result = await hass.config_entries.async_remove(entry.entry_id)
            await hass.async_block_till_done()

            assert remove_result == {"require_restart": False}
            assert er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            ) == []
            assert all(hass.states.get(entity_id) is None for entity_id in ENTITY_IDS)
            assert hass.states.get(renamed_entity_id) is None
            assert hass.config_entries.async_entries(DOMAIN) == []

    assert DOMAIN not in hass.data


async def test_reconfigure_hides_and_preserves_blank_secret(
    hass: HomeAssistant,
) -> None:
    """Reconfigure should never prefill the secret and blank should preserve it."""
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

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        assert result["data_schema"]({}) == {
            CONF_CLIENT_ID: OLD_CREDENTIALS[CONF_CLIENT_ID],
            CONF_CLIENT_SECRET: "",
        }
        assert OLD_CREDENTIALS[CONF_CLIENT_SECRET] not in repr(result["data_schema"])

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_CLIENT_ID: "updated-client-id", CONF_CLIENT_SECRET: ""},
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.data == {
            CONF_CLIENT_ID: "updated-client-id",
            CONF_CLIENT_SECRET: OLD_CREDENTIALS[CONF_CLIENT_SECRET],
        }
        assert entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
