"""Install Herdr agent integrations without modifying tracked repository files."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def direct_integration_targets(home_directory: Path) -> list[tuple[str, Path]]:
    """Targets whose hook files stay untracked in $HOME."""
    targets = [
        ("codex", home_directory / ".codex"),
        ("antigravity-cli", home_directory / ".gemini/config"),
    ]
    pi_extension_path = home_directory / ".pi/agent/extensions/herdr-agent-state.ts"
    if not pi_extension_path.exists():
        targets.append(("pi", home_directory / ".pi/agent/extensions"))
    return targets


def run_herdr_integration_install(
    herdr_executable: str,
    target_name: str,
    target_home_directory: Path,
    base_environment: dict[str, str] | None = None,
) -> None:
    environment = dict(os.environ if base_environment is None else base_environment)
    environment["HOME"] = str(target_home_directory)
    subprocess.run(
        [herdr_executable, "integration", "install", target_name],
        env=environment,
        check=True,
    )


def install_claude_hook_script(
    home_directory: Path,
    herdr_executable: str,
    base_environment: dict[str, str] | None = None,
) -> Path:
    """Stage Claude's hook script in a temporary HOME so tracked settings.json stays clean.

    claude/.claude/settings.json already invokes $HOME/.claude/hooks/herdr-agent-state.sh
    portably on both Linux and macOS. Running `herdr integration install claude` directly
    on $HOME would append a machine-specific absolute path into that tracked file.
    """
    with tempfile.TemporaryDirectory() as temporary_home_name:
        temporary_home = Path(temporary_home_name)
        (temporary_home / ".claude").mkdir(parents=True)
        run_herdr_integration_install(
            herdr_executable,
            "claude",
            temporary_home,
            base_environment=base_environment,
        )
        staged_hook_path = temporary_home / ".claude/hooks/herdr-agent-state.sh"
        destination_hook_path = home_directory / ".claude/hooks/herdr-agent-state.sh"
        destination_hook_path.parent.mkdir(parents=True, exist_ok=True)
        staged_bytes = staged_hook_path.read_bytes()
        if not destination_hook_path.exists() or destination_hook_path.read_bytes() != staged_bytes:
            destination_hook_path.write_bytes(staged_bytes)
        destination_hook_path.chmod(0o755)
        return destination_hook_path


def install(
    home_directory: Path,
    herdr_executable: str | None = None,
    base_environment: dict[str, str] | None = None,
) -> None:
    resolved_herdr = herdr_executable or shutil.which("herdr")
    if not resolved_herdr:
        raise RuntimeError("herdr was not found on PATH; run mise.fish first.")

    for target_name, required_directory in direct_integration_targets(home_directory):
        required_directory.mkdir(parents=True, exist_ok=True)
        run_herdr_integration_install(
            resolved_herdr,
            target_name,
            home_directory,
            base_environment=base_environment,
        )

    install_claude_hook_script(
        home_directory,
        resolved_herdr,
        base_environment=base_environment,
    )


if __name__ == "__main__":
    install(Path.home())
    print("Installed Herdr integrations for Claude, Codex, Antigravity CLI, and Pi.")
    print("In Codex, review and trust the Herdr SessionStart hook with /hooks.")
