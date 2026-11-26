"""The instructions installer links the shared agent files for Antigravity."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "!install/agent-instructions.py"


def load_installer():
    specification = importlib.util.spec_from_file_location("agent_instructions", INSTALLER)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class AntigravityLinkTests(unittest.TestCase):
    def setUp(self):
        self.installer = load_installer()
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name)
        (self.home / ".agents/skills/example").mkdir(parents=True)

    def tearDown(self):
        self.directory.cleanup()

    def test_install_points_antigravity_at_shared_skills_and_local_rules(self):
        self.installer.install(self.home)

        configuration = self.home / ".gemini/config"
        self.assertEqual((configuration / "skills").resolve(), (self.home / ".agents/skills").resolve())
        self.assertTrue((configuration / "skills/example").is_dir())
        self.assertEqual(
            (configuration / "GEMINI.md").resolve(), (self.home / ".agents/local.md").resolve()
        )

    def test_second_install_keeps_the_links(self):
        self.installer.install(self.home)
        self.installer.install(self.home)

        self.assertTrue((self.home / ".gemini/config/skills").is_symlink())

    def test_install_stops_before_replacing_a_real_skills_folder(self):
        own_skills = self.home / ".gemini/config/skills"
        own_skills.mkdir(parents=True)

        with self.assertRaises(RuntimeError):
            self.installer.install(self.home)
        self.assertFalse(own_skills.is_symlink())
        self.assertFalse((self.home / ".codex/hooks.json").exists())


class AntigravityAgentModeTests(unittest.TestCase):
    def setUp(self):
        self.installer = load_installer()
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name) / "home"
        self.repository_root = Path(self.directory.name) / "dotfiles"
        self.home.mkdir()
        self.repository_root.mkdir()
        self.settings = self.home / ".gemini/antigravity-cli/settings.json"
        self.expected_skill_rules = [
            f"read_file({self.home / '.gemini/config/skills'})",
            f"read_file({self.home / '.agents/skills'})",
            f"read_file({self.repository_root / 'agents/.agents/skills'})",
        ]

    def tearDown(self):
        self.directory.cleanup()

    def read_settings(self):
        return json.loads(self.settings.read_text())

    def test_install_starts_agy_in_auto_mode_and_allows_reading_skills(self):
        self.installer.install(self.home, repository_root=self.repository_root)

        self.assertEqual(
            self.read_settings(),
            {
                "agentMode": "auto",
                "permissions": {"allow": self.expected_skill_rules},
            },
        )

    def test_install_keeps_the_other_agy_settings_and_permission_rules(self):
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(
            json.dumps(
                {
                    "trustedWorkspaces": ["/work"],
                    "permissions": {
                        "allow": ["command(git)", self.expected_skill_rules[0]],
                        "deny": ["command(rm -rf)"],
                    },
                }
            )
        )

        self.installer.install(self.home, repository_root=self.repository_root)

        self.assertEqual(
            self.read_settings(),
            {
                "trustedWorkspaces": ["/work"],
                "agentMode": "auto",
                "permissions": {
                    "allow": ["command(git)", *self.expected_skill_rules],
                    "deny": ["command(rm -rf)"],
                },
            },
        )

    def test_second_install_does_not_duplicate_skill_read_permissions(self):
        self.installer.install(self.home, repository_root=self.repository_root)
        self.installer.install(self.home, repository_root=self.repository_root)

        self.assertEqual(
            self.read_settings()["permissions"]["allow"],
            self.expected_skill_rules,
        )

    def test_install_keeps_a_mode_chosen_on_this_machine(self):
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps({"agentMode": ""}))

        self.installer.install(self.home, repository_root=self.repository_root)

        self.assertEqual(self.read_settings()["agentMode"], "")
        self.assertEqual(
            self.read_settings()["permissions"],
            {"allow": self.expected_skill_rules},
        )

    def test_install_stops_on_unreadable_agy_settings(self):
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text("{not json")

        with self.assertRaises(ValueError):
            self.installer.install(self.home, repository_root=self.repository_root)
        self.assertFalse((self.home / ".agents/local.md").exists())

    def test_install_stops_on_malformed_agy_permissions_shape(self):
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps({"permissions": ["not-an-object"]}))

        with self.assertRaises(ValueError):
            self.installer.install(self.home, repository_root=self.repository_root)
        self.assertFalse((self.home / ".agents/local.md").exists())


if __name__ == "__main__":
    unittest.main()
