"""The Claude settings installer writes a real ~/.claude/settings.json from the base and private parts."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "!install/claude-settings.py"


def load_installer():
    specification = importlib.util.spec_from_file_location("claude_settings", INSTALLER)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class ClaudeSettingsInstallerTests(unittest.TestCase):
    def setUp(self):
        self.installer = load_installer()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.home = root / "home"
        self.repository_root = root / "dotfiles"
        self.base = self.repository_root / "claude/.claude/settings.base.json"
        self.private = self.home / ".claude/settings.private.json"
        self.live = self.home / ".claude/settings.json"
        self.base.parent.mkdir(parents=True)
        self.private.parent.mkdir(parents=True)

    def tearDown(self):
        self.directory.cleanup()

    def write_json(self, path, settings):
        path.write_text(json.dumps(settings))

    def install(self):
        return self.installer.install(self.home, repository_root=self.repository_root)

    def read_live(self):
        return json.loads(self.live.read_text())

    def test_install_writes_base_and_private_settings_into_a_private_file(self):
        self.write_json(self.base, {"theme": "dark"})
        self.write_json(self.private, {"autoMode": {"environment": ["work host"]}})

        self.assertTrue(self.install())

        self.assertEqual(self.read_live(), {"theme": "dark", "autoMode": {"environment": ["work host"]}})
        self.assertFalse(self.live.is_symlink())
        self.assertEqual(self.live.stat().st_mode & 0o777, 0o600)

    def test_install_works_without_a_private_file(self):
        self.write_json(self.base, {"theme": "dark"})

        self.install()

        self.assertEqual(self.read_live(), {"theme": "dark"})

    def test_base_wins_over_live_private_wins_over_base_and_other_live_keys_stay(self):
        self.write_json(self.live, {"model": "fable", "hooks": {"Stop": ["live"]}, "feedbackSurveyState": 3})
        self.write_json(self.base, {"model": "opus", "hooks": {"SessionStart": ["base"]}, "theme": "dark"})
        self.write_json(self.private, {"theme": "light"})

        self.install()

        self.assertEqual(
            self.read_live(),
            {
                "model": "opus",
                "hooks": {"Stop": ["live"], "SessionStart": ["base"]},
                "feedbackSurveyState": 3,
                "theme": "light",
            },
        )

    def test_a_list_from_a_later_part_replaces_the_earlier_list(self):
        self.write_json(self.base, {"autoMode": {"soft_deny": ["$defaults", "base rule"]}})
        self.write_json(self.private, {"autoMode": {"soft_deny": ["$defaults", "private rule"]}})

        self.install()

        self.assertEqual(self.read_live(), {"autoMode": {"soft_deny": ["$defaults", "private rule"]}})

    def test_second_install_changes_nothing(self):
        self.write_json(self.base, {"theme": "dark"})
        self.write_json(self.private, {"autoMode": {"environment": ["work host"]}})
        self.install()

        self.assertFalse(self.install())

    def test_install_replaces_the_old_stow_link_and_keeps_the_private_part_out_of_the_repository(self):
        old_tracked_file = self.repository_root / "claude/.claude/settings.json"
        self.write_json(old_tracked_file, {"model": "opus"})
        self.live.symlink_to(old_tracked_file)
        self.write_json(self.base, {"theme": "dark"})
        self.write_json(self.private, {"autoMode": {"environment": ["work host"]}})

        self.install()

        self.assertFalse(self.live.is_symlink())
        self.assertEqual(
            self.read_live(),
            {"model": "opus", "theme": "dark", "autoMode": {"environment": ["work host"]}},
        )
        self.assertEqual(json.loads(old_tracked_file.read_text()), {"model": "opus"})

    def test_install_replaces_a_broken_old_stow_link(self):
        self.live.symlink_to(self.repository_root / "claude/.claude/settings.json")
        self.write_json(self.base, {"theme": "dark"})

        self.install()

        self.assertFalse(self.live.is_symlink())
        self.assertEqual(self.read_live(), {"theme": "dark"})

    def test_install_stops_at_a_symlink_to_a_place_outside_the_repository(self):
        foreign_file = Path(self.directory.name) / "elsewhere.json"
        self.write_json(foreign_file, {"model": "opus"})
        self.live.symlink_to(foreign_file)
        self.write_json(self.base, {"theme": "dark"})

        with self.assertRaises(RuntimeError):
            self.install()

        self.assertTrue(self.live.is_symlink())
        self.assertEqual(json.loads(foreign_file.read_text()), {"model": "opus"})


if __name__ == "__main__":
    unittest.main()
