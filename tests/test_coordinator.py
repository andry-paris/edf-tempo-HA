"""Unit tests for EDF Tempo coordinator scheduling logic."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tests._ha_stubs import install

install()

from custom_components.edf_tempo.api import (
    EdfTempoApiError,
    EdfTempoAuthError,
    EdfTempoClient,
    TempoCalendarData,
    TempoDayData,
    TempoDayWindowData,
    TempoSeasonSummaryData,
)
from custom_components.edf_tempo.const import PARIS_TIME_ZONE
from custom_components.edf_tempo.coordinator import (
    API_RETRY_INTERVAL,
    EdfTempoDataUpdateCoordinator,
)
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


def _day(date_value: str, color_code: str | None) -> TempoDayData:
    display_map = {"BLUE": "Blue", "WHITE": "White", "RED": "Red"}
    return TempoDayData(
        date=date_value,
        color_code=color_code,
        display_color=display_map.get(color_code),
        fallback=False,
        updated_date=None,
    )


def _calendar(today_color: str | None, tomorrow_color: str | None) -> TempoCalendarData:
    return TempoCalendarData(
        today=_day("2026-04-12", today_color),
        tomorrow=_day("2026-04-13", tomorrow_color),
        season_summary=TempoSeasonSummaryData(
            season_start="2025-09-01",
            season_end="2026-08-31",
            total_placed=10,
            blue_days=7,
            white_days=2,
            red_days=1,
        ),
        fetched_at="2026-04-12T00:00:00+02:00",
    )


class _FrozenDateTime(datetime):
    """datetime subclass whose now() can be pinned by tests."""

    fixed_now: datetime

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.fixed_now
        return cls.fixed_now.astimezone(tz)


class EdfTempoCoordinatorSchedulingTests(unittest.TestCase):
    """Validate polling window scheduling decisions."""

    def setUp(self) -> None:
        self.coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        self.coordinator._overnight_baseline_date = None
        self.coordinator._overnight_baseline = None
        self.coordinator._midday_baseline_date = None
        self.coordinator._midday_baseline = None

    def test_midday_window_polls_until_next_slot_when_no_change(self) -> None:
        """Within the midday window, no change should schedule the next slot."""
        now = datetime(2026, 4, 12, 10, 45, tzinfo=PARIS_TIME_ZONE)
        _FrozenDateTime.fixed_now = now
        current = _calendar("BLUE", None)
        previous = _calendar("BLUE", None)

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            interval = self.coordinator._compute_next_update_interval(current, previous)

        self.assertEqual(interval, timedelta(minutes=25))

    def test_midday_window_stops_polling_after_change(self) -> None:
        """Once the midday publication changes, polling should stop for that window."""
        now = datetime(2026, 4, 12, 11, 15, tzinfo=PARIS_TIME_ZONE)
        _FrozenDateTime.fixed_now = now
        current = _calendar("BLUE", "RED")
        previous = _calendar("BLUE", None)

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            interval = self.coordinator._compute_next_update_interval(current, previous)

        next_midnight = datetime(2026, 4, 13, 0, 0, tzinfo=PARIS_TIME_ZONE)
        self.assertEqual(interval, next_midnight - now)

    def test_overnight_window_polls_until_next_slot_when_no_change(self) -> None:
        """Within the overnight window, no change should keep polling every slot."""
        now = datetime(2026, 4, 12, 0, 5, tzinfo=PARIS_TIME_ZONE)
        _FrozenDateTime.fixed_now = now
        current = _calendar("BLUE", None)
        previous = _calendar("BLUE", None)

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            interval = self.coordinator._compute_next_update_interval(current, previous)

        self.assertEqual(interval, timedelta(minutes=25))


class EdfTempoCoordinatorRetryTests(unittest.IsolatedAsyncioTestCase):
    """Validate retry scheduling after transient API failures."""

    async def test_day_failure_stops_before_season_and_can_retry(self) -> None:
        """The original daily-first flow remains intact during outages."""
        _FrozenDateTime.fixed_now = datetime(2026, 4, 12, 10, 45, tzinfo=PARIS_TIME_ZONE)
        for day_error in (
            EdfTempoApiError("days 500"),
            EdfTempoAuthError("days 403"),
        ):
            with self.subTest(day_error=day_error):
                coordinator = EdfTempoDataUpdateCoordinator(
                    HomeAssistant(), ConfigEntry(), AsyncMock(), Mock()
                )
                previous = _calendar("BLUE", None)
                coordinator.data = previous
                coordinator.client.async_get_tempo_days.side_effect = day_error
                coordinator._async_get_current_season_summary = AsyncMock()
                with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
                    with self.assertRaises(UpdateFailed):
                        await coordinator._async_update_data()
                coordinator._async_get_current_season_summary.assert_not_awaited()
                self.assertIs(coordinator.data, previous)
                self.assertEqual(coordinator.update_interval, API_RETRY_INTERVAL)
                self.assertEqual(
                    coordinator.config_entry.reauth_requested,
                    isinstance(day_error, EdfTempoAuthError),
                )

    async def test_season_failures_keep_new_daily_colors_and_can_recover(self) -> None:
        """API, auth and storage errors in season work cannot hide new colors."""
        _FrozenDateTime.fixed_now = datetime(2026, 4, 12, 10, 45, tzinfo=PARIS_TIME_ZONE)
        for season_error in (
            EdfTempoApiError("season 500"),
            EdfTempoAuthError("season 403"),
            OSError("season storage failed"),
        ):
            with self.subTest(season_error=season_error):
                coordinator = EdfTempoDataUpdateCoordinator(
                    HomeAssistant(), ConfigEntry(), AsyncMock(), Mock()
                )
                coordinator.data = None
                coordinator.client.async_get_tempo_days.return_value = TempoDayWindowData(
                    today=_day("2026-04-12", "BLUE"),
                    tomorrow=_day("2026-04-13", "RED"),
                )
                season_fetch = AsyncMock(side_effect=season_error)
                coordinator._async_get_current_season_summary = season_fetch
                coordinator._last_current_season_summary = Mock(return_value=None)
                with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
                    partial = await coordinator._async_update_data()
                    self.assertEqual(partial.today.color_code, "BLUE")
                    self.assertEqual(partial.tomorrow.color_code, "RED")
                    self.assertIsNone(partial.season_summary)
                    self.assertEqual(coordinator.update_interval, API_RETRY_INTERVAL)

                    coordinator.data = partial
                    coordinator.last_update_success = True
                    season_fetch.side_effect = None
                    season_fetch.return_value = _calendar("BLUE", "RED").season_summary
                    recovered = await coordinator._async_update_data()
                self.assertIsNotNone(recovered.season_summary)
                self.assertEqual(season_fetch.await_count, 2)

    async def test_api_failure_replaces_previous_interval_with_retry_interval(self) -> None:
        """A transient failure should retry soon instead of reusing a long delay."""
        coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        coordinator.data = _calendar("BLUE", None)
        coordinator.last_update_success = True
        coordinator.update_interval = timedelta(hours=6, minutes=40)
        coordinator._expired_snapshot_notified_for = None
        coordinator.client = AsyncMock()
        coordinator.client.async_get_tempo_days.side_effect = EdfTempoApiError(
            "API request failed with status 500"
        )
        coordinator._async_get_current_season_summary = AsyncMock(
            side_effect=EdfTempoApiError("season request failed")
        )

        with self.assertRaises(UpdateFailed):
            await coordinator._async_update_data()

        self.assertEqual(coordinator.update_interval, API_RETRY_INTERVAL)
        coordinator._async_get_current_season_summary.assert_not_awaited()

    async def test_successful_retry_compares_with_data_from_before_failure(self) -> None:
        """Recovery should detect a publication and restore normal scheduling."""
        previous = _calendar("BLUE", None)
        coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        coordinator.data = previous
        coordinator.last_update_success = False
        coordinator.update_interval = API_RETRY_INTERVAL
        coordinator._overnight_baseline_date = None
        coordinator._overnight_baseline = None
        coordinator._midday_baseline_date = None
        coordinator._midday_baseline = None
        coordinator._expired_snapshot_notified_for = "2026-04-12"
        coordinator._refresh_started_after_failure = True
        coordinator.client = AsyncMock()
        coordinator.client.async_get_tempo_days.return_value = TempoDayWindowData(
            today=_day("2026-04-12", "BLUE"),
            tomorrow=_day("2026-04-13", "RED"),
        )
        coordinator._async_get_current_season_summary = AsyncMock(
            return_value=previous.season_summary
        )
        now = datetime(2026, 4, 12, 10, 45, tzinfo=PARIS_TIME_ZONE)
        _FrozenDateTime.fixed_now = now

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            data = await coordinator._async_update_data()

        self.assertEqual(data.tomorrow.color_code, "RED")
        self.assertEqual(
            coordinator.update_interval,
            datetime(2026, 4, 13, 0, 0, tzinfo=PARIS_TIME_ZONE) - now,
        )

    async def test_day_colors_recover_while_season_summary_is_unavailable(self) -> None:
        """A season request failure must not discard a successful day request."""
        coordinator = EdfTempoDataUpdateCoordinator(
            HomeAssistant(), ConfigEntry(), AsyncMock(), Mock()
        )
        coordinator.data = _calendar("BLUE", None)
        coordinator.last_update_success = False
        coordinator.client.async_get_tempo_days.return_value = TempoDayWindowData(
            today=_day("2026-04-12", "BLUE"),
            tomorrow=_day("2026-04-13", "RED"),
        )
        coordinator._async_get_current_season_summary = AsyncMock(
            side_effect=EdfTempoApiError("season endpoint unavailable")
        )
        coordinator._last_current_season_summary = Mock(
            return_value=coordinator.data.season_summary
        )
        _FrozenDateTime.fixed_now = datetime(2026, 4, 12, 10, 45, tzinfo=PARIS_TIME_ZONE)

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            recovered_days = await coordinator._async_update_data()

        self.assertEqual(recovered_days.tomorrow.color_code, "RED")
        self.assertEqual(recovered_days.season_summary, coordinator.data.season_summary)
        self.assertEqual(coordinator.update_interval, API_RETRY_INTERVAL)

        coordinator.data = recovered_days
        coordinator.last_update_success = True
        coordinator._async_get_current_season_summary = AsyncMock(
            return_value=recovered_days.season_summary
        )
        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            fully_recovered = await coordinator._async_update_data()

        self.assertEqual(fully_recovered.season_summary, recovered_days.season_summary)
        self.assertGreater(coordinator.update_interval, API_RETRY_INTERVAL)

    async def test_summary_failure_keeps_cached_update_date(self) -> None:
        """A failed summary refresh must retain the date of the available totals."""
        previous = _calendar("BLUE", None)
        cached_at = "2026-04-11T10:45:00+02:00"
        season_cache = Mock()
        season_cache.get.return_value = Mock(
            summary=previous.season_summary, updated_at=cached_at
        )
        coordinator = EdfTempoDataUpdateCoordinator(
            HomeAssistant(), ConfigEntry(), AsyncMock(), season_cache
        )
        coordinator.data = previous
        coordinator.last_update_success = True
        coordinator.client.async_get_tempo_days.return_value = TempoDayWindowData(
            today=_day("2026-04-12", "BLUE"),
            tomorrow=_day("2026-04-13", "RED"),
        )
        coordinator._async_get_current_season_summary = AsyncMock(
            side_effect=EdfTempoApiError("season 500")
        )
        coordinator._last_current_season_summary = Mock(
            return_value=previous.season_summary
        )
        _FrozenDateTime.fixed_now = datetime(2026, 4, 12, 10, 45, tzinfo=PARIS_TIME_ZONE)

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            result = await coordinator._async_update_data()

        self.assertEqual(result.tomorrow.color_code, "RED")
        self.assertEqual(result.season_summary, previous.season_summary)
        self.assertEqual(result.summary_updated_at, cached_at)
        self.assertEqual(coordinator.update_interval, API_RETRY_INTERVAL)

    async def test_first_day_success_is_kept_without_a_season_summary(self) -> None:
        """An empty season cache leaves only the counters unknown."""
        coordinator = EdfTempoDataUpdateCoordinator(
            HomeAssistant(), ConfigEntry(), AsyncMock(), Mock()
        )
        coordinator.data = None
        coordinator.last_update_success = False
        coordinator.client.async_get_tempo_days.return_value = TempoDayWindowData(
            today=_day("2026-04-12", "BLUE"),
            tomorrow=_day("2026-04-13", None),
        )
        coordinator._async_get_current_season_summary = AsyncMock(
            side_effect=EdfTempoApiError("season endpoint unavailable")
        )
        coordinator._last_current_season_summary = Mock(return_value=None)
        _FrozenDateTime.fixed_now = datetime(2026, 4, 12, 10, 45, tzinfo=PARIS_TIME_ZONE)

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            data = await coordinator._async_update_data()

        self.assertEqual(data.today.color_code, "BLUE")
        self.assertIsNone(data.season_summary)
        self.assertEqual(coordinator.update_interval, API_RETRY_INTERVAL)

    def test_previous_season_totals_are_not_reused_after_season_change(self) -> None:
        """A September outage must not show last season's allowance."""
        client = Mock()
        client._get_current_season_bounds = EdfTempoClient._get_current_season_bounds
        coordinator = EdfTempoDataUpdateCoordinator(
            HomeAssistant(), ConfigEntry(), client, Mock()
        )
        coordinator._season_cache.get.return_value = None
        _FrozenDateTime.fixed_now = datetime(2026, 9, 1, 0, 5, tzinfo=PARIS_TIME_ZONE)

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            self.assertIsNone(coordinator._last_current_season_summary(_calendar("BLUE", None)))

    def test_expired_snapshot_notifies_listeners_only_once(self) -> None:
        """Repeated failures must not rewrite unchanged entities each time."""
        coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        coordinator.data = _calendar("BLUE", "RED")
        coordinator.last_update_success = False
        coordinator._expired_snapshot_notified_for = None
        coordinator._refresh_started_after_failure = True
        coordinator.async_update_listeners = Mock()
        _FrozenDateTime.fixed_now = datetime(
            2026, 4, 13, 0, 5, tzinfo=PARIS_TIME_ZONE
        )

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            coordinator._async_refresh_finished()
            coordinator._async_refresh_finished()

        coordinator.async_update_listeners.assert_called_once_with()
        self.assertEqual(coordinator._expired_snapshot_notified_for, "2026-04-13")

        _FrozenDateTime.fixed_now = datetime(2026, 4, 14, 0, 5, tzinfo=PARIS_TIME_ZONE)
        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            coordinator._async_refresh_finished()
        self.assertEqual(coordinator.async_update_listeners.call_count, 2)
        self.assertEqual(coordinator._expired_snapshot_notified_for, "2026-04-14")

    def test_first_failure_lets_home_assistant_notify_expired_snapshot(self) -> None:
        """The hook must not duplicate HA's notification on a first failure."""
        coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        coordinator.data = _calendar("BLUE", "RED")
        coordinator.last_update_success = False
        coordinator._expired_snapshot_notified_for = None
        coordinator._refresh_started_after_failure = False
        coordinator.async_update_listeners = Mock()
        _FrozenDateTime.fixed_now = datetime(
            2026, 4, 13, 0, 5, tzinfo=PARIS_TIME_ZONE
        )

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            coordinator._async_refresh_finished()

        coordinator.async_update_listeners.assert_not_called()
        self.assertEqual(coordinator._expired_snapshot_notified_for, "2026-04-13")

    def test_failure_with_current_snapshot_does_not_notify_listeners(self) -> None:
        """A same-day snapshot should remain available without a forced write."""
        coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        coordinator.data = _calendar("BLUE", "RED")
        coordinator.last_update_success = False
        coordinator._expired_snapshot_notified_for = None
        coordinator._refresh_started_after_failure = True
        coordinator.async_update_listeners = Mock()
        _FrozenDateTime.fixed_now = datetime(
            2026, 4, 12, 23, 55, tzinfo=PARIS_TIME_ZONE
        )

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            coordinator._async_refresh_finished()

        coordinator.async_update_listeners.assert_not_called()
        self.assertIsNone(coordinator._expired_snapshot_notified_for)

    def test_successful_refresh_resets_expiration_notification_guard(self) -> None:
        """A recovered coordinator should prepare the guard for the next day."""
        coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        coordinator.data = _calendar("BLUE", "RED")
        coordinator.last_update_success = True
        coordinator._expired_snapshot_notified_for = "2026-04-13"
        coordinator._refresh_started_after_failure = True
        coordinator.async_update_listeners = Mock()

        coordinator._async_refresh_finished()

        coordinator.async_update_listeners.assert_not_called()
        self.assertIsNone(coordinator._expired_snapshot_notified_for)


