"""Unit tests for EDF Tempo sensor entities."""

from __future__ import annotations

from datetime import datetime
import unittest
from unittest.mock import patch

from tests._ha_stubs import install

install()

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry

from custom_components.edf_tempo.api import (
    TempoCalendarData,
    TempoDayData,
    TempoSeasonSummaryData,
)
from custom_components.edf_tempo.const import PARIS_TIME_ZONE
from custom_components.edf_tempo.sensor import (
    EdfTempoSensor,
    SENSORS,
    TEMPO_COLOR_OPTIONS,
)


class _Coordinator:
    def __init__(
        self,
        today_code: str | None,
        tomorrow_code: str | None,
        *,
        today_date: str = "2026-07-26",
    ) -> None:
        self.last_update_success = True
        self.data = TempoCalendarData(
            today=TempoDayData(today_date, today_code, None, False, None),
            tomorrow=TempoDayData("2026-07-27", tomorrow_code, None, False, None),
            season_summary=TempoSeasonSummaryData(
                season_start="2025-09-01",
                season_end="2026-08-31",
                total_placed=365,
                blue_days=300,
                white_days=43,
                red_days=22,
            ),
            fetched_at="2026-07-26T10:40:00+02:00",
        )


class _FrozenDateTime(datetime):
    """Datetime subclass whose current time can be pinned by tests."""

    fixed_now: datetime

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.fixed_now
        return cls.fixed_now.astimezone(tz)


