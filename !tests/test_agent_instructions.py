"""The instructions installer links the shared agent files for Antigravity."""

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