class EdfTempoConcurrentSeasonTests(unittest.IsolatedAsyncioTestCase):
    """Exercise overlapping requests without contacting RTE."""

    async def asyncSetUp(self) -> None:
        self.entries = {}
        self.cache = Mock()
        self.cache.get.side_effect = self.entries.get

        async def save(entry):
            self.entries[entry.summary.season_start] = entry

        self.cache.async_set = AsyncMock(side_effect=save)
        self.client = Mock()
        self.client._get_current_season_bounds = EdfTempoClient._get_current_season_bounds
        self.started = asyncio.Event()
        self.release = asyncio.Event()

        async def fetch(start, end):
            self.started.set()
            await self.release.wait()
            return {start.isoformat(): "BLUE"}

        self.client.async_get_season_day_colors = AsyncMock(side_effect=fetch)
        self.coordinator = EdfTempoDataUpdateCoordinator(
            HomeAssistant(), ConfigEntry(), self.client, self.cache
        )

    async def test_same_season_shares_download_and_cache_write(self) -> None:
        first = asyncio.create_task(self.coordinator.async_get_season_entry(2020))
        await self.started.wait()
        second = asyncio.create_task(self.coordinator.async_get_season_entry(2020))
        await asyncio.sleep(0)
        self.client.async_get_season_day_colors.assert_awaited_once()
        self.release.set()
        results = await asyncio.gather(first, second)
        self.assertIs(results[0], results[1])
        self.cache.async_set.assert_awaited_once()
        self.assertIs(await self.coordinator.async_get_season_entry(2020), results[0])
        self.client.async_get_season_day_colors.assert_awaited_once()
        self.assertFalse(self.coordinator._season_loads)

    async def test_different_seasons_download_in_parallel(self) -> None:
        first = asyncio.create_task(self.coordinator.async_get_season_entry(2020))
        await self.started.wait()
        self.started.clear()
        second = asyncio.create_task(self.coordinator.async_get_season_entry(2021))
        await asyncio.wait_for(self.started.wait(), timeout=1)
        self.assertEqual(self.client.async_get_season_day_colors.await_count, 2)
        self.release.set()
        results = await asyncio.gather(first, second)
        self.assertNotEqual(results[0].summary.season_start, results[1].summary.season_start)

    async def test_failures_are_shared_and_next_request_can_retry(self) -> None:
        for error in (EdfTempoApiError("offline"), EdfTempoAuthError("rejected")):
            with self.subTest(error=type(error).__name__):
                self.started.clear()
                self.release.clear()
                self.entries.clear()

                async def fail(start, end):
                    self.started.set()
                    await self.release.wait()
                    raise error

                self.client.async_get_season_day_colors.reset_mock()
                self.client.async_get_season_day_colors.side_effect = fail
                first = asyncio.create_task(self.coordinator.async_get_season_entry(2020))
                await self.started.wait()
                second = asyncio.create_task(self.coordinator.async_get_season_entry(2020))
                await asyncio.sleep(0)
                self.release.set()
                results = await asyncio.gather(first, second, return_exceptions=True)
                self.assertTrue(all(result is error for result in results))
                self.client.async_get_season_day_colors.assert_awaited_once()
                self.assertFalse(self.coordinator._season_loads)
                self.client.async_get_season_day_colors.side_effect = None
                self.client.async_get_season_day_colors.return_value = {"2020-09-01": "WHITE"}
                entry = await self.coordinator.async_get_season_entry(2020)
                self.assertEqual(entry.day_colors["2020-09-01"], "WHITE")
                self.assertEqual(self.client.async_get_season_day_colors.await_count, 2)

    async def test_cancelling_one_caller_keeps_shared_download_alive(self) -> None:
        first = asyncio.create_task(self.coordinator.async_get_season_entry(2020))
        await self.started.wait()
        second = asyncio.create_task(self.coordinator.async_get_season_entry(2020))
        await asyncio.sleep(0)
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        self.release.set()
        entry = await second
        self.assertEqual(entry.day_colors["2020-09-01"], "BLUE")
        self.client.async_get_season_day_colors.assert_awaited_once()
        self.assertFalse(self.coordinator._season_loads)


if __name__ == "__main__":
    unittest.main()
