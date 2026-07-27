"""Unit tests for EDF Tempo season cache helpers."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import unittest
from unittest.mock import AsyncMock

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

    def test_async_load_keeps_valid_entries_and_ignores_invalid_entries(self) -> None:
        """Malformed or obsolete entries should become cache misses."""
        valid_entry = build_cache_entry(
            "2025-09-01",
            "2026-08-31",
            {"2025-09-01": "BLUE", "2025-09-02": "RED"},
        )
        valid_payload = {
            "summary": asdict(valid_entry.summary),
            "day_colors": dict(valid_entry.day_colors),
        }
        invalid_payloads = {
            "missing_summary_field": {
                "summary": {
                    key: value
                    for key, value in valid_payload["summary"].items()
                    if key != "red_total"
                },
                "day_colors": valid_payload["day_colors"],
            },
            "invalid_number": {
                "summary": {**valid_payload["summary"], "total_placed": "2"},
                "day_colors": valid_payload["day_colors"],
            },
            "invalid_date": {
                "summary": {**valid_payload["summary"], "season_end": "invalid"},
                "day_colors": valid_payload["day_colors"],
            },
            "invalid_color": {
                "summary": valid_payload["summary"],
                "day_colors": {"2025-09-01": "PURPLE"},
            },
            "inconsistent_summary": {
                "summary": {**valid_payload["summary"], "blue_days": 99},
                "day_colors": valid_payload["day_colors"],
            },
            "truncated_entry": {"summary": valid_payload["summary"]},
        }

        cache = EdfTempoSeasonCache(object())
        cache._store.saved_data = {"2025-09-01": valid_payload}
        asyncio.run(cache.async_load())
        self.assertEqual(cache.get("2025-09-01"), valid_entry)

        for name, invalid_payload in invalid_payloads.items():
            with self.subTest(name=name):
                cache = EdfTempoSeasonCache(object())
                cache._store.saved_data = {"2025-09-01": invalid_payload}

                asyncio.run(cache.async_load())

                self.assertIsNone(cache.get("2025-09-01"))

    def test_async_load_ignores_invalid_root_and_read_errors(self) -> None:
        """An unreadable or non-object storage document should start empty."""
        cache = EdfTempoSeasonCache(object())
        cache._store.saved_data = ["old", "format"]
        asyncio.run(cache.async_load())
        self.assertIsNone(cache.get("2025-09-01"))

        cache._store.async_load = AsyncMock(side_effect=ValueError("truncated JSON"))
        asyncio.run(cache.async_load())
        self.assertIsNone(cache.get("2025-09-01"))

    def test_get_handles_malformed_in_memory_payload(self) -> None:
        """Defensive reads should never raise for an invalid cached entry."""
        cache = EdfTempoSeasonCache(object())
        cache._data["2025-09-01"] = {"summary": {}, "day_colors": {}}

        self.assertIsNone(cache.get("2025-09-01"))

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
