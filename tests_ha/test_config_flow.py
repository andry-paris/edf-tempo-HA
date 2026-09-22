"""Configuration validation against mocked OAuth and Tempo HTTP endpoints."""

import asyncio
from unittest.mock import AsyncMock, patch

import aiohttp

import pytest

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse
from homeassistant.data_entry_flow import FlowResultType

from custom_components.edf_tempo.const import (
    API_BASE_URL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
    TEMPO_CALENDARS_PATH,
    TOKEN_URL,
)


@pytest.mark.parametrize(
    ("token_status", "tempo_status", "error"),
    [
        (200, 200, None),
        (401, 200, "invalid_auth"),
        (403, 200, "invalid_auth"),
        (200, 401, "invalid_auth"),
        (200, 403, "access_denied"),
        (200, 500, "cannot_connect"),
    ],
)
async def test_user_setup_validates_token_and_tempo_access(
    hass, aioclient_mock, token_status, tempo_status, error
):
    """Do not create an entry when OAuth succeeds but Tempo access fails."""
    aioclient_mock.post(
        TOKEN_URL,
        status=token_status,
        json={"access_token": "test-token", "expires_in": 7200},
    )
    aioclient_mock.get(
        f"{API_BASE_URL}{TEMPO_CALENDARS_PATH}",
        status=tempo_status,
        json={"tempo_like_calendars": []},
    )
    with patch(
        "custom_components.edf_tempo.async_setup_entry",
        new=AsyncMock(return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_CLIENT_ID: "test-id", CONF_CLIENT_SECRET: "test-secret"},
        )
        await hass.async_block_till_done()

    if error:
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error}
        assert not hass.config_entries.async_entries(DOMAIN)
    else:
        # An unpublished tomorrow does not block setup.
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert aioclient_mock.call_count == 2


@pytest.mark.parametrize("stage", ["token", "tempo"])
@pytest.mark.parametrize("error_type", [aiohttp.ClientConnectionError, asyncio.TimeoutError])
async def test_network_failure_returns_translatable_connection_error(
    hass, aioclient_mock, stage, error_type
):
    """Network failures at either endpoint must keep the form with cannot_connect."""
    if stage == "token":
        aioclient_mock.post(TOKEN_URL, exc=error_type())
    else:
        aioclient_mock.post(
            TOKEN_URL, json={"access_token": "test-token", "expires_in": 7200}
        )
        aioclient_mock.get(
            f"{API_BASE_URL}{TEMPO_CALENDARS_PATH}", exc=error_type()
        )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_CLIENT_ID: "test-id", CONF_CLIENT_SECRET: "test-secret"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("source", [SOURCE_REAUTH, SOURCE_RECONFIGURE])
@pytest.mark.parametrize("status,error", [(403, "access_denied"), (500, "cannot_connect")])
async def test_existing_credentials_survive_failed_access_check(
    hass, aioclient_mock, source, status, error
):
    """Failure during either edit flow leaves the stored credentials intact."""
    old = {CONF_CLIENT_ID: "old-id", CONF_CLIENT_SECRET: "old-secret"}
    new = {CONF_CLIENT_ID: "new-id", CONF_CLIENT_SECRET: "new-secret"}
    entry = MockConfigEntry(domain=DOMAIN, data=old, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    aioclient_mock.post(TOKEN_URL, json={"access_token": "test-token", "expires_in": 7200})
    aioclient_mock.get(f"{API_BASE_URL}{TEMPO_CALENDARS_PATH}", status=status, json={})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": entry.entry_id},
        data=old if source == SOURCE_REAUTH else None,
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], new)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert entry.data == old

    # Correcting the problem in the same form updates credentials only after success.
    aioclient_mock.clear_requests()
    aioclient_mock.post(TOKEN_URL, json={"access_token": "test-token", "expires_in": 7200})
    aioclient_mock.get(
        f"{API_BASE_URL}{TEMPO_CALENDARS_PATH}", json={"tempo_like_calendars": []}
    )
    with patch.object(hass.config_entries, "async_reload", new=AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], new)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == (
        "reauth_successful" if source == SOURCE_REAUTH else "reconfigure_successful"
    )
    assert entry.data == new


@pytest.mark.parametrize("first_status", [401, 403])
async def test_access_succeeds_after_token_refresh(hass, aioclient_mock, first_status):
    """A first authorization failure may recover with a fresh token."""
    aioclient_mock.post(TOKEN_URL, json={"access_token": "test-token", "expires_in": 7200})
    url = f"{API_BASE_URL}{TEMPO_CALENDARS_PATH}"
    aioclient_mock.get(url, side_effect=AsyncMock(side_effect=[
        AiohttpClientMockResponse("get", url, status=first_status, json={}),
        AiohttpClientMockResponse("get", url, json={"tempo_like_calendars": []}),
    ]))
    with patch("custom_components.edf_tempo.async_setup_entry", new=AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER},
            data={CONF_CLIENT_ID: "test-id", CONF_CLIENT_SECRET: "test-secret"},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert aioclient_mock.call_count == 4


@pytest.mark.parametrize("payload", [[], {"tempo_like_calendars": "invalid"}])
async def test_malformed_tempo_response_blocks_setup(hass, aioclient_mock, payload):
    """HTTP 200 must contain usable calendar structure to validate access."""
    aioclient_mock.post(TOKEN_URL, json={"access_token": "test-token", "expires_in": 7200})
    aioclient_mock.get(f"{API_BASE_URL}{TEMPO_CALENDARS_PATH}", json=payload)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER},
        data={CONF_CLIENT_ID: "test-id", CONF_CLIENT_SECRET: "test-secret"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert not hass.config_entries.async_entries(DOMAIN)
