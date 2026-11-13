"""Install and load the macOS LaunchAgent that runs ~/.config/monitors/macos.py."""

import os
from pathlib import Path
import plistlib
import subprocess
from typing import Callable


SERVICE_LABEL = "local.monitor-layout"
PYTHON_CANDIDATES = (
    Path("/opt/homebrew/bin/python3"),
    Path("/usr/local/bin/python3"),
    Path("/usr/bin/python3"),
)


def is_executable_file(candidate_path: Path) -> bool:
    return os.access(candidate_path, os.X_OK)


def select_python_executable(
    candidate_paths: tuple[Path, ...] = PYTHON_CANDIDATES,
    executable_predicate: Callable[[Path], bool] = is_executable_file,
) -> Path:
    for candidate_path in candidate_paths:
        if executable_predicate(candidate_path):
            return candidate_path
    return Path("/usr/bin/python3")


def monitor_layout_plist_bytes(home_directory: Path, python_executable: Path) -> bytes:
    log_path = str(home_directory / "Library/Logs/monitor-layout.log")
    configuration = {
        "Label": SERVICE_LABEL,
        "LimitLoadToSessionType": "Aqua",
        "ProcessType": "Background",
        "ProgramArguments": [
            str(python_executable),
            str(home_directory / ".config/monitors/macos.py"),
        ],
        "RunAtLoad": True,
        "StandardErrorPath": log_path,
        "StandardOutPath": log_path,
        "StartInterval": 10,
    }
    return plistlib.dumps(configuration)


def launchctl_commands(
    user_identifier: int,
    plist_path: Path,
    service_is_loaded: bool,
    plist_changed: bool,
) -> list[list[str]]:
    domain_target = f"gui/{user_identifier}"
    if not service_is_loaded:
        return [["launchctl", "bootstrap", domain_target, str(plist_path)]]
    if plist_changed:
        return [
            ["launchctl", "bootout", domain_target, str(plist_path)],
            ["launchctl", "bootstrap", domain_target, str(plist_path)],
        ]
    return []


def write_monitor_layout_plist(
    home_directory: Path,
    python_executable: Path,
) -> tuple[Path, bool]:
    launch_agents_directory = home_directory / "Library/LaunchAgents"
    logs_directory = home_directory / "Library/Logs"
    launch_agents_directory.mkdir(parents=True, exist_ok=True)
    logs_directory.mkdir(parents=True, exist_ok=True)

    plist_path = launch_agents_directory / f"{SERVICE_LABEL}.plist"
    wanted_bytes = monitor_layout_plist_bytes(home_directory, python_executable)
    existing_bytes = plist_path.read_bytes() if plist_path.exists() else None
    if existing_bytes == wanted_bytes:
        return plist_path, False

    plist_path.write_bytes(wanted_bytes)
    return plist_path, True


def install(
    home_directory: Path,
    user_identifier: int | None = None,
    python_executable: Path | None = None,
    command_environment: dict[str, str] | None = None,
) -> Path:
    resolved_user_identifier = os.getuid() if user_identifier is None else user_identifier
    resolved_python = python_executable or select_python_executable()
    plist_path, plist_changed = write_monitor_layout_plist(home_directory, resolved_python)

    service_target = f"gui/{resolved_user_identifier}/{SERVICE_LABEL}"
    probe_result = subprocess.run(
        ["launchctl", "print", service_target],
        env=command_environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    service_is_loaded = probe_result.returncode == 0

    for command in launchctl_commands(
        resolved_user_identifier,
        plist_path,
        service_is_loaded=service_is_loaded,
        plist_changed=plist_changed,
    ):
        # bootout can return non-zero if the agent exited between print and bootout.
        is_bootout = len(command) >= 2 and command[1] == "bootout"
        subprocess.run(
            command,
            env=command_environment,
            check=not is_bootout,
            stdout=subprocess.DEVNULL if is_bootout else None,
            stderr=subprocess.DEVNULL if is_bootout else None,
        )

    return plist_path


if __name__ == "__main__":
    installed_plist = install(Path.home())
    print(f"Installed and loaded {installed_plist}.")
