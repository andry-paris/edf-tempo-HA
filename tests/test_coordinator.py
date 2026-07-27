"""Unit tests for EDF Tempo coordinator scheduling logic."""

from __future__ import annotations

from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from tests._ha_stubs import install

install()

from custom_components.edf_tempo.api import TempoCalendarData, TempoDayData, TempoSeasonSummaryData
from custom_components.edf_tempo.const import PARIS_TIME_ZONE
from custom_components.edf_tempo.coordinator import EdfTempoDataUpdateCoordinator


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


if __name__ == "__main__":
    unittest.main()
