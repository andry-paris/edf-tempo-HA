"""Tests for integration translations."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

INTEGRATION_DIR = Path(__file__).parents[1] / "custom_components" / "edf_tempo"


def _load_catalog(path: Path) -> dict:
    """Load a translation catalog."""
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten(value: dict, prefix: str = "") -> dict[str, str]:
    """Flatten a nested translation catalog into dotted keys."""
    flattened: dict[str, str] = {}
    for key, item in value.items():
        dotted_key = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            flattened.update(_flatten(item, dotted_key))
        else:
            flattened[dotted_key] = item
    return flattened


class EdfTempoTranslationTests(unittest.TestCase):
    """Ensure the English and French catalogs stay complete and localized."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load all translation catalogs once."""
        cls.source = _flatten(_load_catalog(INTEGRATION_DIR / "strings.json"))
        cls.english = _flatten(
            _load_catalog(INTEGRATION_DIR / "translations" / "en.json")
        )
        cls.french = _flatten(
            _load_catalog(INTEGRATION_DIR / "translations" / "fr.json")
        )

    def test_catalogs_have_exactly_the_same_keys(self) -> None:
        """Every source string must exist in both supported languages."""
        self.assertEqual(set(self.english), set(self.source))
        self.assertEqual(set(self.french), set(self.source))

    def test_english_catalog_matches_home_assistant_source_strings(self) -> None:
        """The explicit English catalog must not drift from strings.json."""
        self.assertEqual(self.english, self.source)

    def test_french_catalog_does_not_reuse_english_ui_text(self) -> None:
        """Only the EDF Tempo proper name may be identical in both languages."""
        identical_values = {
            key for key, value in self.english.items() if self.french[key] == value
        }
        self.assertEqual(identical_values, {"title"})

    def test_all_translation_values_are_non_empty_strings(self) -> None:
        """No supported catalog may contain an empty or non-string value."""
        for language, catalog in (("en", self.english), ("fr", self.french)):
            for key, value in catalog.items():
                with self.subTest(language=language, key=key):
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip())

    def test_french_sensor_names_are_localized(self) -> None:
        """French UI labels should be French while entity IDs remain code-defined."""
        expected_names = {
            "entity.sensor.today.name": "Aujourd'hui",
            "entity.sensor.tomorrow.name": "Demain",
            "entity.sensor.season_summary.name": "Synthèse de la saison",
            "entity.sensor.remaining_red_days.name": "Jours rouges restants",
            "entity.sensor.remaining_white_days.name": "Jours blancs restants",
            "entity.sensor.remaining_blue_days.name": "Jours bleus restants",
        }
        for key, expected in expected_names.items():
            with self.subTest(key=key):
                self.assertEqual(self.french[key], expected)

    def test_french_config_fields_are_localized(self) -> None:
        """Credential labels must be French throughout every config flow step."""
        for step in ("user", "reauth_confirm", "reconfigure"):
            with self.subTest(step=step):
                prefix = f"config.step.{step}.data"
                self.assertEqual(
                    self.french[f"{prefix}.client_id"], "Identifiant client"
                )
                self.assertEqual(
                    self.french[f"{prefix}.client_secret"], "Secret client"
                )

    def test_enum_states_are_localized_in_both_languages(self) -> None:
        """Tempo color states must have complete English and French labels."""
        expected = {
            "blue": ("Blue", "Bleu"),
            "white": ("White", "Blanc"),
            "red": ("Red", "Rouge"),
            "unknown": ("Unknown", "Inconnue"),
        }
        for sensor in ("today", "tomorrow"):
            for state, (english, french) in expected.items():
                key = f"entity.sensor.{sensor}.state.{state}"
                with self.subTest(sensor=sensor, state=state):
                    self.assertEqual(self.english[key], english)
                    self.assertEqual(self.french[key], french)


if __name__ == "__main__":
    unittest.main()
