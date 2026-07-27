"""Unit tests for EDF Tempo sensor entities."""

from __future__ import annotations

import unittest

from tests._ha_stubs import install

install()

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry

from custom_components.edf_tempo.api import (
    TempoCalendarData,
    TempoDayData,
    TempoSeasonSummaryData,
)
from custom_components.edf_tempo.sensor import (
    EdfTempoSensor,
    SENSORS,
    TEMPO_COLOR_OPTIONS,
)


class _Coordinator:
    def __init__(self, today_code: str | None, tomorrow_code: str | None) -> None:
        self.data = TempoCalendarData(
            today=TempoDayData("2026-07-26", today_code, None, False, None),
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

    def test_color_codes_are_normalized_to_lowercase(self) -> None:
        """Raw API color codes become canonical lowercase enum states."""
        coordinator = _Coordinator("BLUE", "RED")
        self.assertEqual(self._sensor("today", coordinator).native_value, "blue")
        self.assertEqual(self._sensor("tomorrow", coordinator).native_value, "red")

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
