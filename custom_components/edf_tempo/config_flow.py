"""Config flow for the EDF Tempo integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import EdfTempoApiError, EdfTempoAuthError, EdfTempoClient
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, DEFAULT_NAME, DOMAIN


CLIENT_SECRET_SELECTOR = TextSelector(
    TextSelectorConfig(
        type=TextSelectorType.PASSWORD,
        autocomplete="current-password",
    )
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): CLIENT_SECRET_SELECTOR,
    }
)


def _reconfigure_schema(client_id: str) -> vol.Schema:
    """Return a reconfiguration schema that never exposes the stored secret."""
    return vol.Schema(
        {
            vol.Required(CONF_CLIENT_ID, default=client_id): str,
            vol.Optional(CONF_CLIENT_SECRET, default=""): CLIENT_SECRET_SELECTOR,
        }
    )


class EdfTempoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EDF Tempo."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors = await self._async_validate_input(user_input)
        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauthentication."""
        await self.async_set_unique_id(DOMAIN)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauthentication confirmation step."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors = await self._async_validate_input(user_input)
        if errors:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates=user_input,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the existing entry."""
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=_reconfigure_schema(
                    reconfigure_entry.data[CONF_CLIENT_ID]
                ),
            )

        updated_data = dict(user_input)
        if updated_data.get(CONF_CLIENT_SECRET, "") == "":
            updated_data[CONF_CLIENT_SECRET] = reconfigure_entry.data[
                CONF_CLIENT_SECRET
            ]

        errors = await self._async_validate_input(updated_data)
        if errors:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=_reconfigure_schema(user_input[CONF_CLIENT_ID]),
                errors=errors,
            )

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_mismatch()

        return self.async_update_reload_and_abort(
            reconfigure_entry,
            data_updates=updated_data,
        )

    async def _async_validate_input(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate user input against the EDF Tempo API."""
        client = EdfTempoClient(
            session=async_get_clientsession(self.hass),
            client_id=data[CONF_CLIENT_ID],
            client_secret=data[CONF_CLIENT_SECRET],
        )

        try:
            await client.async_validate_credentials()
        except EdfTempoAuthError:
            return {"base": "invalid_auth"}
        except EdfTempoApiError:
            return {"base": "cannot_connect"}
        except Exception:
            return {"base": "unknown"}

        return {}
