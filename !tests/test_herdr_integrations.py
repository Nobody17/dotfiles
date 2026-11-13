"""The Herdr integrations installer keeps tracked Claude and Pi files clean."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "!install/herdr-integrations.py"


def load_installer():
    specification = importlib.util.spec_from_file_location("herdr_integrations", INSTALLER)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class HerdrIntegrationsInstallerTests(unittest.TestCase):
    def setUp(self):
        self.installer = load_installer()
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.call_log = self.root / "herdr-calls.jsonl"
        self.fake_herdr = self.root / "herdr"
        self.fake_herdr.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, sys\n"
            "home = pathlib.Path(os.environ['HOME'])\n"
            "target = sys.argv[3]\n"
            "with open(os.environ['FAKE_HERDR_CALLS'], 'a') as handle:\n"
            "    handle.write(json.dumps({'target': target, 'home': str(home)}) + '\\n')\n"
            "if target == 'claude':\n"
            "    hook = home / '.claude/hooks/herdr-agent-state.sh'\n"
            "    hook.parent.mkdir(parents=True, exist_ok=True)\n"
            "    hook.write_text('#!/bin/bash\\necho claude-hook\\n')\n"
            "    (home / '.claude/settings.json').write_text(json.dumps({'mutated': str(home)}))\n"
            "elif target == 'codex':\n"
            "    (home / '.codex/herdr-agent-state.sh').write_text('#!/bin/bash\\n')\n"
            "elif target == 'antigravity-cli':\n"
            "    hook = home / '.gemini/config/hooks/herdr-agent-state.sh'\n"
            "    hook.parent.mkdir(parents=True, exist_ok=True)\n"
            "    hook.write_text('#!/bin/bash\\n')\n"
            "elif target == 'pi':\n"
            "    (home / '.pi/agent/extensions/herdr-agent-state.ts').write_text('// pi-hook\\n')\n"
        )
        self.fake_herdr.chmod(0o755)
        self.environment = {
            **os.environ,
            "FAKE_HERDR_CALLS": str(self.call_log),
        }

    def tearDown(self):
        self.directory.cleanup()

    def recorded_calls(self) -> list[dict[str, str]]:
        return [json.loads(line) for line in self.call_log.read_text().splitlines()]

    def test_install_preserves_tracked_claude_settings_and_pi_extension(self):
        claude_settings = self.home / ".claude/settings.json"
        claude_settings.parent.mkdir(parents=True)
        claude_settings.write_text('{"portable": "$HOME/.claude/hooks/herdr-agent-state.sh"}\n')

        pi_extension = self.home / ".pi/agent/extensions/herdr-agent-state.ts"
        pi_extension.parent.mkdir(parents=True)
        pi_extension.write_text("// tracked in dotfiles\n")

        self.installer.install(
            self.home,
            herdr_executable=str(self.fake_herdr),
            base_environment=self.environment,
        )

        self.assertEqual(
            claude_settings.read_text(),
            '{"portable": "$HOME/.claude/hooks/herdr-agent-state.sh"}\n',
        )
        claude_hook = self.home / ".claude/hooks/herdr-agent-state.sh"
        self.assertEqual(claude_hook.read_text(), "#!/bin/bash\necho claude-hook\n")
        self.assertTrue(os.access(claude_hook, os.X_OK))
        self.assertEqual(pi_extension.read_text(), "// tracked in dotfiles\n")
        self.assertTrue((self.home / ".codex/herdr-agent-state.sh").is_file())
        self.assertTrue((self.home / ".gemini/config/hooks/herdr-agent-state.sh").is_file())

        targets = [entry["target"] for entry in self.recorded_calls()]
        self.assertEqual(targets, ["codex", "antigravity-cli", "claude"])

    def test_install_adds_pi_extension_when_missing(self):
        self.installer.install(
            self.home,
            herdr_executable=str(self.fake_herdr),
            base_environment=self.environment,
        )

        self.assertEqual(
            (self.home / ".pi/agent/extensions/herdr-agent-state.ts").read_text(),
            "// pi-hook\n",
        )
        targets = [entry["target"] for entry in self.recorded_calls()]
        self.assertEqual(targets, ["codex", "antigravity-cli", "pi", "claude"])


if __name__ == "__main__":
    unittest.main()
