"""Unit tests for EDF Tempo diagnostics redaction."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import unittest

from tests._ha_stubs import install

install()

from custom_components.edf_tempo.api import TempoCalendarData, TempoDayData, TempoSeasonSummaryData
from custom_components.edf_tempo.const import DOMAIN
from custom_components.edf_tempo.diagnostics import REDACTED, async_get_config_entry_diagnostics


class _Entry:
    def __init__(self) -> None:
        self.entry_id = "entry-1"
        self.data = {"client_id": "abc", "client_secret": "secret"}


class _Client:
    def __init__(self) -> None:
        self._client_id = "abc"
        self._client_secret = "secret"
        self._access_token = "token-123"
        self._token_expires_at = datetime(2026, 4, 12, 12, 0, 0)


class _Cache:
    def __init__(self) -> None:
        self._data = {"2025-09-01": {}}


class _Coordinator:
    def __init__(self) -> None:
        self.client = _Client()
        self._season_cache = _Cache()
        self.current_season_start_year = 2025
        self.update_interval = timedelta(minutes=30)
        self.last_update_success = True
        self.data = TempoCalendarData(
            today=TempoDayData("2026-04-12", "BLUE", "Blue", False, "2026-04-12T00:00:00+02:00"),
            tomorrow=TempoDayData("2026-04-13", None, None, False, None),
            season_summary=TempoSeasonSummaryData(
                season_start="2025-09-01",
                season_end="2026-08-31",
                total_placed=100,
                blue_days=80,
                white_days=15,
                red_days=5,
            ),
            fetched_at="2026-04-12T10:40:00+02:00",
        )


class _Hass:
    def __init__(self) -> None:
        self.data = {DOMAIN: {"entry-1": _Coordinator()}}


class EdfTempoDiagnosticsTests(unittest.TestCase):
    """Validate diagnostics output and redaction."""

    def test_diagnostics_redacts_credentials_and_tokens(self) -> None:
        """Sensitive values should not be exposed."""
        diagnostics = asyncio.run(async_get_config_entry_diagnostics(_Hass(), _Entry()))

        self.assertEqual(diagnostics["entry"]["client_id"], REDACTED)
        self.assertEqual(diagnostics["entry"]["client_secret"], REDACTED)
        self.assertEqual(diagnostics["client"]["client_id"], REDACTED)
        self.assertEqual(diagnostics["client"]["client_secret"], REDACTED)
        self.assertEqual(diagnostics["client"]["access_token"], REDACTED)
        self.assertEqual(diagnostics["current_season_start_year"], 2025)
        self.assertEqual(diagnostics["season_cache_keys"], ["2025-09-01"])
        self.assertEqual(diagnostics["data"]["today"]["color_code"], "BLUE")


if __name__ == "__main__":
    unittest.main()
