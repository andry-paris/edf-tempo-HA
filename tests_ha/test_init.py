"""Integration lifecycle tests using the official Home Assistant fixtures."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from homeassistant.config_entries import (
    ConfigEntryState,
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edf_tempo.api import (
    EdfTempoApiError,
    EdfTempoAuthError,
    TempoCalendarData,
    TempoDayData,
    TempoDayWindowData,
    TempoSeasonSummaryData,
)
from custom_components.edf_tempo.const import (
    API_BASE_URL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
    PARIS_TIME_ZONE,
    TEMPO_CALENDARS_PATH,
    TOKEN_URL,
)
from custom_components.edf_tempo.coordinator import EdfTempoDataUpdateCoordinator
from custom_components.edf_tempo.season_cache import (
    EdfTempoSeasonCache,
    STORAGE_KEY,
    build_cache_entry,
)

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


@pytest.mark.parametrize("cached", [False, True], ids=["empty", "cached"])
async def test_startup_during_rte_outage_keeps_sensors_available(
    hass: HomeAssistant, hass_storage: dict, cached: bool
) -> None:
    """A failed first request exposes unknown or matching cached colors."""
    _FrozenDateTime.fixed_now = datetime(2026, 7, 27, 12, 0, tzinfo=PARIS_TIME_ZONE)
    if cached:
        cache = EdfTempoSeasonCache(hass)
        await cache.async_set(
            build_cache_entry(
                "2025-09-01", "2026-08-31", {"2026-07-27": "BLUE"}
            )
        )

    entry = MockConfigEntry(
        domain=DOMAIN, title="EDF Tempo", data=OLD_CREDENTIALS, unique_id=DOMAIN
    )
    entry.add_to_hass(hass)
    with (
        patch.object(
            EdfTempoDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            new=AsyncMock(side_effect=ConfigEntryNotReady("RTE unavailable")),
        ),
        patch("custom_components.edf_tempo.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.edf_tempo_today").state == (
            "blue" if cached else "unknown"
        )
        assert hass.states.get("sensor.edf_tempo_tomorrow").state == "unknown"
        if not cached:
            assert all(
                hass.states.get(entity_id).state == "0"
                for entity_id in ENTITY_IDS
                if entity_id not in {"sensor.edf_tempo_today", "sensor.edf_tempo_tomorrow"}
            )
        assert all(
            hass.states.get(entity_id).state != STATE_UNAVAILABLE
            for entity_id in ENTITY_IDS
        )
        hass.data[DOMAIN][entry.entry_id].async_set_updated_data(MOCK_DATA)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.edf_tempo_today").state == "blue"
        assert hass.states.get("sensor.edf_tempo_tomorrow").state == "white"
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize("failure", ["http-500", "network"])
async def test_restart_with_real_rte_failure_creates_available_sensors(
    hass: HomeAssistant, aioclient_mock, failure: str
) -> None:
    """A configured entry must load entities even when its first RTE request fails."""
    _FrozenDateTime.fixed_now = datetime(2026, 7, 27, 12, 0, tzinfo=PARIS_TIME_ZONE)
    aioclient_mock.post(
        TOKEN_URL, json={"access_token": "test-token", "expires_in": 7200}
    )
    response_kwargs = (
        {"status": 500, "json": {}}
        if failure == "http-500"
        else {"exc": aiohttp.ClientConnectionError()}
    )
    aioclient_mock.get(
        f"{API_BASE_URL}{TEMPO_CALENDARS_PATH}", **response_kwargs
    )
    entry = MockConfigEntry(
        domain=DOMAIN, title="EDF Tempo", data=OLD_CREDENTIALS, unique_id=DOMAIN
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.edf_tempo.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert all(
            hass.states.get(entity_id) is not None
            and hass.states.get(entity_id).state != STATE_UNAVAILABLE
            for entity_id in ENTITY_IDS
        )
        assert hass.states.get("sensor.edf_tempo_today").state == "unknown"
        assert hass.states.get("sensor.edf_tempo_season_summary").state == "0"
        assert hass.data[DOMAIN][entry.entry_id].update_interval.total_seconds() == 300

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


async def test_no_snapshot_advances_sensor_dates_during_midnight_outage(
    hass: HomeAssistant,
) -> None:
    """Even without cached data, an outage must not leave yesterday's dates on sensors."""
    _FrozenDateTime.fixed_now = datetime(2026, 7, 27, 23, 55, tzinfo=PARIS_TIME_ZONE)
    entry = MockConfigEntry(
        domain=DOMAIN, title="EDF Tempo", data=OLD_CREDENTIALS, unique_id=DOMAIN
    )
    entry.add_to_hass(hass)
    with (
        patch.object(
            EdfTempoDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            new=AsyncMock(side_effect=ConfigEntryNotReady("RTE unavailable")),
        ),
        patch("custom_components.edf_tempo.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert hass.states.get("sensor.edf_tempo_today").attributes["date"] == "2026-07-27"

        with patch.object(
            coordinator.client,
            "async_get_tempo_days",
            new=AsyncMock(side_effect=EdfTempoApiError("RTE unavailable")),
        ):
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            _FrozenDateTime.fixed_now = datetime(2026, 7, 28, 0, 0, tzinfo=PARIS_TIME_ZONE)
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get("sensor.edf_tempo_today").attributes["date"] == "2026-07-28"
            assert hass.states.get("sensor.edf_tempo_tomorrow").attributes["date"] == "2026-07-29"
            assert all(
                hass.states.get(entity_id).state != STATE_UNAVAILABLE
                for entity_id in ENTITY_IDS
            )
            last_updated = hass.states.get("sensor.edf_tempo_today").last_updated

            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get("sensor.edf_tempo_today").last_updated == last_updated

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize("cached", [False, True], ids=["without-cache", "with-cache"])
async def test_reloading_after_success_keeps_sensors_alive_during_rte_auth_error(
    hass: HomeAssistant, cached: bool,
) -> None:
    """A later RTE auth failure must not remove sensors or stop their recovery."""
    _FrozenDateTime.fixed_now = datetime(2026, 7, 27, 12, 0, tzinfo=PARIS_TIME_ZONE)
    entry = MockConfigEntry(
        domain=DOMAIN, title="EDF Tempo", data=OLD_CREDENTIALS, unique_id=DOMAIN
    )
    entry.add_to_hass(hass)
    with (
        patch.object(
            EdfTempoDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            _mock_first_refresh,
        ),
        patch("custom_components.edf_tempo.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        if cached:
            cache = hass.data[DOMAIN][entry.entry_id]._season_cache
            await cache.async_set(
                build_cache_entry(
                    "2025-09-01", "2026-08-31", {"2026-07-27": "BLUE"}
                )
            )

    with (
        patch(
            "custom_components.edf_tempo.api.EdfTempoClient.async_validate_credentials",
            new=AsyncMock(side_effect=EdfTempoAuthError("RTE token rejected")),
        ),
        patch("custom_components.edf_tempo.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime),
    ):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert len(list(entry.async_get_active_flows(hass, {SOURCE_REAUTH}))) == 1
        assert all(
            hass.states.get(entity_id) is not None
            and hass.states.get(entity_id).state != STATE_UNAVAILABLE
            for entity_id in ENTITY_IDS
        )
        assert hass.states.get("sensor.edf_tempo_today").state == (
            "blue" if cached else "unknown"
        )
        if not cached:
            assert hass.states.get("sensor.edf_tempo_season_summary").state == "0"
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert coordinator.update_interval.total_seconds() == 300

        with (
            patch.object(
                coordinator.client,
                "async_get_tempo_days",
                new=AsyncMock(
                    return_value=TempoDayWindowData(
                        today=MOCK_DATA.today, tomorrow=MOCK_DATA.tomorrow
                    )
                ),
            ),
            patch.object(
                coordinator.client,
                "async_get_season_day_colors",
                new=AsyncMock(return_value={"2026-07-27": "BLUE", "2026-07-28": "WHITE"}),
            ),
        ):
            await coordinator.async_refresh()
            await hass.async_block_till_done()
        assert hass.states.get("sensor.edf_tempo_tomorrow").state == "white"

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()


async def test_day_colors_recover_before_season_summary(hass: HomeAssistant) -> None:
    """A working day endpoint updates colors even if season totals still fail."""
    _FrozenDateTime.fixed_now = datetime(2026, 7, 27, 12, 0, tzinfo=PARIS_TIME_ZONE)
    entry = MockConfigEntry(
        domain=DOMAIN, title="EDF Tempo", data=OLD_CREDENTIALS, unique_id=DOMAIN
    )
    entry.add_to_hass(hass)
    with (
        patch.object(
            EdfTempoDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            new=AsyncMock(side_effect=ConfigEntryNotReady("RTE unavailable")),
        ),
        patch("custom_components.edf_tempo.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert hass.states.get("sensor.edf_tempo_today").state == "unknown"

        with (
            patch.object(
                coordinator.client,
                "async_get_tempo_days",
                new=AsyncMock(
                    return_value=TempoDayWindowData(
                        today=MOCK_DATA.today, tomorrow=MOCK_DATA.tomorrow
                    )
                ),
            ),
            patch.object(
                coordinator,
                "_async_get_current_season_summary",
                new=AsyncMock(side_effect=EdfTempoApiError("season unavailable")),
            ) as summary_fetch,
        ):
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get("sensor.edf_tempo_today").state == "blue"
            assert hass.states.get("sensor.edf_tempo_tomorrow").state == "white"
            assert hass.states.get("sensor.edf_tempo_season_summary").state == "0"
            assert all(
                hass.states.get(entity_id).state == "0"
                for entity_id in ENTITY_IDS
                if entity_id not in {"sensor.edf_tempo_today", "sensor.edf_tempo_tomorrow"}
            )
            assert coordinator.update_interval.total_seconds() == 300

            summary_fetch.side_effect = None
            summary_fetch.return_value = MOCK_DATA.season_summary
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get("sensor.edf_tempo_season_summary").state == "360"

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "day_failure",
    [EdfTempoApiError("days unavailable"), EdfTempoAuthError("days denied")],
    ids=["api-error", "authentication-error"],
)
async def test_day_failure_does_not_request_season(
    hass: HomeAssistant, day_failure: Exception
) -> None:
    """A failed day request retains states and skips the season request."""
    _FrozenDateTime.fixed_now = datetime(2026, 7, 27, 12, 0, tzinfo=PARIS_TIME_ZONE)
    entry = MockConfigEntry(
        domain=DOMAIN, title="EDF Tempo", data=OLD_CREDENTIALS, unique_id=DOMAIN
    )
    entry.add_to_hass(hass)
    with (
        patch.object(
            EdfTempoDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            new=AsyncMock(side_effect=ConfigEntryNotReady("RTE unavailable")),
        ),
        patch("custom_components.edf_tempo.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        with (
            patch.object(
                coordinator.client,
                "async_get_tempo_days",
                new=AsyncMock(side_effect=day_failure),
            ) as day_fetch,
            patch.object(
                coordinator.client,
                "async_get_season_day_colors",
                new=AsyncMock(return_value={"2026-07-27": "BLUE", "2026-07-28": "WHITE"}),
            ) as season_fetch,
        ):
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get("sensor.edf_tempo_today").state == "unknown"
            assert hass.states.get("sensor.edf_tempo_tomorrow").state == "unknown"
            assert hass.states.get("sensor.edf_tempo_season_summary").state == "0"
            assert coordinator.update_interval.total_seconds() == 300
            day_fetch.assert_awaited_once()
            season_fetch.assert_not_awaited()
            last_updated = {
                entity_id: hass.states.get(entity_id).last_updated
                for entity_id in ENTITY_IDS
            }

            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert day_fetch.await_count == 2
            season_fetch.assert_not_awaited()
            assert {
                entity_id: hass.states.get(entity_id).last_updated
                for entity_id in ENTITY_IDS
            } == last_updated

            day_fetch.side_effect = None
            day_fetch.return_value = TempoDayWindowData(
                today=MOCK_DATA.today, tomorrow=MOCK_DATA.tomorrow
            )
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get("sensor.edf_tempo_today").state == "blue"
            assert hass.states.get("sensor.edf_tempo_tomorrow").state == "white"
            assert hass.states.get("sensor.edf_tempo_season_summary").state == "2"
            season_fetch.assert_awaited_once()

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


async def test_midnight_advances_colors_when_only_day_request_fails(
    hass: HomeAssistant,
) -> None:
    """A working season cache must not keep yesterday's color after midnight."""
    _FrozenDateTime.fixed_now = datetime(2026, 7, 27, 23, 55, tzinfo=PARIS_TIME_ZONE)
    entry = MockConfigEntry(
        domain=DOMAIN, title="EDF Tempo", data=OLD_CREDENTIALS, unique_id=DOMAIN
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
        with (
            patch.object(
                coordinator.client,
                "async_get_tempo_days",
                new=AsyncMock(side_effect=EdfTempoApiError("days unavailable")),
            ),
            patch.object(
                coordinator,
                "_async_get_current_season_summary",
                new=AsyncMock(return_value=MOCK_DATA.season_summary),
            ) as summary_fetch,
        ):
            _FrozenDateTime.fixed_now = datetime(
                2026, 7, 28, 0, 0, tzinfo=PARIS_TIME_ZONE
            )
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get("sensor.edf_tempo_today").state == "white"
            assert hass.states.get("sensor.edf_tempo_tomorrow").state == "unknown"
            assert hass.states.get("sensor.edf_tempo_season_summary").state == "360"
            summary_fetch.assert_not_awaited()

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


async def test_daily_api_failure_then_recover(hass: HomeAssistant) -> None:
    """A daily outage skips season work, then restores both feeds on retry."""
    _FrozenDateTime.fixed_now = datetime(2026, 7, 27, 12, 0, tzinfo=PARIS_TIME_ZONE)
    entry = MockConfigEntry(
        domain=DOMAIN, title="EDF Tempo", data=OLD_CREDENTIALS, unique_id=DOMAIN
    )
    entry.add_to_hass(hass)
    with (
        patch.object(
            EdfTempoDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            new=AsyncMock(side_effect=ConfigEntryNotReady("RTE unavailable")),
        ),
        patch("custom_components.edf_tempo.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime),
        patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        with (
            patch.object(
                coordinator.client,
                "async_get_tempo_days",
                new=AsyncMock(side_effect=EdfTempoApiError("days 500")),
            ) as day_fetch,
            patch.object(
                coordinator.client,
                "async_get_season_day_colors",
                new=AsyncMock(side_effect=EdfTempoApiError("season 500")),
            ) as season_fetch,
        ):
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            day_fetch.assert_awaited_once()
            season_fetch.assert_not_awaited()
            assert hass.states.get("sensor.edf_tempo_today").state == "unknown"
            assert hass.states.get("sensor.edf_tempo_season_summary").state == "0"
            assert all(
                hass.states.get(entity_id).state != STATE_UNAVAILABLE
                for entity_id in ENTITY_IDS
            )
            assert coordinator.update_interval.total_seconds() == 300

            day_fetch.side_effect = None
            day_fetch.return_value = TempoDayWindowData(
                today=MOCK_DATA.today, tomorrow=MOCK_DATA.tomorrow
            )
            season_fetch.side_effect = None
            season_fetch.return_value = {
                "2026-07-27": "BLUE", "2026-07-28": "WHITE"
            }
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert day_fetch.await_count == 2
            season_fetch.assert_awaited_once()
            assert hass.states.get("sensor.edf_tempo_today").state == "blue"
            assert hass.states.get("sensor.edf_tempo_tomorrow").state == "white"
            assert hass.states.get("sensor.edf_tempo_season_summary").state == "2"
            assert hass.states.get("sensor.edf_tempo_tomorrow").attributes["fetched_at"]

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "failure",
    ["http-500", "api-connection", "api-timeout", "token-connection"],
)
async def test_real_http_failure_keeps_all_sensors_available(
    hass: HomeAssistant, aioclient_mock, failure: str
) -> None:
    """The original RTE 500 and transport failures must not hide HA entities."""
    _FrozenDateTime.fixed_now = datetime(2026, 7, 27, 12, 0, tzinfo=PARIS_TIME_ZONE)
    entry = MockConfigEntry(
        domain=DOMAIN, title="EDF Tempo", data=OLD_CREDENTIALS, unique_id=DOMAIN
    )
    entry.add_to_hass(hass)
    with (
        patch.object(
            EdfTempoDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            _mock_first_refresh,
        ),
        patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        if failure == "token-connection":
            aioclient_mock.post(TOKEN_URL, exc=aiohttp.ClientConnectionError())
        else:
            aioclient_mock.post(
                TOKEN_URL, json={"access_token": "test-token", "expires_in": 7200}
            )
            response_kwargs = {
                "http-500": {"status": 500, "json": {}},
                "api-connection": {"exc": aiohttp.ClientConnectionError()},
                "api-timeout": {"exc": asyncio.TimeoutError()},
            }[failure]
            aioclient_mock.get(
                f"{API_BASE_URL}{TEMPO_CALENDARS_PATH}", **response_kwargs
            )

        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert coordinator.last_update_success is False
        assert coordinator.update_interval.total_seconds() == 300
        assert all(
            hass.states.get(entity_id) is not None
            and hass.states.get(entity_id).state != STATE_UNAVAILABLE
            for entity_id in ENTITY_IDS
        )
        assert hass.states.get("sensor.edf_tempo_today").state == "blue"
        assert hass.states.get("sensor.edf_tempo_tomorrow").state == "white"

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


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
    """The stored HA state retains dated colors and marks new days unknown."""
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

        with (
            patch.object(
                coordinator.client,
                "async_get_tempo_days",
                new=AsyncMock(
                    side_effect=[
                        EdfTempoApiError("RTE unavailable"),
                        failure_after_midnight,
                        failure_after_midnight,
                    ]
                ),
            ),
            patch.object(
                coordinator,
                "_async_get_current_season_summary",
                new=AsyncMock(side_effect=EdfTempoApiError("season unavailable")),
            ) as summary_fetch,
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

            # A failure crosses midnight. Yesterday's tomorrow color now
            # belongs to today; the new tomorrow has no known color.
            _FrozenDateTime.fixed_now = datetime(
                2026, 7, 28, 0, 0, tzinfo=PARIS_TIME_ZONE
            )
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get("sensor.edf_tempo_today").state == "white"
            assert hass.states.get("sensor.edf_tempo_tomorrow").state == "unknown"
            assert (
                hass.states.get("sensor.edf_tempo_tomorrow").attributes["date"]
                == "2026-07-29"
            )
            assert all(
                hass.states.get(entity_id).state != STATE_UNAVAILABLE
                for entity_id in ENTITY_IDS
            )

            # Further failures must not rewrite unchanged states every five minutes.
            retained_last_updated = {
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
            } == retained_last_updated
            summary_fetch.assert_not_awaited()

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
            "custom_components.edf_tempo.config_flow.EdfTempoClient.async_validate_access",
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
        tomorrow_attributes = hass.states.get("sensor.edf_tempo_tomorrow").attributes
        assert tomorrow_attributes["fetched_at"] == MOCK_DATA.fetched_at
        assert tomorrow_attributes["updated_date"] == MOCK_DATA.tomorrow.updated_date

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


async def test_clear_cache_action_and_removal_delete_persisted_seasons(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """The action and permanent removal delete the mocked HA season store."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EDF Tempo",
        data=OLD_CREDENTIALS,
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    season = build_cache_entry(
        "2020-09-01", "2021-08-31", {"2020-09-01": "BLUE"}
    )

    with patch.object(
        EdfTempoDataUpdateCoordinator,
        "async_config_entry_first_refresh",
        _mock_first_refresh,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        coordinator = hass.data[DOMAIN][entry.entry_id]
        cache = coordinator._season_cache
        assert hass.services.has_service(DOMAIN, "clear_cache")

        await cache.async_set(season)
        assert STORAGE_KEY in hass_storage
        assert cache.get(season.summary.season_start) == season

        with patch.object(
            coordinator.client,
            "async_get_season_day_colors",
            new=AsyncMock(return_value={"2020-09-01": "BLUE"}),
        ) as request:
            await hass.services.async_call(DOMAIN, "clear_cache", blocking=True)
            request.assert_not_awaited()
            assert STORAGE_KEY not in hass_storage
            assert cache.get(season.summary.season_start) is None

            fetched = await coordinator.async_get_season_entry(2020)
            assert fetched.summary == season.summary
            assert fetched.day_colors == season.day_colors
            assert fetched.updated_at is not None
            request.assert_awaited_once()

        await hass.services.async_call(DOMAIN, "clear_cache", blocking=True)
        assert STORAGE_KEY not in hass_storage
        assert cache.get(season.summary.season_start) is None
        reloaded_cache = EdfTempoSeasonCache(hass)
        await reloaded_cache.async_load()
        assert reloaded_cache.get(season.summary.season_start) is None

        await cache.async_set(season)
        assert STORAGE_KEY in hass_storage
        assert await hass.config_entries.async_reload(entry.entry_id)
        assert STORAGE_KEY in hass_storage
        assert hass.services.has_service(DOMAIN, "clear_cache")
        assert hass.data[DOMAIN][entry.entry_id]._season_cache.get(
            season.summary.season_start
        ) == season
        assert await hass.config_entries.async_remove(entry.entry_id) == {
            "require_restart": False
        }
        assert STORAGE_KEY not in hass_storage
        assert not hass.services.has_service(DOMAIN, "clear_cache")


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
            "custom_components.edf_tempo.config_flow.EdfTempoClient.async_validate_access",
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
