"""Tests for release metadata consistency."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
INTEGRATION_DIR = ROOT / "custom_components" / "edf_tempo"


class EdfTempoReleaseMetadataTests(unittest.TestCase):
    """Prevent incomplete or internally inconsistent release artifacts."""

    def test_version_is_consistent_across_release_files(self) -> None:
        """Manifest, Lovelace cache key and README must use one version."""
        manifest = json.loads(
            (INTEGRATION_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        version = manifest["version"]
        const_source = (INTEGRATION_DIR / "const.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        match = re.search(
            r'^INTEGRATION_VERSION = "([^"]+)"$', const_source, re.MULTILINE
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), version)
        self.assertIn(f"/edf_tempo/card.js?v={version}", readme)

    def test_hacs_and_home_assistant_metadata_are_complete(self) -> None:
        """Required HACS and Home Assistant release metadata must be present."""
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        manifest = json.loads(
            (INTEGRATION_DIR / "manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(hacs["name"], "EDF Tempo")
        self.assertEqual(hacs["country"], "FR")
        self.assertEqual(hacs["homeassistant"], "2025.1.0")
        for key in (
            "codeowners",
            "config_flow",
            "documentation",
            "integration_type",
            "iot_class",
            "issue_tracker",
            "version",
        ):
            with self.subTest(key=key):
                self.assertTrue(manifest.get(key))

    def test_public_release_assets_exist(self) -> None:
        """A release must contain its card, translations, icons and legal files."""
        required_paths = (
            ROOT / "LICENSE",
            ROOT / "NOTICE",
            ROOT / "README.md",
            ROOT / "brand" / "icon.png",
            ROOT / "brand" / "icon@2x.png",
            INTEGRATION_DIR / "brand" / "icon.png",
            INTEGRATION_DIR / "brand" / "icon@2x.png",
            INTEGRATION_DIR / "card.js",
            INTEGRATION_DIR / "strings.json",
            INTEGRATION_DIR / "translations" / "en.json",
            INTEGRATION_DIR / "translations" / "fr.json",
        )
        for path in required_paths:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
