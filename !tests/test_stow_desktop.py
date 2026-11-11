"""Package installation must preserve running desktop applications."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


STOW_SCRIPT = Path(__file__).resolve().parents[1] / "stow.fish"


@unittest.skipUnless(shutil.which("fish") and shutil.which("stow"), "fish and stow are required")
class StowDesktopTests(unittest.TestCase):
    def test_installation_links_files_without_signalling_or_reloading_the_desktop(self):
        for package_name in ("agents", "hypr", "ghostty"):
            with self.subTest(package=package_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repository = root / "repository"
                repository.mkdir()
                shutil.copyfile(STOW_SCRIPT, repository / "stow.fish")
                package = repository / package_name
                package.mkdir()
                (package / "installed-file").write_text("preserve the desktop\n")
                subprocess.run(["git", "init", "--quiet", str(repository)], check=True)

                home_directory = root / "home"
                (home_directory / ".config/hypr").mkdir(parents=True)
                commands = root / "commands"
                commands.mkdir()
                command_log = root / "desktop-commands"
                # These commands record attempted desktop changes instead of
                # contacting the user's compositor or sending process signals.
                for command_name in ("hyprctl", "pkill", "aerospace"):
                    command = commands / command_name
                    command.write_text('#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$DESKTOP_COMMAND_LOG"\n')
                    command.chmod(0o755)
                for command_name in ("ghostty", "pgrep"):
                    command = commands / command_name
                    command.write_text("#!/bin/sh\nexit 0\n")
                    command.chmod(0o755)

                environment = dict(os.environ, HOME=str(home_directory),
                                   PATH=str(commands) + os.pathsep + os.environ["PATH"],
                                   HYPRLAND_INSTANCE_SIGNATURE="test-instance",
                                   DESKTOP_COMMAND_LOG=str(command_log))
                result = subprocess.run(
                    ["fish", "--no-config", str(repository / "stow.fish"),
                     "--no-adopt", package_name],
                    env=environment, capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((home_directory / "installed-file").read_text(),
                                 "preserve the desktop\n")
                self.assertFalse(command_log.exists(),
                                 command_log.read_text() if command_log.exists() else "")
