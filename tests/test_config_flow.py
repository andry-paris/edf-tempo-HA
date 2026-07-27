"""Unit tests for the EDF Tempo config flow."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch
import unittest

from tests._ha_stubs import install

install()

from custom_components.edf_tempo.api import EdfTempoApiError, EdfTempoAuthError
from custom_components.edf_tempo.config_flow import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DEFAULT_NAME,
    EdfTempoConfigFlow,
)


class EdfTempoConfigFlowTests(unittest.TestCase):
    """Validate config flow behavior and error mapping."""

    def setUp(self) -> None:
        self.flow = object.__new__(EdfTempoConfigFlow)
        self.flow.hass = object()
        self.flow.async_show_form = lambda **kwargs: {"type": "form", **kwargs}
        self.flow.async_create_entry = lambda **kwargs: {"type": "create_entry", **kwargs}
        self.flow.async_update_reload_and_abort = (
            lambda entry, **kwargs: {"type": "abort", "entry": entry, **kwargs}
        )
        self.flow._get_reauth_entry = lambda: {"id": "reauth-entry"}
        self.flow._get_reconfigure_entry = lambda: type(
            "Entry",
            (),
            {"data": {CONF_CLIENT_ID: "old_id", CONF_CLIENT_SECRET: "old_secret"}},
        )()
        self.flow._abort_if_unique_id_configured = lambda: None
        self.flow._abort_if_unique_id_mismatch = lambda: None
        self.flow.async_set_unique_id = AsyncMock()

    def test_validate_input_returns_invalid_auth(self) -> None:
        """Auth errors should map to invalid_auth."""
        with patch(
            "custom_components.edf_tempo.config_flow.EdfTempoClient.async_validate_credentials",
            new=AsyncMock(side_effect=EdfTempoAuthError("bad creds")),
        ):
            result = asyncio.run(
                self.flow._async_validate_input(
                    {CONF_CLIENT_ID: "id", CONF_CLIENT_SECRET: "secret"}
                )
            )

        self.assertEqual(result, {"base": "invalid_auth"})

    def test_validate_input_returns_cannot_connect(self) -> None:
        """API errors should map to cannot_connect."""
        with patch(
            "custom_components.edf_tempo.config_flow.EdfTempoClient.async_validate_credentials",
            new=AsyncMock(side_effect=EdfTempoApiError("api down")),
        ):
            result = asyncio.run(
                self.flow._async_validate_input(
                    {CONF_CLIENT_ID: "id", CONF_CLIENT_SECRET: "secret"}
                )
            )

        self.assertEqual(result, {"base": "cannot_connect"})

    def test_user_step_creates_entry_when_validation_passes(self) -> None:
        """Valid credentials should create the config entry."""
        user_input = {CONF_CLIENT_ID: "id", CONF_CLIENT_SECRET: "secret"}
        self.flow._async_validate_input = AsyncMock(return_value={})

        result = asyncio.run(self.flow.async_step_user(user_input))

        self.assertEqual(
            result,
            {
                "type": "create_entry",
                "title": DEFAULT_NAME,
                "data": user_input,
            },
        )

    def test_user_step_returns_form_errors_when_validation_fails(self) -> None:
        """Validation errors should keep the user on the form."""
        self.flow._async_validate_input = AsyncMock(return_value={"base": "invalid_auth"})

        result = asyncio.run(
            self.flow.async_step_user(
                {CONF_CLIENT_ID: "id", CONF_CLIENT_SECRET: "secret"}
            )
        )

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "user")
        self.assertEqual(result["errors"], {"base": "invalid_auth"})


if __name__ == "__main__":
    unittest.main()
