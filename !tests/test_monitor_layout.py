"""The monitor layout installer writes the LaunchAgent plist and manages launchctl state."""

import importlib.util
import os
from pathlib import Path
import plistlib
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "!install/monitor-layout.py"


def load_installer():
    specification = importlib.util.spec_from_file_location("monitor_layout", INSTALLER)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class MonitorLayoutInstallerTests(unittest.TestCase):
    def setUp(self):
        self.installer = load_installer()
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.binaries = self.root / "bin"
        self.binaries.mkdir()
        self.command_log = self.root / "launchctl.log"

    def tearDown(self):
        self.directory.cleanup()

    def write_fake_launchctl(self, print_exit_status: int) -> dict[str, str]:
        launchctl = self.binaries / "launchctl"
        launchctl.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$*" >> "$FAKE_LAUNCHCTL_LOG"\n'
            'if [ "$1" = "print" ]; then exit ' + str(print_exit_status) + "; fi\n"
            "exit 0\n"
        )
        launchctl.chmod(0o755)
        return {
            **os.environ,
            "PATH": str(self.binaries) + os.pathsep + os.environ["PATH"],
            "FAKE_LAUNCHCTL_LOG": str(self.command_log),
        }

    def recorded_calls(self) -> list[str]:
        if not self.command_log.exists():
            return []
        return self.command_log.read_text().splitlines()

    def test_plist_bytes_match_expected_launch_agent_fields(self):
        payload = plistlib.loads(
            self.installer.monitor_layout_plist_bytes(
                Path("/Users/example"),
                Path("/opt/homebrew/bin/python3"),
            )
        )
        self.assertEqual(payload["Label"], "local.monitor-layout")
        self.assertEqual(
            payload["ProgramArguments"],
            ["/opt/homebrew/bin/python3", "/Users/example/.config/monitors/macos.py"],
        )
        self.assertEqual(payload["StartInterval"], 10)
        self.assertTrue(payload["RunAtLoad"])

    def test_install_bootstraps_unloaded_service(self):
        environment = self.write_fake_launchctl(print_exit_status=113)
        plist_path = self.installer.install(
            self.home,
            user_identifier=501,
            python_executable=Path("/opt/homebrew/bin/python3"),
            command_environment=environment,
        )

        self.assertTrue(plist_path.is_file())
        self.assertEqual(
            self.recorded_calls(),
            [
                "print gui/501/local.monitor-layout",
                f"bootstrap gui/501 {plist_path}",
            ],
        )

    def test_second_install_with_unchanged_plist_does_not_reload_running_service(self):
        environment = self.write_fake_launchctl(print_exit_status=0)
        self.installer.install(
            self.home,
            user_identifier=501,
            python_executable=Path("/opt/homebrew/bin/python3"),
            command_environment=environment,
        )
        self.command_log.unlink()

        self.installer.install(
            self.home,
            user_identifier=501,
            python_executable=Path("/opt/homebrew/bin/python3"),
            command_environment=environment,
        )
        self.assertEqual(self.recorded_calls(), ["print gui/501/local.monitor-layout"])


if __name__ == "__main__":
    unittest.main()
