"""Run the shipped blueprints through Home Assistant's automation engine."""

from pathlib import Path

import pytest

from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_mock_service, mock_restore_cache

BLUEPRINT_DIR = Path(__file__).parents[1] / "blueprints" / "automation" / "edf_tempo"
SENSOR = "sensor.test_tempo_tomorrow"


async def _setup_alert(hass, language="fr", inputs=None):
    filename = "tomorrow_color_alert_en.yaml" if language == "en" else "tomorrow_color_alert.yaml"
    destination = Path(hass.config.path("blueprints", "automation", "edf_tempo", filename))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text((BLUEPRINT_DIR / filename).read_text())
    await hass.config.async_update(time_zone="Europe/Paris")
    assert await async_setup_component(hass, "automation", {"automation": [{
        "id": "tempo_alert_test", "alias": "Tempo alert test",
        "use_blueprint": {"path": f"edf_tempo/{filename}",
                          "input": {"tomorrow_entity": SENSOR, **(inputs or {})}},
    }]})
    await hass.async_block_till_done()
    assert hass.states.get("automation.tempo_alert_test") is not None


@pytest.mark.parametrize("language", ["fr", "en"])
async def test_alert_once_per_day_with_recovery_and_next_day(hass: HomeAssistant, freezer, language):
    freezer.move_to("2026-09-21T10:00:00+00:00")
    calls = async_mock_service(hass, "persistent_notification", "create")
    await _setup_alert(hass, language)
    for state, attributes in [
        ("unknown", {"date": "2026-09-22"}),
        ("blue", {"date": "2026-09-22"}),
        ("red", {"date": "2026-09-21"}),  # Yesterday's retained tomorrow data.
        ("red", {}),
    ]:
        hass.states.async_set(SENSOR, state, attributes)
        await hass.async_block_till_done()
    assert not calls
    hass.states.async_set(SENSOR, "red", {"date": "2026-09-22"})
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert "2026-09-22" in calls[0].data["message"]
    assert ("rouge" if language == "fr" else "red") in calls[0].data["message"]
    for state in ["red", "unavailable", "red"]:
        hass.states.async_set(SENSOR, state, {"date": "2026-09-22", "fetched_at": "updated"})
        await hass.async_block_till_done()
    assert len(calls) == 1
    freezer.move_to("2026-09-22T10:00:00+00:00")
    # Same color on consecutive days must still produce a new alert.
    hass.states.async_set(SENSOR, "red", {"date": "2026-09-23"})
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_restored_last_trigger_prevents_duplicate_after_restart(hass: HomeAssistant, freezer):
    freezer.move_to("2026-09-21T12:00:00+00:00")
    mock_restore_cache(hass, [State("automation.tempo_alert_test", "on", {
        "last_triggered": "2026-09-21T10:00:00+00:00",
    })])
    calls = async_mock_service(hass, "persistent_notification", "create")
    await _setup_alert(hass)
    hass.states.async_set(SENSOR, "red", {"date": "2026-09-22"})
    await hass.async_block_till_done()
    assert not calls


async def test_selected_colors_and_custom_action(hass: HomeAssistant, freezer):
    freezer.move_to("2026-09-21T10:00:00+00:00")
    calls = async_mock_service(hass, "test", "alert")
    await _setup_alert(hass, inputs={
        "alert_colors": ["white"],
        "alert_actions": [{"action": "test.alert", "data": {"color": "{{ tempo_color }}"}}],
    })
    hass.states.async_set(SENSOR, "red", {"date": "2026-09-22"})
    await hass.async_block_till_done()
    assert not calls
    hass.states.async_set(SENSOR, "white", {"date": "2026-09-22"})
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["color"] == "white"


@pytest.mark.parametrize("already_alerted", [False, True])
async def test_startup_with_color_already_available(hass: HomeAssistant, freezer, already_alerted):
    freezer.move_to("2026-09-21T12:00:00+00:00")
    hass.state = CoreState.not_running
    if already_alerted:
        mock_restore_cache(hass, [State("automation.tempo_alert_test", "on", {
            "last_triggered": "2026-09-21T10:00:00+00:00",
        })])
    calls = async_mock_service(hass, "persistent_notification", "create")
    hass.states.async_set(SENSOR, "red", {"date": "2026-09-22"})
    await _setup_alert(hass)
    await hass.async_start()
    await hass.async_block_till_done()
    assert len(calls) == (0 if already_alerted else 1)
