"""The Karabiner rule generator bootstraps fresh profiles and preserves existing settings."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


GENERATOR = Path(__file__).resolve().parents[1] / "karabiner/.config/karabiner/generate-defy-rules.py"


def load_generator():
    specification = importlib.util.spec_from_file_location("karabiner_generator", GENERATOR)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class KarabinerRuleGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.generator = load_generator()
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_install_creates_karabiner_json_and_asset_on_a_fresh_mac(self):
        self.generator.install_karabiner_rules(str(self.home))

        configuration_path = self.home / ".config/karabiner/karabiner.json"
        asset_path = self.home / ".config/karabiner/assets/complex_modifications/dygma-linux-parity.json"
        self.assertTrue(configuration_path.is_file())
        self.assertTrue(asset_path.is_file())

        configuration = json.loads(configuration_path.read_text())
        self.assertEqual(configuration["global"], {"show_in_menu_bar": True})
        profile = configuration["profiles"][0]
        self.assertEqual(profile["name"], "Default profile")
        self.assertTrue(profile["selected"])
        self.assertEqual(len(profile["devices"]), 3)

        descriptions = [rule["description"] for rule in profile["complex_modifications"]["rules"]]
        self.assertIn("Defy: Super+Shift+S opens the macOS screenshot menu", descriptions)
        self.assertEqual(len(descriptions), 13)

    def test_install_preserves_existing_profile_fields(self):
        configuration_path = self.home / ".config/karabiner/karabiner.json"
        configuration_path.parent.mkdir(parents=True)
        configuration_path.write_text(
            json.dumps({
                "global": {"show_in_menu_bar": False},
                "profiles": [{
                    "name": "Custom profile",
                    "selected": True,
                    "simple_modifications": [{"from": {"key_code": "a"}, "to": [{"key_code": "b"}]}],
                }],
            })
        )

        self.generator.install_karabiner_rules(str(self.home))

        configuration = json.loads(configuration_path.read_text())
        self.assertEqual(configuration["global"], {"show_in_menu_bar": False})
        profile = configuration["profiles"][0]
        self.assertEqual(profile["name"], "Custom profile")
        self.assertEqual(
            profile["simple_modifications"],
            [{"from": {"key_code": "a"}, "to": [{"key_code": "b"}]}],
        )
        self.assertEqual(len(profile["complex_modifications"]["rules"]), 13)


if __name__ == "__main__":
    unittest.main()
