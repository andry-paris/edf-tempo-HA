"""Unit tests for automatic EDF Tempo card registration."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
import unittest

from tests._ha_stubs import install

install()

from custom_components.edf_tempo.const import CARD_URL_PATH, LEGACY_CARD_URL_PATH
from custom_components.edf_tempo.frontend import (
    CARD_RESOURCE_URL,
    async_register_frontend,
    async_remove_frontend_resource,
)


class _Http:
    def __init__(self) -> None:
        self.paths = []

    async def async_register_static_paths(self, paths) -> None:
        self.paths.extend(paths)


class _Resources:
    def __init__(self, items=None) -> None:
        self.items = list(items or [])
        self.created = []
        self.updated = []
        self.deleted = []

    async def async_get_info(self):
        return {"resources": len(self.items)}

    def async_items(self):
        return self.items

    async def async_create_item(self, item):
        self.created.append(item)

    async def async_update_item(self, item_id, item):
        self.updated.append((item_id, item))

    async def async_delete_item(self, item_id):
        self.deleted.append(item_id)
        self.items = [item for item in self.items if item["id"] != item_id]


class _Hass:
    def __init__(self, lovelace_data=None) -> None:
        self.http = _Http()
        self.data = {}
        if lovelace_data is not None:
            self.data["lovelace"] = lovelace_data


class EdfTempoFrontendTests(unittest.TestCase):
    """Validate card serving and Lovelace resource management."""

    def test_creates_resource_in_storage_mode(self) -> None:
        resources = _Resources()
        hass = _Hass(SimpleNamespace(resource_mode="storage", resources=resources))

        asyncio.run(async_register_frontend(hass))

        self.assertEqual(hass.http.paths[0].url_path, CARD_URL_PATH)
        self.assertTrue(hass.http.paths[0].path.endswith("/edf_tempo/card.js"))
        self.assertFalse(hass.http.paths[0].cache_headers)
        self.assertEqual(
            resources.created,
            [{"res_type": "module", "url": CARD_RESOURCE_URL}],
        )

    def test_updates_previous_automatic_resource(self) -> None:
        resources = _Resources(
            [{"id": "card", "type": "module", "url": f"{CARD_URL_PATH}?v=old"}]
        )
        hass = _Hass(SimpleNamespace(resource_mode="storage", resources=resources))

        asyncio.run(async_register_frontend(hass))

        self.assertEqual(
            resources.updated,
            [("card", {"res_type": "module", "url": CARD_RESOURCE_URL})],
        )
        self.assertEqual(resources.created, [])

    def test_migrates_legacy_manual_resource(self) -> None:
        resources = _Resources(
            [{"id": "legacy", "type": "module", "url": LEGACY_CARD_URL_PATH}]
        )
        hass = _Hass(SimpleNamespace(resource_mode="storage", resources=resources))

        asyncio.run(async_register_frontend(hass))

        self.assertEqual(
            resources.updated,
            [("legacy", {"res_type": "module", "url": CARD_RESOURCE_URL})],
        )

    def test_yaml_mode_only_exposes_static_file(self) -> None:
        resources = _Resources()
        hass = _Hass(SimpleNamespace(resource_mode="yaml", resources=resources))

        asyncio.run(async_register_frontend(hass))

        self.assertEqual(hass.http.paths[0].url_path, CARD_URL_PATH)
        self.assertEqual(resources.created, [])
        self.assertEqual(resources.updated, [])

    def test_removes_current_and_legacy_resources_only(self) -> None:
        """Final removal should clean integration resources without touching others."""
        resources = _Resources(
            [
                {"id": "current", "type": "module", "url": CARD_RESOURCE_URL},
                {"id": "legacy", "type": "module", "url": LEGACY_CARD_URL_PATH},
                {"id": "other", "type": "module", "url": "/local/other-card.js"},
            ]
        )
        hass = _Hass(SimpleNamespace(resource_mode="storage", resources=resources))

        asyncio.run(async_remove_frontend_resource(hass))

        self.assertEqual(resources.deleted, ["current", "legacy"])
        self.assertEqual([item["id"] for item in resources.items], ["other"])

    def test_remove_does_nothing_outside_storage_mode(self) -> None:
        """YAML resources remain manually managed by the user."""
        resources = _Resources(
            [{"id": "card", "type": "module", "url": CARD_RESOURCE_URL}]
        )
        hass = _Hass(SimpleNamespace(resource_mode="yaml", resources=resources))

        asyncio.run(async_remove_frontend_resource(hass))

        self.assertEqual(resources.deleted, [])


if __name__ == "__main__":
    unittest.main()
