"""Unit tests for the EDF Tempo websocket handlers."""

from __future__ import annotations

import asyncio
import unittest

from tests._ha_stubs import install

install()

from custom_components.edf_tempo.api import EdfTempoApiError, EdfTempoAuthError
from custom_components.edf_tempo.const import DATA_COORDINATOR, DOMAIN, MIN_SEASON_START_YEAR
from custom_components.edf_tempo.coordinator import EdfTempoDataUpdateCoordinator
from custom_components.edf_tempo.season_cache import build_cache_entry
from custom_components.edf_tempo.websocket_api import ws_get_season_calendar


class _Connection:
    """Capture websocket responses."""

    def __init__(self) -> None:
        self.errors: list[tuple] = []
        self.results: list[tuple] = []

    def send_error(self, *args) -> None:
        self.errors.append(args)

    def send_result(self, *args) -> None:
        self.results.append(args)


class _Coordinator(EdfTempoDataUpdateCoordinator):
    """Minimal coordinator used to satisfy isinstance checks."""

    def __init__(self) -> None:
        pass

    @property
    def current_season_start_year(self) -> int:  # type: ignore[override]
        return 2025

    async def async_get_season_entry(self, season_start_year: int):
        return build_cache_entry(
            "2025-09-01",
            "2026-08-31",
            {
                "2025-09-01": "BLUE",
                "2025-09-02": "WHITE",
            },
        )


class _AuthFailCoordinator(_Coordinator):
    async def async_get_season_entry(self, season_start_year: int):
        raise EdfTempoAuthError("bad auth")


class _ApiFailCoordinator(_Coordinator):
    async def async_get_season_entry(self, season_start_year: int):
        raise EdfTempoApiError("upstream unavailable")


class _Hass:
    """Minimal hass object."""

    def __init__(self, data) -> None:
        self.data = data


class EdfTempoWebsocketTests(unittest.TestCase):
    """Validate websocket success and error branches."""

    def test_ws_returns_not_loaded_when_domain_missing(self) -> None:
        """The websocket should fail cleanly when the integration is not loaded."""
        hass = _Hass({})
        connection = _Connection()

        asyncio.run(ws_get_season_calendar(hass, connection, {"id": 1, "season_start_year": 2025}))

        self.assertEqual(connection.errors, [(1, "not_loaded", "EDF Tempo is not loaded")])

    def test_ws_returns_invalid_season_when_out_of_range(self) -> None:
        """Out-of-range seasons should be rejected."""
        coordinator = _Coordinator()
        hass = _Hass({DOMAIN: {DATA_COORDINATOR: coordinator}})
        connection = _Connection()

        asyncio.run(
            ws_get_season_calendar(
                hass,
                connection,
                {"id": 2, "season_start_year": MIN_SEASON_START_YEAR - 1},
            )
        )

        self.assertEqual(connection.errors, [(2, "invalid_season", "Season out of allowed range")])

    def test_ws_returns_season_payload(self) -> None:
        """A valid season request should return the cached/fetched day colors."""
        coordinator = _Coordinator()
        hass = _Hass({DOMAIN: {DATA_COORDINATOR: coordinator}})
        connection = _Connection()

        asyncio.run(ws_get_season_calendar(hass, connection, {"id": 3, "season_start_year": 2025}))

        self.assertEqual(connection.errors, [])
        self.assertEqual(len(connection.results), 1)
        message_id, payload = connection.results[0]
        self.assertEqual(message_id, 3)
        self.assertEqual(payload["season_start_year"], 2025)
        self.assertEqual(payload["current_season_start_year"], 2025)
        self.assertEqual(payload["season_start"], "2025-09-01")
        self.assertEqual(payload["season_end"], "2026-08-31")
        self.assertEqual(payload["day_colors"]["2025-09-01"], "BLUE")

    def test_ws_returns_auth_failed_when_backend_auth_breaks(self) -> None:
        """Auth failures should be sent as websocket errors."""
        coordinator = _AuthFailCoordinator()
        hass = _Hass({DOMAIN: {DATA_COORDINATOR: coordinator}})
        connection = _Connection()

        asyncio.run(ws_get_season_calendar(hass, connection, {"id": 4, "season_start_year": 2025}))

        self.assertEqual(connection.errors, [(4, "auth_failed", "EDF Tempo authentication failed")])

    def test_ws_returns_fetch_failed_when_backend_request_breaks(self) -> None:
        """API failures should be sent as websocket errors."""
        coordinator = _ApiFailCoordinator()
        hass = _Hass({DOMAIN: {DATA_COORDINATOR: coordinator}})
        connection = _Connection()

        asyncio.run(ws_get_season_calendar(hass, connection, {"id": 5, "season_start_year": 2025}))

        self.assertEqual(connection.errors, [(5, "fetch_failed", "upstream unavailable")])


if __name__ == "__main__":
    unittest.main()