class EdfTempoSensorTests(unittest.TestCase):
    """Validate enum sensor states and metadata."""

    def _sensor(self, key: str, coordinator: _Coordinator) -> EdfTempoSensor:
        description = next(item for item in SENSORS if item.key == key)
        return EdfTempoSensor(coordinator, ConfigEntry(), description)

    def test_color_sensors_are_enums_with_fixed_options(self) -> None:
        """Today and tomorrow expose the same fixed enum options."""
        for description in SENSORS[:2]:
            self.assertEqual(description.device_class, SensorDeviceClass.ENUM)
            self.assertEqual(description.options, TEMPO_COLOR_OPTIONS)

    def test_device_identifies_the_community_integration_and_rte_source(self) -> None:
        """Device metadata should not identify EDF as the manufacturer."""
        device_info = self._sensor("today", _Coordinator("BLUE", "RED")).device_info
        self.assertEqual(device_info["manufacturer"], "Community integration")
        self.assertEqual(device_info["model"], "Tempo data source: RTE")

    def test_color_codes_are_normalized_to_lowercase(self) -> None:
        """Raw API color codes become canonical lowercase enum states."""
        coordinator = _Coordinator("BLUE", "RED")
        self.assertEqual(self._sensor("today", coordinator).native_value, "blue")
        self.assertEqual(self._sensor("tomorrow", coordinator).native_value, "red")

    def test_tomorrow_exposes_last_successful_fetch_even_during_failure(self) -> None:
        """The timestamp describes the retained snapshot, not failed attempts."""
        coordinator = _Coordinator("BLUE", None)
        sensor = self._sensor("tomorrow", coordinator)
        self.assertEqual(sensor.extra_state_attributes["fetched_at"], coordinator.data.fetched_at)
        self.assertIsNone(sensor.extra_state_attributes["updated_date"])
        coordinator.last_update_success = False
        self.assertEqual(sensor.extra_state_attributes["fetched_at"], coordinator.data.fetched_at)
        self.assertNotIn("fetched_at", self._sensor("today", coordinator).extra_state_attributes)

    def test_current_snapshot_is_available_after_success(self) -> None:
        """A successful snapshot for the current Paris date is available."""
        coordinator = _Coordinator("BLUE", "RED")
        _FrozenDateTime.fixed_now = datetime(
            2026, 7, 26, 18, 0, tzinfo=PARIS_TIME_ZONE
        )

        with patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime):
            self.assertTrue(self._sensor("today", coordinator).available)

    def test_current_snapshot_stays_available_during_same_day_failure(self) -> None:
        """A transient failure does not hide data that is still valid today."""
        coordinator = _Coordinator("BLUE", "RED")
        coordinator.last_update_success = False
        _FrozenDateTime.fixed_now = datetime(
            2026, 7, 26, 23, 59, tzinfo=PARIS_TIME_ZONE
        )

        with patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime):
            self.assertTrue(self._sensor("today", coordinator).available)

    def test_previous_day_snapshot_becomes_unavailable_after_midnight(self) -> None:
        """A prolonged failure must not expose yesterday's snapshot as current."""
        coordinator = _Coordinator("BLUE", "RED")
        coordinator.last_update_success = False
        _FrozenDateTime.fixed_now = datetime(
            2026, 7, 27, 0, 0, tzinfo=PARIS_TIME_ZONE
        )

        with patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime):
            self.assertFalse(self._sensor("today", coordinator).available)

    def test_sensor_without_an_initial_snapshot_is_unavailable(self) -> None:
        """No entity is available before the first successful data refresh."""
        coordinator = _Coordinator("BLUE", "RED")
        coordinator.data = None
        coordinator.last_update_success = False
        _FrozenDateTime.fixed_now = datetime(
            2026, 7, 26, 12, 0, tzinfo=PARIS_TIME_ZONE
        )

        with patch("custom_components.edf_tempo.sensor.datetime", _FrozenDateTime):
            self.assertFalse(self._sensor("today", coordinator).available)

    def test_entity_id_is_suggested_but_not_forced(self) -> None:
        """Home Assistant should use a language-independent suggested entity ID."""
        sensor = self._sensor("today", _Coordinator("BLUE", "RED"))
        self.assertEqual(sensor.suggested_object_id, "today")
        self.assertTrue(sensor._attr_has_entity_name)
        self.assertIsNone(getattr(sensor, "entity_id", None))

    def test_missing_or_unrecognized_color_is_unknown(self) -> None:
        """Missing and unexpected API colors use the enum's unknown option."""
        coordinator = _Coordinator(None, "PURPLE")
        self.assertEqual(self._sensor("today", coordinator).native_value, "unknown")
        self.assertEqual(self._sensor("tomorrow", coordinator).native_value, "unknown")

    def test_season_summary_remains_numeric(self) -> None:
        """The non-enum season sensor returns its numeric total."""
        sensor = self._sensor("season_summary", _Coordinator("WHITE", None))
        self.assertEqual(sensor.native_value, "365")

    def test_remaining_day_sensors_use_season_allowances(self) -> None:
        """Remaining sensors subtract placed days from each color allowance."""
        coordinator = _Coordinator("WHITE", None)
        coordinator.data = TempoCalendarData(
            today=coordinator.data.today,
            tomorrow=coordinator.data.tomorrow,
            season_summary=TempoSeasonSummaryData(
                season_start="2025-09-01",
                season_end="2026-08-31",
                total_placed=104,
                blue_days=80,
                white_days=18,
                red_days=6,
            ),
            fetched_at=coordinator.data.fetched_at,
        )

        self.assertEqual(self._sensor("remaining_red_days", coordinator).native_value, 16)
        self.assertEqual(self._sensor("remaining_white_days", coordinator).native_value, 25)
        self.assertEqual(self._sensor("remaining_blue_days", coordinator).native_value, 220)

    def test_remaining_days_are_clamped_at_zero(self) -> None:
        """Unexpected excess source counts never produce negative remaining days."""
        coordinator = _Coordinator("RED", None)
        coordinator.data = TempoCalendarData(
            today=coordinator.data.today,
            tomorrow=coordinator.data.tomorrow,
            season_summary=TempoSeasonSummaryData(
                season_start="2025-09-01",
                season_end="2026-08-31",
                total_placed=366,
                blue_days=300,
                white_days=43,
                red_days=23,
            ),
            fetched_at=coordinator.data.fetched_at,
        )

        sensor = self._sensor("remaining_red_days", coordinator)
        self.assertEqual(sensor.native_value, 0)
        self.assertEqual(sensor.extra_state_attributes["used_days"], 23)
        self.assertEqual(sensor.extra_state_attributes["total_days"], 22)


if __name__ == "__main__":
    unittest.main()
