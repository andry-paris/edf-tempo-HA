"""Unit tests for EDF Tempo API parsing logic."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from tests._ha_stubs import install

install()

from custom_components.edf_tempo.api import EdfTempoAccessError, EdfTempoApiError, EdfTempoAuthError, EdfTempoClient


class _TimeoutRequestContext:
    async def __aenter__(self):
        raise asyncio.TimeoutError()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _TimeoutSession:
    def post(self, *args, **kwargs):
        return _TimeoutRequestContext()

    def request(self, *args, **kwargs):
        return _TimeoutRequestContext()


class _JsonResponseContext:
    status = 200

    def __init__(self, payload=None, *, error=None) -> None:
        self._payload = payload
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, *, content_type=None):
        if self._error is not None:
            raise self._error
        return self._payload


class _JsonSession:
    def __init__(self, payload=None, *, error=None) -> None:
        self._payload = payload
        self._error = error

    def post(self, *args, **kwargs):
        return _JsonResponseContext(self._payload, error=self._error)

    def request(self, *args, **kwargs):
        return _JsonResponseContext(self._payload, error=self._error)


class EdfTempoApiParsingTests(unittest.TestCase):
    """Validate response parsing and date helpers."""

    def setUp(self) -> None:
        self.client = EdfTempoClient(session=None, client_id="id", client_secret="secret")

    def test_validation_checks_tempo_access_after_authentication(self) -> None:
        """An OAuth token alone must not validate configuration."""
        for token_status, api_status, expected_error in [
            (200, 200, None),
            (401, 200, EdfTempoAuthError),
            (403, 200, EdfTempoAuthError),
            (200, 401, EdfTempoAuthError),
            (200, 403, EdfTempoAccessError),
            (200, 500, EdfTempoApiError),
        ]:
            with self.subTest(token=token_status, api=api_status):
                token = _JsonResponseContext({"access_token": "test-token", "expires_in": 7200})
                token.status = token_status
                # Empty calendars are valid: tomorrow need not be published.
                calendar = _JsonResponseContext({"tempo_like_calendars": []})
                calendar.status = api_status
                async def body():
                    return "upstream error"
                calendar.text = body
                session = Mock()
                session.post.return_value = token
                session.request.return_value = calendar
                client = EdfTempoClient(session=session, client_id="id", client_secret="secret")
                if expected_error:
                    with self.assertRaises(expected_error) as raised:
                        asyncio.run(client.async_validate_access())
                    self.assertIs(type(raised.exception), expected_error)
                else:
                    asyncio.run(client.async_validate_access())
                if token_status != 200:
                    session.request.assert_not_called()
                else:
                    self.assertEqual(session.request.call_count, 2 if api_status in (401, 403) else 1)
                    # The successful path reuses its token for the calendar request.
                    self.assertEqual(session.post.call_count, 2 if api_status in (401, 403) else 1)

    def test_startup_credential_validation_only_requests_a_token(self) -> None:
        """Coordinator setup leaves the daily fetch to its normal first refresh."""
        session = Mock()
        session.post.return_value = _JsonResponseContext(
            {"access_token": "test-token", "expires_in": 7200}
        )
        client = EdfTempoClient(session=session, client_id="id", client_secret="secret")
        asyncio.run(client.async_validate_credentials())
        session.post.assert_called_once()
        session.request.assert_not_called()

    def test_http_errors_do_not_propagate_response_bodies(self) -> None:
        """Upstream error bodies must not reach logs or WebSocket errors."""
        for stage in ("token", "tempo"):
            with self.subTest(stage=stage):
                response = _JsonResponseContext()
                response.status = 500
                response.text = AsyncMock(return_value="sensitive-upstream-body")
                session = Mock()
                session.post.return_value = response
                session.request.return_value = response
                client = EdfTempoClient(session=session, client_id="id", client_secret="secret")
                request = (
                    client.async_validate_credentials() if stage == "token"
                    else client._async_request_json("GET", "https://example.test", headers={})
                )
                with self.assertRaises(EdfTempoApiError) as raised:
                    asyncio.run(request)
                self.assertIn("500", str(raised.exception))
                self.assertNotIn("sensitive-upstream-body", str(raised.exception))
                response.text.assert_not_awaited()

    def test_parse_day_value_maps_color_and_string_fallback(self) -> None:
        """A valid day payload should be normalized."""
        day = self.client._parse_day_value(
            {
                "start_date": "2026-04-12T00:00:00+02:00",
                "value": "blue",
                "fallback": "true",
                "updated_date": "2026-04-11T10:31:00+02:00",
            }
        )

        self.assertEqual(day.date, "2026-04-12")
        self.assertEqual(day.color_code, "BLUE")
        self.assertEqual(day.display_color, "Blue")
        self.assertTrue(day.fallback)
        self.assertEqual(day.updated_date, "2026-04-11T10:31:00+02:00")

    def test_parse_day_window_response_handles_missing_tomorrow(self) -> None:
        """Tomorrow should remain undefined when the API has not published it yet."""
        result = self.client._parse_day_window_response(
            {
                "tempo_like_calendars": [
                    {
                        "values": [
                            {
                                "start_date": "2026-04-12T00:00:00+02:00",
                                "value": "RED",
                                "fallback": False,
                                "updated_date": "2026-04-11T20:00:00+02:00",
                            }
                        ]
                    }
                ]
            },
            "2026-04-12",
            "2026-04-13",
        )

        self.assertEqual(result.today.color_code, "RED")
        self.assertEqual(result.today.display_color, "Red")
        self.assertEqual(result.tomorrow.date, "2026-04-13")
        self.assertIsNone(result.tomorrow.color_code)
        self.assertIsNone(result.tomorrow.display_color)
        self.assertFalse(result.tomorrow.fallback)

    def test_parse_values_by_date_rejects_invalid_shape(self) -> None:
        """Invalid payload shape should raise a client error."""
        with self.assertRaises(EdfTempoApiError):
            self.client._parse_values_by_date({"tempo_like_calendars": "invalid"})

    def test_get_current_season_bounds(self) -> None:
        """Season should switch on September 1st."""
        season_start, season_end = EdfTempoClient._get_current_season_bounds(
            __import__("datetime").datetime(2026, 4, 12)
        )
        self.assertEqual(str(season_start), "2025-09-01")
        self.assertEqual(str(season_end), "2026-08-31")

        season_start, season_end = EdfTempoClient._get_current_season_bounds(
            __import__("datetime").datetime(2026, 9, 1)
        )
        self.assertEqual(str(season_start), "2026-09-01")
        self.assertEqual(str(season_end), "2027-08-31")

    def test_access_token_timeout_is_reported_cleanly(self) -> None:
        """Timeouts during token fetch should raise a readable API error."""
        client = EdfTempoClient(session=_TimeoutSession(), client_id="id", client_secret="secret")

        with self.assertRaises(EdfTempoApiError) as context:
            asyncio.run(client._async_get_access_token(force_refresh=True))

        self.assertEqual(str(context.exception), "Token request timed out")

    def test_api_request_timeout_is_reported_cleanly(self) -> None:
        """Timeouts during API fetch should raise a readable API error."""
        client = EdfTempoClient(session=_TimeoutSession(), client_id="id", client_secret="secret")

        with self.assertRaises(EdfTempoApiError) as context:
            asyncio.run(
                client._async_request_json(
                    "GET",
                    "https://example.test",
                    headers={"Authorization": "Bearer token"},
                )
            )

        self.assertEqual(str(context.exception), "API request timed out")

    def test_access_token_invalid_json_is_reported_cleanly(self) -> None:
        """Invalid JSON in a successful token response should raise a client error."""
        client = EdfTempoClient(
            session=_JsonSession(error=ValueError("invalid JSON")),
            client_id="id",
            client_secret="secret",
        )

        with self.assertRaises(EdfTempoApiError) as context:
            asyncio.run(client._async_get_access_token(force_refresh=True))

        self.assertEqual(str(context.exception), "Token response contained invalid JSON")

    def test_access_token_rejects_non_object_json(self) -> None:
        """A token response must be a JSON object before fields are accessed."""
        client = EdfTempoClient(
            session=_JsonSession([{"access_token": "token"}]),
            client_id="id",
            client_secret="secret",
        )

        with self.assertRaises(EdfTempoApiError) as context:
            asyncio.run(client._async_get_access_token(force_refresh=True))

        self.assertEqual(str(context.exception), "Token response was not a JSON object")

    def test_api_request_invalid_json_is_reported_cleanly(self) -> None:
        """Invalid JSON in a successful API response should raise a client error."""
        client = EdfTempoClient(
            session=_JsonSession(error=ValueError("invalid JSON")),
            client_id="id",
            client_secret="secret",
        )

        with self.assertRaises(EdfTempoApiError) as context:
            asyncio.run(
                client._async_request_json(
                    "GET",
                    "https://example.test",
                    headers={"Authorization": "Bearer token"},
                )
            )

        self.assertEqual(str(context.exception), "API response contained invalid JSON")

    def test_api_request_rejects_non_object_json(self) -> None:
        """A successful API response must contain a JSON object."""
        client = EdfTempoClient(
            session=_JsonSession([]),
            client_id="id",
            client_secret="secret",
        )

        with self.assertRaises(EdfTempoApiError) as context:
            asyncio.run(
                client._async_request_json(
                    "GET",
                    "https://example.test",
                    headers={"Authorization": "Bearer token"},
                )
            )

        self.assertEqual(str(context.exception), "API response was not a JSON object")


if __name__ == "__main__":
    unittest.main()
