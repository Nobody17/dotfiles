"""Run with python3 -m unittest discover -s '!tests' -p 'test_codex_herdr.py'."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


FUNCTION = Path(__file__).resolve().parents[1] / "fish/.config/fish/functions/codex.fish"


@unittest.skipUnless(shutil.which("fish"), "fish is required")
class CodexHerdrTests(unittest.TestCase):
    def run_codex(self, arguments, inside_herdr=True):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "codex"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "print(json.dumps(sys.argv[1:]))\n"
            )
            executable.chmod(0o755)
            environment = dict(os.environ, PATH=directory + os.pathsep + os.environ["PATH"])
            environment.pop("HERDR_ENV", None)
            if inside_herdr:
                environment["HERDR_ENV"] = "1"
            result = subprocess.run(
                ["fish", "--no-config", "-c", 'source "$argv[1]"; codex $argv[2..-1]',
                 str(FUNCTION), *arguments],
                env=environment, text=True, capture_output=True, check=True,
            )
            return json.loads(result.stdout)

    def test_new_and_restored_chats_keep_their_own_server(self):
        for arguments in ([], ["resume", "saved-chat"], ["fork", "saved-chat"],
                          ["--model", "chosen-model", "a prompt with spaces"]):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.run_codex(arguments), ["--no-daemon", *arguments])

    def test_outside_herdr_preserves_normal_startup(self):
        self.assertEqual(self.run_codex(["resume", "saved-chat"], False),
                         ["resume", "saved-chat"])

    def test_explicit_shared_or_remote_connections_are_preserved(self):
        for arguments in (["agents"], ["remote-control", "status"],
                          ["--remote", "unix:///tmp/explicit.sock"],
                          ["--remote=unix:///tmp/explicit.sock"]):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.run_codex(arguments), arguments)

    def test_explicit_standalone_option_is_not_duplicated(self):
        self.assertEqual(self.run_codex(["--no-daemon", "resume", "saved-chat"]),
                         ["--no-daemon", "resume", "saved-chat"])
