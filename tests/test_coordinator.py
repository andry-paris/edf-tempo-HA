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

    async def test_api_failure_replaces_previous_interval_with_retry_interval(self) -> None:
        """A transient failure should retry soon instead of reusing a long delay."""
        coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        coordinator.data = _calendar("BLUE", None)
        coordinator.last_update_success = True
        coordinator.update_interval = timedelta(hours=6, minutes=40)
        coordinator._expired_snapshot_notified = False
        coordinator.client = AsyncMock()
        coordinator.client.async_get_tempo_days.side_effect = EdfTempoApiError(
            "API request failed with status 500"
        )

        with self.assertRaises(UpdateFailed):
            await coordinator._async_update_data()

        self.assertEqual(coordinator.update_interval, API_RETRY_INTERVAL)

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
        coordinator._expired_snapshot_notified = True
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

    def test_expired_snapshot_notifies_listeners_only_once(self) -> None:
        """Repeated failures must not rewrite unavailable entities each time."""
        coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        coordinator.data = _calendar("BLUE", "RED")
        coordinator.last_update_success = False
        coordinator._expired_snapshot_notified = False
        coordinator._refresh_started_after_failure = True
        coordinator.async_update_listeners = Mock()
        _FrozenDateTime.fixed_now = datetime(
            2026, 4, 13, 0, 5, tzinfo=PARIS_TIME_ZONE
        )

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            coordinator._async_refresh_finished()
            coordinator._async_refresh_finished()

        coordinator.async_update_listeners.assert_called_once_with()
        self.assertTrue(coordinator._expired_snapshot_notified)

    def test_first_failure_lets_home_assistant_notify_expired_snapshot(self) -> None:
        """The hook must not duplicate HA's notification on a first failure."""
        coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        coordinator.data = _calendar("BLUE", "RED")
        coordinator.last_update_success = False
        coordinator._expired_snapshot_notified = False
        coordinator._refresh_started_after_failure = False
        coordinator.async_update_listeners = Mock()
        _FrozenDateTime.fixed_now = datetime(
            2026, 4, 13, 0, 5, tzinfo=PARIS_TIME_ZONE
        )

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            coordinator._async_refresh_finished()

        coordinator.async_update_listeners.assert_not_called()
        self.assertTrue(coordinator._expired_snapshot_notified)

    def test_failure_with_current_snapshot_does_not_notify_listeners(self) -> None:
        """A same-day snapshot should remain available without a forced write."""
        coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        coordinator.data = _calendar("BLUE", "RED")
        coordinator.last_update_success = False
        coordinator._expired_snapshot_notified = False
        coordinator._refresh_started_after_failure = True
        coordinator.async_update_listeners = Mock()
        _FrozenDateTime.fixed_now = datetime(
            2026, 4, 12, 23, 55, tzinfo=PARIS_TIME_ZONE
        )

        with patch("custom_components.edf_tempo.coordinator.datetime", _FrozenDateTime):
            coordinator._async_refresh_finished()

        coordinator.async_update_listeners.assert_not_called()
        self.assertFalse(coordinator._expired_snapshot_notified)

    def test_successful_refresh_resets_expiration_notification_guard(self) -> None:
        """A recovered coordinator should prepare the guard for the next day."""
        coordinator = object.__new__(EdfTempoDataUpdateCoordinator)
        coordinator.data = _calendar("BLUE", "RED")
        coordinator.last_update_success = True
        coordinator._expired_snapshot_notified = True
        coordinator._refresh_started_after_failure = True
        coordinator.async_update_listeners = Mock()

        coordinator._async_refresh_finished()

        coordinator.async_update_listeners.assert_not_called()
        self.assertFalse(coordinator._expired_snapshot_notified)


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
