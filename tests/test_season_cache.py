"""Unit tests for EDF Tempo season cache helpers."""

from __future__ import annotations

import asyncio
import unittest

from tests._ha_stubs import install

install()

from custom_components.edf_tempo.api import TempoDayData
from custom_components.edf_tempo.season_cache import EdfTempoSeasonCache, build_cache_entry


class EdfTempoSeasonCacheTests(unittest.TestCase):
    """Validate summary building and cache updates."""

    def test_build_cache_entry_counts_known_colors_only(self) -> None:
        """Only BLUE/WHITE/RED days should contribute to totals."""
        entry = build_cache_entry(
            "2025-09-01",
            "2026-08-31",
            {
                "2025-09-01": "blue",
                "2025-09-02": "WHITE",
                "2025-09-03": "RED",
                "2025-09-04": "UNKNOWN",
            },
        )

        self.assertEqual(entry.summary.total_placed, 3)
        self.assertEqual(entry.summary.blue_days, 1)
        self.assertEqual(entry.summary.white_days, 1)
        self.assertEqual(entry.summary.red_days, 1)
        self.assertEqual(entry.day_colors["2025-09-01"], "BLUE")
        self.assertNotIn("2025-09-04", entry.day_colors)

    def test_async_update_current_season_merges_today_and_tomorrow(self) -> None:
        """Fresh day values should update the persisted summary."""
        hass = object()
        cache = EdfTempoSeasonCache(hass)
        entry = build_cache_entry(
            "2025-09-01",
            "2026-08-31",
            {"2025-09-01": "BLUE"},
        )

        updated_entry = asyncio.run(
            cache.async_update_current_season(
                entry,
                TempoDayData(
                    date="2026-04-12",
                    color_code="WHITE",
                    display_color="White",
                    fallback=False,
                    updated_date="2026-04-12T00:00:00+02:00",
                ),
                TempoDayData(
                    date="2026-04-13",
                    color_code="RED",
                    display_color="Red",
                    fallback=False,
                    updated_date="2026-04-12T11:00:00+02:00",
                ),
            )
        )

        self.assertEqual(updated_entry.summary.total_placed, 3)
        self.assertEqual(updated_entry.summary.blue_days, 1)
        self.assertEqual(updated_entry.summary.white_days, 1)
        self.assertEqual(updated_entry.summary.red_days, 1)
        self.assertEqual(updated_entry.day_colors["2026-04-12"], "WHITE")
        self.assertEqual(updated_entry.day_colors["2026-04-13"], "RED")

    def test_async_update_current_season_ignores_out_of_range_day(self) -> None:
        """Days outside the target season should not alter the summary."""
        hass = object()
        cache = EdfTempoSeasonCache(hass)
        entry = build_cache_entry(
            "2025-09-01",
            "2026-08-31",
            {"2025-09-01": "BLUE"},
        )

        updated_entry = asyncio.run(
            cache.async_update_current_season(
                entry,
                TempoDayData(
                    date="2026-09-01",
                    color_code="RED",
                    display_color="Red",
                    fallback=False,
                    updated_date="2026-09-01T00:00:00+02:00",
                ),
                TempoDayData(
                    date="2026-09-02",
                    color_code=None,
                    display_color=None,
                    fallback=False,
                    updated_date=None,
                ),
            )
        )

        self.assertEqual(updated_entry.summary.total_placed, 1)
        self.assertEqual(updated_entry.day_colors, {"2025-09-01": "BLUE"})


if __name__ == "__main__":
    unittest.main()
